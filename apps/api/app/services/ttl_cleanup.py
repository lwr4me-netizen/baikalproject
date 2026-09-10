"""Логика удаления файлов по TTL и по запросу пользователя. Отдельный аудит удаления —
каждое удаление пишет AuditEvent, но никогда не пишет имена файлов или их содержимое."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AuditEvent, BatchStatus, DownloadToken, ProcessingJob, UploadBatch, UploadedFile
from app.storage import get_storage


def delete_batch_files(db: Session, batch: UploadBatch) -> int:
    """Удаляет все объекты хранилища, связанные с батчем (исходники + готовые архивы),
    помечает батч как deleted. Возвращает количество удалённых объектов."""
    storage = get_storage()
    deleted = 0

    files = db.query(UploadedFile).filter(UploadedFile.batch_id == batch.id).all()
    for f in files:
        try:
            if storage.exists(f.storage_key):
                storage.delete(f.storage_key)
                deleted += 1
        except Exception:
            pass

    jobs = db.query(ProcessingJob).filter(ProcessingJob.batch_id == batch.id).all()
    for job in jobs:
        if job.archive_storage_key:
            try:
                if storage.exists(job.archive_storage_key):
                    storage.delete(job.archive_storage_key)
                    deleted += 1
            except Exception:
                pass

    batch.status = BatchStatus.deleted
    batch.deleted_at = datetime.now(timezone.utc)
    # product_code берём из самого батча, а не из умолчания — иначе удаление JusticePack-батчей
    # всегда попадало бы в audit_events как ARBITRPACK (найдено в launch-readiness аудите).
    batch_product_code = batch.product_code.value if hasattr(batch.product_code, "value") else (batch.product_code or "ARBITRPACK")
    db.add(
        AuditEvent(
            batch_id=batch.id,
            product_code=batch_product_code,
            event_type="files_deleted",
            payload={"deleted_object_count": deleted, "reason": "ttl_or_manual"},
        )
    )
    db.commit()
    return deleted


def sweep_expired_batches(db: Session) -> list[str]:
    """Находит и удаляет все батчи с истёкшим TTL. Возвращает список id удалённых батчей."""
    now = datetime.now(timezone.utc)
    expired = (
        db.query(UploadBatch)
        .filter(UploadBatch.expires_at.isnot(None))
        .filter(UploadBatch.expires_at < now)
        .filter(UploadBatch.status != BatchStatus.deleted)
        .all()
    )
    deleted_ids = []
    for batch in expired:
        delete_batch_files(db, batch)
        deleted_ids.append(batch.id)
    return deleted_ids
