import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.config import get_rules, get_settings
from app.db import get_db
from app.products import DEFAULT_PRODUCT_CODE, PRODUCTS, get_product
from app.rate_limit import limiter
from app.models import (
    BatchStatus,
    ConsentRecord,
    UploadBatch,
    UploadedFile,
    UserSession,
    ValidationResult,
)
from app.schemas import DiagnosticsOut, FileResultOut, IssueOut
from app.security import hash_ip, sha256_bytes
from app.services.analytics import audit, track
from app.services.diagnostics import diagnose_batch, summarize
from app.storage import get_storage

router = APIRouter(prefix="/api", tags=["upload"])

SESSION_COOKIE = "arbitrpack_sid"


def get_or_create_session(request: Request, response: Response, db: Session, sid: str | None) -> UserSession:
    if sid:
        existing = db.get(UserSession, sid)
        if existing is not None:
            existing.last_seen_at = datetime.now(timezone.utc)
            db.commit()
            return existing
    session = UserSession(
        utm_source=request.query_params.get("utm_source"),
        utm_medium=request.query_params.get("utm_medium"),
        utm_campaign=request.query_params.get("utm_campaign"),
    )
    db.add(session)
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        session.id,
        httponly=True,
        secure=get_settings().environment == "production",
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )
    return session


@router.post("/upload", response_model=DiagnosticsOut)
@limiter.limit(lambda: get_settings().rate_limit_uploads_per_hour)
async def upload_batch(
    request: Request,
    response: Response,
    files: list[UploadFile] = File(...),
    consent_given: bool = Form(...),
    ttl_hours: int = Form(72),
    # По умолчанию ARBITRPACK — старый frontend/тесты, не передающие product_code явно, не ломаются.
    product_code: str = Form(DEFAULT_PRODUCT_CODE),
    db: Session = Depends(get_db),
    arbitrpack_sid: str | None = Cookie(default=None),
):
    if product_code not in PRODUCTS:
        raise HTTPException(400, f"Неизвестный product_code. Допустимые значения: {sorted(PRODUCTS)}")

    if not consent_given:
        raise HTTPException(400, "Необходимо согласие на обработку файлов перед загрузкой.")

    rules = get_rules(product_code)
    if ttl_hours not in rules["ttl_options_hours"]:
        raise HTTPException(400, f"Недопустимый срок хранения. Разрешено: {rules['ttl_options_hours']}")
    if not files:
        raise HTTPException(400, "Не переданы файлы.")

    session = get_or_create_session(request, response, db, arbitrpack_sid)
    track(db, event_name="upload_started", session_id=session.id, product_code=product_code)

    batch = UploadBatch(
        session_id=session.id, product_code=product_code, status=BatchStatus.uploading, ttl_hours=ttl_hours
    )
    db.add(batch)
    db.flush()

    client_ip = request.client.host if request.client else "unknown"
    db.add(
        ConsentRecord(
            session_id=session.id,
            batch_id=batch.id,
            consent_text_version="2026-09-09",
            ip_hash=hash_ip(client_ip, get_settings().secret_key),
        )
    )

    raw_files: list[tuple[str, bytes]] = []
    for f in files:
        content = await f.read()
        raw_files.append((f.filename or "file", content))

    diagnostics, batch_issues = diagnose_batch(raw_files, product_code=product_code)
    summary = summarize(diagnostics, batch_issues)

    storage = get_storage()
    total_size = 0
    for d in diagnostics:
        storage_key = f"batches/{batch.id}/{sha256_bytes(d.original_filename.encode())[:8]}_{d.safe_name}"
        storage.put(storage_key, d.data, content_type=d.content_type)
        total_size += d.size_bytes
        uf = UploadedFile(
            batch_id=batch.id,
            original_filename=d.original_filename,
            safe_filename=d.safe_name,
            storage_key=storage_key,
            content_type=d.content_type,
            detected_mime=d.content_type,
            size_bytes=d.size_bytes,
            sha256=d.sha256,
            page_count=d.page_count,
        )
        db.add(uf)
        db.flush()
        for issue in d.issues:
            db.add(
                ValidationResult(
                    file_id=uf.id,
                    batch_id=batch.id,
                    rule_code=issue.rule_code,
                    severity=issue.severity,
                    message=issue.message,
                    auto_fixable=issue.auto_fixable,
                )
            )

    for issue in batch_issues:
        db.add(
            ValidationResult(
                file_id=None,
                batch_id=batch.id,
                rule_code=issue.rule_code,
                severity=issue.severity,
                message=issue.message,
                auto_fixable=issue.auto_fixable,
            )
        )

    batch.total_size_bytes = total_size
    batch.status = BatchStatus.diagnosed
    batch.expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    db.commit()

    audit(db, event_type="batch_uploaded", batch_id=batch.id, payload={"file_count": len(diagnostics)}, product_code=product_code)
    track(db, event_name="upload_completed", session_id=session.id, batch_id=batch.id, properties={"file_count": len(diagnostics)}, product_code=product_code)
    track(db, event_name="diagnostics_free_result_shown", session_id=session.id, batch_id=batch.id, properties=summary, product_code=product_code)

    file_results = [
        FileResultOut(
            original_filename=d.original_filename,
            size_bytes=d.size_bytes,
            page_count=d.page_count,
            issues=[IssueOut(rule_code=i.rule_code, severity=i.severity, message=i.message, auto_fixable=i.auto_fixable) for i in d.issues],
        )
        for d in diagnostics
    ]

    return DiagnosticsOut(
        batch_id=batch.id,
        product_code=product_code,
        can_download_free=(summary["critical_count"] == 0 and summary["warning_count"] == 0),
        files=file_results,
        **summary,
    )


