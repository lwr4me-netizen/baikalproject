from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ProcessingJob
from app.products import get_product
from app.services.analytics import track
from app.services.tokens import resolve_download_token
from app.storage import get_storage

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/download/{token}")
def download_archive(token: str, db: Session = Depends(get_db)):
    record = resolve_download_token(db, token)
    if record is None:
        raise HTTPException(410, "Ссылка на скачивание недействительна или истекла.")

    job = db.get(ProcessingJob, record.job_id)
    if job is None or job.status != "done" or not job.archive_storage_key:
        raise HTTPException(404, "Архив ещё не готов.")

    storage = get_storage()
    if not storage.exists(job.archive_storage_key):
        raise HTTPException(410, "Файлы уже удалены (истёк срок хранения).")

    job_product_code = job.product_code.value if hasattr(job.product_code, "value") else (job.product_code or "ARBITRPACK")
    product = get_product(job_product_code)

    data = storage.get(job.archive_storage_key)
    record.used_count += 1
    db.commit()
    track(db, event_name="archive_downloaded", batch_id=job.batch_id, product_code=job_product_code)

    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{product.archive_filename_prefix}_result.zip"'},
    )
