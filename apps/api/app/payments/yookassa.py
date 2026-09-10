"""Адаптер тестового магазина ЮKassa (https://yookassa.ru/developers).
Реализация протестирована на замоканных HTTP-вызовах (httpx.MockTransport) — реальные ключи
тестового магазина владельцем не предоставлены (см. финальный отчёт). Переменные окружения:
ARBITRPACK_YOOKASSA_SHOP_ID, ARBITRPACK_YOOKASSA_SECRET_KEY. Без них create_payment() выбросит
RuntimeError с понятным сообщением, а не тихо использует пустые значения."""
from __future__ import annotations

import base64
import json

import httpx

from app.config import get_settings
from app.payments.base import CreatedPayment, PaymentProvider, PaymentStatusResult


class YooKassaConfigError(RuntimeError):
    pass


class YooKassaPaymentProvider(PaymentProvider):
    name = "yookassa"

    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        if not settings.yookassa_shop_id or not settings.yookassa_secret_key:
            raise YooKassaConfigError(
                "Не заданы ARBITRPACK_YOOKASSA_SHOP_ID / ARBITRPACK_YOOKASSA_SECRET_KEY. "
                "Получите их в личном кабинете тестового магазина ЮKassa и добавьте в .env "
                "(см. README раздел 'Платежи')."
            )
        self._base_url = settings.yookassa_api_base
        token = base64.b64encode(f"{settings.yookassa_shop_id}:{settings.yookassa_secret_key}".encode()).decode()
        self._auth_header = f"Basic {token}"
        self._client = client or httpx.Client(base_url=self._base_url, timeout=15.0)

    def create_payment(self, *, amount_value, currency, idempotency_key, return_url, description, metadata) -> CreatedPayment:
        body = {
            "amount": {"value": amount_value, "currency": currency},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description[:128],
            "metadata": metadata,
        }
        resp = self._client.post(
            "/payments",
            headers={
                "Authorization": self._auth_header,
                "Idempotence-Key": idempotency_key,  # R-8: обязательный заголовок для защиты от дублей
                "Content-Type": "application/json",
            },
            content=json.dumps(body),
        )
        resp.raise_for_status()
        data = resp.json()
        return CreatedPayment(
            provider_payment_id=data["id"],
            confirmation_url=data["confirmation"]["confirmation_url"],
            status=data["status"],
        )

    def get_status(self, provider_payment_id: str) -> PaymentStatusResult:
        resp = self._client.get(f"/payments/{provider_payment_id}", headers={"Authorization": self._auth_header})
        resp.raise_for_status()
        data = resp.json()
        return PaymentStatusResult(
            provider_payment_id=data["id"],
            status=data["status"],
            amount_value=data["amount"]["value"],
            currency=data["amount"]["currency"],
        )

    def parse_webhook(self, raw_body: bytes, headers: dict) -> dict:
        payload = json.loads(raw_body or b"{}")
        obj = payload.get("object", {})
        return {"provider_payment_id": obj.get("id"), "status": obj.get("status")}
