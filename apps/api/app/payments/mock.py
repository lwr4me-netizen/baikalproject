"""Mock-провайдер для локальной разработки и тестов. Не требует сети и реальных ключей.
Симулирует ЮKassa: create -> pending -> (внешний вызов /mock/confirm или /mock/cancel) -> succeeded/canceled."""
from __future__ import annotations

import json
import uuid

from app.payments.base import CreatedPayment, PaymentProvider, PaymentStatusResult

# In-memory состояние на процесс — достаточно для dev/test, не переживает рестарт (это mock).
_STATE: dict[str, dict] = {}


class MockPaymentProvider(PaymentProvider):
    name = "mock"

    def create_payment(self, *, amount_value, currency, idempotency_key, return_url, description, metadata) -> CreatedPayment:
        # идемпотентность: повторный вызов с тем же idempotency_key возвращает тот же платёж
        for pid, rec in _STATE.items():
            if rec["idempotency_key"] == idempotency_key:
                return CreatedPayment(provider_payment_id=pid, confirmation_url=rec["confirmation_url"], status=rec["status"])

        payment_id = f"mock_{uuid.uuid4().hex}"
        confirmation_url = f"{return_url}?mock_payment_id={payment_id}"
        _STATE[payment_id] = {
            "status": "pending",
            "amount_value": amount_value,
            "currency": currency,
            "idempotency_key": idempotency_key,
            "confirmation_url": confirmation_url,
            "metadata": metadata,
        }
        return CreatedPayment(provider_payment_id=payment_id, confirmation_url=confirmation_url, status="pending")

    def get_status(self, provider_payment_id: str) -> PaymentStatusResult:
        rec = _STATE.get(provider_payment_id)
        if rec is None:
            raise KeyError(f"Unknown mock payment {provider_payment_id}")
        return PaymentStatusResult(
            provider_payment_id=provider_payment_id,
            status=rec["status"],
            amount_value=rec["amount_value"],
            currency=rec["currency"],
        )

    def parse_webhook(self, raw_body: bytes, headers: dict) -> dict:
        payload = json.loads(raw_body or b"{}")
        return {"provider_payment_id": payload.get("provider_payment_id"), "status": payload.get("status")}

    # --- тестовые хелперы, не часть интерфейса PaymentProvider ---
    @staticmethod
    def simulate(provider_payment_id: str, new_status: str) -> None:
        if provider_payment_id in _STATE:
            _STATE[provider_payment_id]["status"] = new_status

    @staticmethod
    def reset() -> None:
        _STATE.clear()
