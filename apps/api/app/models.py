"""SQLAlchemy модели. Ни один документ пользователя не хранится в текстовом виде в БД —
только метаданные и ссылки на объекты в S3/MinIO. Содержимое файлов не попадает в логи."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.products import DEFAULT_PRODUCT_CODE
from app.products import ProductCode as ProductCode  # re-exported for convenience


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BatchStatus(str, enum.Enum):
    uploading = "uploading"
    diagnosed = "diagnosed"
    awaiting_payment = "awaiting_payment"
    paid = "paid"
    processing = "processing"
    ready = "ready"
    expired = "expired"
    deleted = "deleted"


class Severity(str, enum.Enum):
    critical = "critical"
    warning = "warning"
    recommendation = "recommendation"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    canceled = "canceled"
    failed = "failed"
    refunded = "refunded"


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # обезличенный источник трафика (utm_*), без cookie сторонних трекеров
    utm_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(120), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(120), nullable=True)

    batches: Mapped[list["UploadBatch"]] = relationship(back_populates="session")


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_sessions.id"))
    batch_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("upload_batches.id"), nullable=True)
    consent_text_version: Mapped[str] = mapped_column(String(40))
    given_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # хэш IP, не сам IP


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("user_sessions.id"))
    # Какой "цифровой аппарат" обрабатывает эту загрузку. default/server_default = ARBITRPACK —
    # обратная совместимость: старые вызовы upload без явного product_code не ломаются.
    product_code: Mapped[ProductCode] = mapped_column(
        Enum(ProductCode), default=ProductCode.ARBITRPACK, server_default=DEFAULT_PRODUCT_CODE
    )
    status: Mapped[BatchStatus] = mapped_column(Enum(BatchStatus), default=BatchStatus.uploading)
    ttl_hours: Mapped[int] = mapped_column(Integer, default=72)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped["UserSession"] = relationship(back_populates="batches")
    files: Mapped[list["UploadedFile"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="batch")
    payments: Mapped[list["Payment"]] = relationship(back_populates="batch")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_batches.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    safe_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(500))  # случайное внутреннее имя объекта в S3
    content_type: Mapped[str] = mapped_column(String(120))
    detected_mime: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    batch: Mapped["UploadBatch"] = relationship(back_populates="files")
    results: Mapped[list["ValidationResult"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class ValidationRule(Base):
    """Снимок правила, применённого при диагностике — для воспроизводимости отчётов даже если
    rules.yaml изменится позже."""

    __tablename__ = "validation_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text)
    default_severity: Mapped[Severity] = mapped_column(Enum(Severity))
    rules_version: Mapped[int] = mapped_column(Integer, default=1)


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    file_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("uploaded_files.id"), nullable=True)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_batches.id"))
    rule_code: Mapped[str] = mapped_column(String(80))
    severity: Mapped[Severity] = mapped_column(Enum(Severity))
    message: Mapped[str] = mapped_column(Text)
    auto_fixable: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    file: Mapped["UploadedFile | None"] = relationship(back_populates="results")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_batches.id"))
    product_code: Mapped[ProductCode] = mapped_column(
        Enum(ProductCode), default=ProductCode.ARBITRPACK, server_default=DEFAULT_PRODUCT_CODE
    )
    is_paid_run: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending|running|done|failed
    operations_performed: Mapped[list] = mapped_column(JSON, default=list)
    archive_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    archive_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch: Mapped["UploadBatch"] = relationship(back_populates="jobs")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_payment_idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("upload_batches.id"))
    product_code: Mapped[ProductCode] = mapped_column(
        Enum(ProductCode), default=ProductCode.ARBITRPACK, server_default=DEFAULT_PRODUCT_CODE
    )
    provider: Mapped[str] = mapped_column(String(30))  # mock | yookassa
    provider_payment_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    amount_value: Mapped[str] = mapped_column(String(20))  # строка, как того требует API ЮKassa ("399.00")
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), default=PaymentStatus.pending)
    confirmation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # обезличенный источник события webhook (например "yookassa-webhook" | "poll" | "mock")
    event_source: Mapped[str | None] = mapped_column(String(60), nullable=True)

    batch: Mapped["UploadBatch"] = relationship(back_populates="payments")


class ProcessedWebhookEvent(Base):
    """Гарантия идемпотентности: один и тот же (provider, provider_payment_id, status) обрабатывается один раз."""

    __tablename__ = "processed_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_payment_id", "status", name="uq_webhook_event"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    provider: Mapped[str] = mapped_column(String(30))
    provider_payment_id: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DownloadToken(Base):
    __tablename__ = "download_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("processing_jobs.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 токена, сам токен не хранится
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEvent(Base):
    """Журнал операций. Содержимое документов и оригинальные имена файлов НИКОГДА сюда не пишутся."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    product_code: Mapped[ProductCode] = mapped_column(
        Enum(ProductCode), default=ProductCode.ARBITRPACK, server_default=DEFAULT_PRODUCT_CODE, index=True
    )
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # только метаданные/идентификаторы
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AnalyticsEvent(Base):
    """Продуктовая аналитика (см. docs/analytics.md). Не содержит имён файлов, содержимого документов
    или сторонних трекеров."""

    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    product_code: Mapped[ProductCode] = mapped_column(
        Enum(ProductCode), default=ProductCode.ARBITRPACK, server_default=DEFAULT_PRODUCT_CODE, index=True
    )
    event_name: Mapped[str] = mapped_column(String(80), index=True)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
