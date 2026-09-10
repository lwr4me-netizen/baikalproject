from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_rules, get_settings
from app.db import get_db
from app.products import get_product
from app.rate_limit import limiter
from app.models import BatchStatus, Payment, PaymentStatus, ProcessedWebhookEvent, ProcessingJob, UploadBatch
from app.payments import MockPaymentProvider, get_payment_provider
from app.payments.base import PaymentProvider
from app.schemas import CreatePaymentIn, JobStatusOut, PaymentOut
from app.security import generate_idempotency_key
from app.services.analytics import audit, track
from app.services.archive import build_archive
from app.services.tokens import issue_download_token
from app.storage import get_storage

router = APIRouter(prefix="/api", tags=["payments"])


def _batch_product_code(batch: UploadBatch) -> str:
    return batch.product_code.value if hasattr(batch.product_code, "value") else (batch.product_code or "ARBITRPACK")


def _price_for_batch(batch: UploadBatch) -> str:
    # Тариф ВСЕГДА берётся из product_code, уже сохранённого на батче при загрузке — никогда не из
    # значения, присланного клиентом на этапе оплаты (защита от подмены цены).
    rules = get_rules(_batch_product_code(batch))["pricing"]
    kopeks = rules["full_processing_price"]
    return f"{kopeks / 100:.2f}"


@router.post("/payments", response_model=PaymentOut)
def create_payment(payload: CreatePaymentIn, db: Session = Depends(get_db), provider: PaymentProvider = Depends(get_payment_provider)):
    batch = db.get(UploadBatch, payload.batch_id)
    if batch is None:
        raise HTTPException(404, "Загрузка не найдена.")
    if batch.status == BatchStatus.deleted:
        raise HTTPException(410, "Данные по этой загрузке уже удалены.")

    settings = get_settings()
    product_code = _batch_product_code(batch)
    product = get_product(product_code)
    amount_value = _price_for_batch(batch)
    idem_key = generate_idempotency_key()

    created = provider.create_payment(
        amount_value=amount_value,
        currency="RUB",
        idempotency_key=idem_key,
        return_url=f"{settings.frontend_base_url}/result/{batch.id}",
        description=f"{product.payment_description_prefix}, заказ {batch.id[:8]}",
        metadata={"batch_id": batch.id, "product_code": product_code},
    )

    payment = Payment(
        batch_id=batch.id,
        product_code=product_code,
        provider=provider.name,
        provider_payment_id=created.provider_payment_id,
        idempotency_key=idem_key,
        amount_value=amount_value,
        currency="RUB",
        status=PaymentStatus.pending,
    )
    db.add(payment)
    batch.status = BatchStatus.awaiting_payment
    db.commit()

    track(db, event_name="checkout_started", batch_id=batch.id, properties={"amount": amount_value}, product_code=product_code)

    return PaymentOut(payment_id=payment.id, product_code=product_code, status=payment.status.value, confirmation_url=created.confirmation_url, amount_value=amount_value, currency="RUB")


def _fulfil_paid_batch(db: Session, batch: UploadBatch) -> ProcessingJob:
    """Строит архив и выдаёт токен скачивания. Идемпотентно: если джоба для батча уже есть и готова — переиспользуется."""
    existing = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.batch_id == batch.id, ProcessingJob.is_paid_run == True)  # noqa: E712
        .order_by(ProcessingJob.started_at.desc())
        .first()
    )
    if existing is not None and existing.status == "done":
        return existing

    from app.models import UploadedFile, ValidationResult
    from app.services.diagnostics import FileDiagnostic
    from app.validators.file_checks import Issue

    storage = get_storage()
    files = db.query(UploadedFile).filter(UploadedFile.batch_id == batch.id).all()
    results = db.query(ValidationResult).filter(ValidationResult.batch_id == batch.id).all()
    by_file: dict[str, list] = {}
    for r in results:
        by_file.setdefault(r.file_id, []).append(r)

    diagnostics = []
    for f in files:
        data = storage.get(f.storage_key)
        issues = [Issue(r.rule_code, r.severity, r.message, r.auto_fixable) for r in by_file.get(f.id, [])]
        diagnostics.append(
            FileDiagnostic(
                original_filename=f.original_filename,
                safe_name=f.safe_filename,
                size_bytes=f.size_bytes,
                sha256=f.sha256,
                content_type=f.content_type,
                page_count=f.page_count,
                issues=issues,
                data=data,
            )
        )

    product_code = _batch_product_code(batch)
    job = ProcessingJob(
        batch_id=batch.id, product_code=product_code, is_paid_run=True, status="running", started_at=datetime.now(timezone.utc)
    )
    db.add(job)
    db.flush()

    try:
        archive_bytes, operations = build_archive(diagnostics, apply_autofixes=True, product_code=product_code)
        archive_key = f"batches/{batch.id}/results/{job.id}.zip"
        storage.put(archive_key, archive_bytes, content_type="application/zip")

        job.status = "done"
        job.operations_performed = operations
        job.archive_storage_key = archive_key
        from app.security import sha256_bytes

        job.archive_sha256 = sha256_bytes(archive_bytes)
        job.finished_at = datetime.now(timezone.utc)
        batch.status = BatchStatus.ready
        db.commit()

        audit(db, event_type="archive_created", batch_id=batch.id, payload={"job_id": job.id, "operation_count": len(operations)}, product_code=product_code)
        track(db, event_name="archive_created", batch_id=batch.id, product_code=product_code)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        db.commit()
        raise

    return job


