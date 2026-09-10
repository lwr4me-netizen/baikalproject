from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ConsentIn(BaseModel):
    consent_given: bool
    ttl_hours: int = 72


class IssueOut(BaseModel):
    rule_code: str
    severity: str
    message: str
    auto_fixable: bool = False


class FileResultOut(BaseModel):
    original_filename: str
    size_bytes: int
    page_count: int | None
    issues: list[IssueOut]


class DiagnosticsOut(BaseModel):
    batch_id: str
    product_code: str = "ARBITRPACK"
    file_count: int
    critical_count: int
    warning_count: int
    recommendation_count: int
    categories: list[str]
    files_needing_fix: list[str]
    auto_fixable_count: int
    files: list[FileResultOut]
    can_download_free: bool = False


class CreatePaymentIn(BaseModel):
    batch_id: str


class PaymentOut(BaseModel):
    payment_id: str
    product_code: str = "ARBITRPACK"
    status: str
    confirmation_url: str | None
    amount_value: str
    currency: str


class WebhookAck(BaseModel):
    received: bool = True


class JobStatusOut(BaseModel):
    job_id: str
    product_code: str = "ARBITRPACK"
    status: str
    operations_performed: list[str]
    download_token: str | None = None
    expires_at: datetime | None = None


class ErrorOut(BaseModel):
    detail: str
