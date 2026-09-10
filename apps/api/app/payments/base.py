"""Интерфейс платёжного провайдера. Любая реализация должна:
- принимать внутренний ключ идемпотентности, сгенерированный сервером (не клиентом);
- никогда не выдавать платный результат до подтверждённого статуса `succeeded`;
- уметь опрашивать актуальный статус независимо от тела webhook (см. R-9 в requirements-sources.md)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CreatedPayment:
    provider_payment_id: str
    confirmation_url: str
    status: str


@dataclass
class PaymentStatusResult:
    provider_payment_id: str
    status: str  # pending | succeeded | canceled | failed
    amount_value: str
    currency: str


class PaymentProvider(ABC):
    name: str = "base"

    @abstractmethod
    def create_payment(
        self,
        *,
        amount_value: str,
        currency: str,
        idempotency_key: str,
        return_url: str,
        description: str,
        metadata: dict,
    ) -> CreatedPayment: ...

    @abstractmethod
    def get_status(self, provider_payment_id: str) -> PaymentStatusResult: ...

    @abstractmethod
    def parse_webhook(self, raw_body: bytes, headers: dict) -> dict:
        """Парсит событие webhook и возвращает {provider_payment_id, status} для использования
        только как ПОДСКАЗКИ, какой платёж перепроверить через get_status(). Тело webhook
        никогда не используется напрямую для выдачи результата."""
        ...
