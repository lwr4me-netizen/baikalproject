from app.payments.base import PaymentProvider, PaymentStatusResult
from app.payments.mock import MockPaymentProvider
from app.payments.yookassa import YooKassaPaymentProvider

__all__ = ["PaymentProvider", "PaymentStatusResult", "MockPaymentProvider", "YooKassaPaymentProvider", "get_payment_provider"]


def get_payment_provider() -> PaymentProvider:
    from app.config import get_settings

    settings = get_settings()
    if settings.payment_provider == "yookassa":
        return YooKassaPaymentProvider()
    return MockPaymentProvider()
