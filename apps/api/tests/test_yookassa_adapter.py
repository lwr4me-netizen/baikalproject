"""Тесты адаптера ЮKassa на замоканных HTTP-вызовах (httpx.MockTransport).
Реальные ключи тестового магазина владельцем не предоставлены — см. docs/requirements-sources.md R-8/R-9
и финальный отчёт. Эти тесты проверяют, что адаптер ПРАВИЛЬНО формирует запросы к официальному API,
а не то, что реальная ЮKassa действительно на них ответит."""
import json
import os

import httpx
import pytest

os.environ.setdefault("ARBITRPACK_YOOKASSA_SHOP_ID", "test-shop-id")
os.environ.setdefault("ARBITRPACK_YOOKASSA_SECRET_KEY", "test-secret-key-value")

from app.payments.yookassa import YooKassaConfigError, YooKassaPaymentProvider


def _mock_client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url="https://api.yookassa.ru/v3")


def test_missing_credentials_raises_clear_error(monkeypatch):
    monkeypatch.delenv("ARBITRPACK_YOOKASSA_SHOP_ID", raising=False)
    monkeypatch.delenv("ARBITRPACK_YOOKASSA_SECRET_KEY", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(YooKassaConfigError):
        YooKassaPaymentProvider()
    get_settings.cache_clear()
    os.environ["ARBITRPACK_YOOKASSA_SHOP_ID"] = "test-shop-id"
    os.environ["ARBITRPACK_YOOKASSA_SECRET_KEY"] = "test-secret-key-value"


def test_create_payment_sends_idempotence_key_and_auth():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "2c85d21b-000f-5000-8000-1234567890ab",
                "status": "pending",
                "confirmation": {"type": "redirect", "confirmation_url": "https://yookassa.ru/checkout/pay/xyz"},
                "amount": {"value": "399.00", "currency": "RUB"},
            },
        )

    provider = YooKassaPaymentProvider(client=_mock_client(handler))
    result = provider.create_payment(
        amount_value="399.00",
        currency="RUB",
        idempotency_key="idem-key-123",
        return_url="https://arbitrpack.ru/result/abc",
        description="Тестовый заказ",
        metadata={"batch_id": "abc"},
    )

    assert result.confirmation_url == "https://yookassa.ru/checkout/pay/xyz"
    assert captured["headers"]["idempotence-key"] == "idem-key-123"
    assert captured["headers"]["authorization"].startswith("Basic ")
    assert captured["body"]["amount"]["value"] == "399.00"
    assert captured["body"]["confirmation"]["return_url"] == "https://arbitrpack.ru/result/abc"


def test_get_status_returns_current_state():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": "pay_1", "status": "succeeded", "amount": {"value": "399.00", "currency": "RUB"}},
        )

    provider = YooKassaPaymentProvider(client=_mock_client(handler))
    status = provider.get_status("pay_1")
    assert status.status == "succeeded"
    assert status.amount_value == "399.00"


def test_parse_webhook_extracts_id_and_status_but_is_not_trusted_alone():
    def handler(request):
        return httpx.Response(200, json={})

    provider = YooKassaPaymentProvider(client=_mock_client(handler))
    body = json.dumps({"event": "payment.succeeded", "object": {"id": "pay_1", "status": "succeeded"}}).encode()
    hint = provider.parse_webhook(body, {})
    assert hint == {"provider_payment_id": "pay_1", "status": "succeeded"}
    # Примечание: приложение (app/routers/payments.py) намеренно НЕ использует hint["status"] напрямую —
    # оно всегда перезапрашивает get_status(). Это отдельно проверяется в test_payments_api.py через mock-провайдер.
