"""Продуктовая аналитика первого лица — без сторонних трекеров, без содержимого документов.
См. docs/analytics.md за списком событий и метрик."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AnalyticsEvent, AuditEvent
from app.products import DEFAULT_PRODUCT_CODE

VALID_EVENTS = {
    "page_view",
    "upload_started",
    "upload_completed",
    "diagnostics_started",
    "diagnostics_free_result_shown",
    "checkout_started",
    "payment_succeeded",
    "payment_failed",
    "archive_created",
    "archive_downloaded",
    "return_visit",
    "data_deleted",
}


def track(
    db: Session,
    *,
    event_name: str,
    session_id: str | None = None,
    batch_id: str | None = None,
    properties: dict | None = None,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> None:
    if event_name not in VALID_EVENTS:
        raise ValueError(f"Unknown analytics event: {event_name}")
    db.add(
        AnalyticsEvent(
            session_id=session_id,
            batch_id=batch_id,
            product_code=product_code,
            event_name=event_name,
            properties=properties or {},
        )
    )
    db.commit()


def audit(
    db: Session,
    *,
    event_type: str,
    batch_id: str | None = None,
    payload: dict | None = None,
    product_code: str = DEFAULT_PRODUCT_CODE,
) -> None:
    """Журнал операций для безопасности/поддержки. НИКОГДА не передавайте сюда имена файлов или контент."""
    db.add(AuditEvent(batch_id=batch_id, product_code=product_code, event_type=event_type, payload=payload or {}))
    db.commit()
