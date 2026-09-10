import io
import zipfile
from datetime import datetime, timedelta, timezone

from PIL import Image

from app.config import get_settings
from app.models import BatchStatus, UploadBatch, UserSession
from app.services.archive import build_archive
from app.services.diagnostics import FileDiagnostic
from app.services.ttl_cleanup import sweep_expired_batches
from app.services.tokens import issue_download_token
from app.storage import get_storage
from app.validators.file_checks import Issue
from app.validators.image_checks import strip_exif
from tests.factories import make_jpeg_with_exif_orientation, make_valid_jpeg, make_valid_pdf


def test_archive_excludes_critical_files_and_has_manifest():
    good = FileDiagnostic(
        original_filename="ok.pdf",
        safe_name="ok.pdf",
        size_bytes=10,
        sha256="a" * 64,
        content_type="application/pdf",
        page_count=1,
        issues=[],
        data=make_valid_pdf(),
    )
    bad = FileDiagnostic(
        original_filename="broken.pdf",
        safe_name="broken.pdf",
        size_bytes=5,
        sha256="b" * 64,
        content_type="application/pdf",
        page_count=None,
        issues=[Issue("corrupted_file", "critical", "broken")],
        data=b"garbage",
    )
    archive_bytes, ops = build_archive([good, bad], apply_autofixes=True)
    zf = zipfile.ZipFile(io.BytesIO(archive_bytes))
    names = zf.namelist()
    assert any("ok.pdf" in n for n in names)
    assert not any("broken.pdf" in n for n in names)
    assert "00_МАНИФЕСТ.txt" in names


def test_archive_arcnames_never_contain_path_traversal():
    """Защита от zip-slip: даже если исходное имя содержит '../', в архиве не должно быть путей вовне."""
    evil = FileDiagnostic(
        original_filename="../../etc/passwd.pdf",
        safe_name="../../etc/passwd.pdf",  # намеренно не нормализовано до вызова archive, чтобы проверить защиту на этом слое
        size_bytes=10,
        sha256="c" * 64,
        content_type="application/pdf",
        page_count=1,
        issues=[],
        data=make_valid_pdf(),
    )
    archive_bytes, _ = build_archive([evil], apply_autofixes=False)
    zf = zipfile.ZipFile(io.BytesIO(archive_bytes))
    for name in zf.namelist():
        assert not name.startswith("/")
        assert ".." not in name


def test_archive_autofix_strips_pdf_metadata_and_exif():
    pdf_diag = FileDiagnostic(
        original_filename="a.pdf",
        safe_name="a.pdf",
        size_bytes=1,
        sha256="d" * 64,
        content_type="application/pdf",
        page_count=1,
        issues=[],
        data=make_valid_pdf(),
    )
    archive_bytes, ops = build_archive([pdf_diag], apply_autofixes=True)
    assert any("метаданные" in op.lower() for op in ops)


def test_strip_exif_physically_rotates_before_dropping_orientation_tag():
    """Регрессия launch-readiness аудита: strip_exif() раньше удаляла EXIF (включая тег Orientation),
    НЕ повернув пиксели физически — скан, снятый телефоном в портретной ориентации (тег Orientation=6),
    оказывался в итоговом архиве развёрнутым боком, и подсказка для просмотрщика уже была стёрта."""
    raw = make_jpeg_with_exif_orientation(orientation=6, width=200, height=100)
    raw_img = Image.open(io.BytesIO(raw))
    assert raw_img.size == (200, 100)
    assert raw_img.getexif().get(274) == 6

    fixed_bytes = strip_exif(raw, "JPEG")
    fixed_img = Image.open(io.BytesIO(fixed_bytes))
    # после фикса пиксели должны быть физически повёрнуты в "правильную" сторону (портрет), а не остаться landscape
    assert fixed_img.size == (100, 200)
    # EXIF по-прежнему удалён (это и есть цель функции — не оставлять метаданные устройства/геолокацию)
    assert not fixed_img.getexif()


def test_archive_autofix_preserves_visual_orientation_of_rotated_photo():
    """То же самое, но через полный путь build_archive() (как выполняется в реальном платном прогоне)."""
    photo = FileDiagnostic(
        original_filename="scan.jpg",
        safe_name="scan.jpg",
        size_bytes=1,
        sha256="f" * 64,
        content_type="image/jpeg",
        page_count=None,
        issues=[],
        data=make_jpeg_with_exif_orientation(orientation=6, width=200, height=100),
    )
    archive_bytes, ops = build_archive([photo], apply_autofixes=True)
    zf = zipfile.ZipFile(io.BytesIO(archive_bytes))
    jpg_name = next(n for n in zf.namelist() if n.endswith(".jpg"))
    result_img = Image.open(io.BytesIO(zf.read(jpg_name)))
    assert result_img.size == (100, 200)
    assert any("exif" in op.lower() for op in ops)


def test_download_link_rejected_after_expiry(client):
    """Регрессия launch-readiness аудита: ветка истечения download-токена (app/routers/download.py,
    app/services/tokens.py::resolve_download_token) была на 0% покрытия — добавлен явный тест."""
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    # ttl_seconds отрицательный => токен уже "истёк" в момент выдачи
    token = issue_download_token(db, job_id="fake-job-id-not-used", ttl_seconds=-10)
    db.close()

    resp = client.get(f"/api/download/{token}")
    assert resp.status_code == 410


def test_ttl_cleanup_removes_expired_files(client, db_session=None):
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    session = UserSession()
    db.add(session)
    db.flush()

    batch = UploadBatch(
        session_id=session.id,
        status=BatchStatus.ready,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # уже истёк
    )
    db.add(batch)
    db.commit()

    storage = get_storage()
    storage.put(f"batches/{batch.id}/dummy.pdf", b"hello", content_type="application/pdf")

    from app.models import UploadedFile

    db.add(
        UploadedFile(
            batch_id=batch.id,
            original_filename="dummy.pdf",
            safe_filename="dummy.pdf",
            storage_key=f"batches/{batch.id}/dummy.pdf",
            content_type="application/pdf",
            size_bytes=5,
            sha256="e" * 64,
        )
    )
    db.commit()

    deleted_ids = sweep_expired_batches(db)
    assert batch.id in deleted_ids
    assert storage.exists(f"batches/{batch.id}/dummy.pdf") is False

    refreshed = db.get(UploadBatch, batch.id)
    assert refreshed.status == BatchStatus.deleted
    db.close()


def test_active_batch_not_removed_by_ttl_sweep():
    from tests.conftest import TestingSessionLocal

    db = TestingSessionLocal()
    session = UserSession()
    db.add(session)
    db.flush()
    batch = UploadBatch(
        session_id=session.id,
        status=BatchStatus.diagnosed,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=10),
    )
    db.add(batch)
    db.commit()

    deleted_ids = sweep_expired_batches(db)
    assert batch.id not in deleted_ids
    db.close()