@router.post("/payments/webhook")
@limiter.limit(lambda: get_settings().rate_limit_webhook_per_minute)
async def payments_webhook(request: Request, db: Session = Depends(get_db), provider: PaymentProvider = Depends(get_payment_provider)):
    raw_body = await request.body()
    hint = provider.parse_webhook(raw_body, dict(request.headers))
    provider_payment_id = hint.get("provider_payment_id")
    if not provider_payment_id:
        raise HTTPException(400, "Некорректный webhook: отсутствует идентификатор платежа.")

    audit(db, event_type="webhook_received", payload={"provider": provider.name, "provider_payment_id": provider_payment_id})

    # R-9: НИКОГДА не доверяем телу webhook напрямую — перепроверяем статус через API провайдера.
    status_result = provider.get_status(provider_payment_id)

    dedup_key = (provider.name, provider_payment_id, status_result.status)
    already_processed = (
        db.query(ProcessedWebhookEvent)
        .filter(
            ProcessedWebhookEvent.provider == dedup_key[0],
            ProcessedWebhookEvent.provider_payment_id == dedup_key[1],
            ProcessedWebhookEvent.status == dedup_key[2],
        )
        .first()
    )
    if already_processed is not None:
        return {"received": True, "duplicate": True}

    payment = db.query(Payment).filter(Payment.provider_payment_id == provider_payment_id, Payment.provider == provider.name).first()
    if payment is None:
        raise HTTPException(404, "Платёж не найден во внутренней системе.")

    payment_product_code = payment.product_code.value if hasattr(payment.product_code, "value") else (payment.product_code or "ARBITRPACK")

    # Проверка соответствия суммы и валюты (защита от подмены суммы в webhook)
    if status_result.amount_value != payment.amount_value or status_result.currency != payment.currency:
        audit(db, event_type="webhook_amount_mismatch", batch_id=payment.batch_id, payload={"payment_id": payment.id}, product_code=payment_product_code)
        raise HTTPException(409, "Сумма или валюта платежа не совпадает с ожидаемой.")

    db.add(ProcessedWebhookEvent(provider=provider.name, provider_payment_id=provider_payment_id, status=status_result.status))

    if status_result.status == "succeeded" and payment.status != PaymentStatus.succeeded:
        payment.status = PaymentStatus.succeeded
        payment.confirmed_at = datetime.now(timezone.utc)
        payment.event_source = "webhook_verified"
        db.commit()
        batch = db.get(UploadBatch, payment.batch_id)
        batch.status = BatchStatus.paid
        db.commit()
        track(db, event_name="payment_succeeded", batch_id=payment.batch_id, properties={"amount": payment.amount_value}, product_code=payment_product_code)
        _fulfil_paid_batch(db, batch)
    elif status_result.status in ("canceled", "failed"):
        payment.status = PaymentStatus.canceled if status_result.status == "canceled" else PaymentStatus.failed
        db.commit()
        track(db, event_name="payment_failed", batch_id=payment.batch_id, properties={"status": status_result.status}, product_code=payment_product_code)
    else:
        db.commit()

    return {"received": True, "duplicate": False}


@router.get("/payments/{payment_id}/status", response_model=PaymentOut)
def payment_status(payment_id: str, db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(404, "Платёж не найден.")
    payment_product_code = payment.product_code.value if hasattr(payment.product_code, "value") else (payment.product_code or "ARBITRPACK")
    return PaymentOut(payment_id=payment.id, product_code=payment_product_code, status=payment.status.value, confirmation_url=None, amount_value=payment.amount_value, currency=payment.currency)


@router.get("/batches/{batch_id}/job", response_model=JobStatusOut)
def get_job_status(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(UploadBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Загрузка не найдена.")
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.batch_id == batch_id, ProcessingJob.is_paid_run == True)  # noqa: E712
        .order_by(ProcessingJob.started_at.desc())
        .first()
    )
    if job is None:
        raise HTTPException(404, "Оплата ещё не подтверждена — обработка не запущена.")

    token = None
    expires_at = None
    if job.status == "done":
        settings = get_settings()
        token = issue_download_token(db, job_id=job.id, ttl_seconds=settings.download_token_ttl_seconds)
        expires_at = datetime.now(timezone.utc)

    job_product_code = job.product_code.value if hasattr(job.product_code, "value") else (job.product_code or "ARBITRPACK")
    return JobStatusOut(job_id=job.id, product_code=job_product_code, status=job.status, operations_performed=job.operations_performed or [], download_token=token, expires_at=expires_at)


# --- DEV-ONLY: эндпоинты для локальной симуляции mock-провайдера (недоступны, если ARBITRPACK_PAYMENT_PROVIDER=yookassa) ---


@router.post("/mock/{provider_payment_id}/confirm")
async def mock_confirm(provider_payment_id: str, request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if settings.payment_provider != "mock":
        raise HTTPException(403, "Mock-эндпоинты отключены в этом окружении.")
    MockPaymentProvider.simulate(provider_payment_id, "succeeded")
    fake_body = f'{{"provider_payment_id": "{provider_payment_id}", "status": "succeeded"}}'.encode()
    request._body = fake_body  # noqa: SLF001 — тестовый шорткат для повторного использования webhook-обработчика
    return await payments_webhook(request, db, MockPaymentProvider())


@router.post("/mock/{provider_payment_id}/cancel")
async def mock_cancel(provider_payment_id: str, request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if settings.payment_provider != "mock":
        raise HTTPException(403, "Mock-эндпоинты отключены в этом окружении.")
    MockPaymentProvider.simulate(provider_payment_id, "canceled")
    fake_body = f'{{"provider_payment_id": "{provider_payment_id}", "status": "canceled"}}'.encode()
    request._body = fake_body  # noqa: SLF001
    return await payments_webhook(request, db, MockPaymentProvider())