@router.get("/batches/{batch_id}/diagnostics", response_model=DiagnosticsOut)
def get_diagnostics(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(UploadBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Загрузка не найдена или уже удалена.")
    files = db.query(UploadedFile).filter(UploadedFile.batch_id == batch_id).all()
    results = db.query(ValidationResult).filter(ValidationResult.batch_id == batch_id).all()

    by_file: dict[str | None, list[ValidationResult]] = {}
    for r in results:
        by_file.setdefault(r.file_id, []).append(r)

    file_results = [
        FileResultOut(
            original_filename=f.original_filename,
            size_bytes=f.size_bytes,
            page_count=f.page_count,
            issues=[IssueOut(rule_code=r.rule_code, severity=r.severity, message=r.message, auto_fixable=r.auto_fixable) for r in by_file.get(f.id, [])],
        )
        for f in files
    ]
    critical = sum(1 for r in results if r.severity == "critical")
    warning = sum(1 for r in results if r.severity == "warning")
    recommendation = sum(1 for r in results if r.severity == "recommendation")
    product_code = batch.product_code.value if hasattr(batch.product_code, "value") else batch.product_code
    return DiagnosticsOut(
        batch_id=batch.id,
        product_code=product_code,
        file_count=len(files),
        critical_count=critical,
        warning_count=warning,
        recommendation_count=recommendation,
        categories=sorted({r.rule_code for r in results}),
        files_needing_fix=sorted({f.original_filename for f in files if any(r.file_id == f.id and r.severity in ("critical", "warning") for r in results)}),
        auto_fixable_count=sum(1 for r in results if r.auto_fixable),
        files=file_results,
        can_download_free=(critical == 0 and warning == 0),
    )


@router.post("/batches/{batch_id}/delete")
def delete_batch_now(batch_id: str, db: Session = Depends(get_db)):
    """Пользовательская команда немедленного удаления данных (раздел 9 ТЗ)."""
    from app.services.ttl_cleanup import delete_batch_files

    batch = db.get(UploadBatch, batch_id)
    if batch is None:
        raise HTTPException(404, "Загрузка не найдена.")
    product_code = batch.product_code.value if hasattr(batch.product_code, "value") else batch.product_code
    delete_batch_files(db, batch)
    track(db, event_name="data_deleted", batch_id=batch_id, properties={"reason": "user_requested"}, product_code=product_code)
    return {"deleted": True}
