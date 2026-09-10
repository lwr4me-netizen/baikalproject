import io

from tests.factories import (
    make_corrupted_pdf,
    make_encrypted_pdf,
    make_valid_jpeg,
    make_valid_pdf,
    make_valid_png,
)


def _upload(client, files, ttl_hours=72, consent=True):
    return client.post(
        "/api/upload",
        data={"consent_given": str(consent).lower(), "ttl_hours": ttl_hours},
        files=files,
    )


def test_free_diagnostics_for_valid_files(client):
    files = [
        ("files", ("Исковое заявление.pdf", make_valid_pdf(pages=2), "application/pdf")),
        ("files", ("Приложение.jpg", make_valid_jpeg(), "image/jpeg")),
    ]
    resp = _upload(client, files)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["file_count"] == 2
    assert "batch_id" in body


def test_upload_requires_consent(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    resp = _upload(client, files, consent=False)
    assert resp.status_code == 400


def test_encrypted_pdf_flagged_critical(client):
    files = [("files", ("secret.pdf", make_encrypted_pdf(), "application/pdf"))]
    resp = _upload(client, files)
    body = resp.json()
    assert body["critical_count"] >= 1
    assert "encrypted_pdf" in body["categories"]
    assert body["can_download_free"] is False


def test_corrupted_pdf_flagged_critical(client):
    files = [("files", ("broken.pdf", make_corrupted_pdf(), "application/pdf"))]
    resp = _upload(client, files)
    body = resp.json()
    assert "corrupted_file" in body["categories"]


def test_duplicate_files_flagged_as_warning(client):
    data = make_valid_pdf()
    files = [
        ("files", ("a.pdf", data, "application/pdf")),
        ("files", ("b.pdf", data, "application/pdf")),
    ]
    resp = _upload(client, files)
    body = resp.json()
    assert "duplicate_file" in body["categories"]
    assert body["warning_count"] >= 1


def test_mime_extension_mismatch_rejects_disguised_file(client):
    # реальный JPEG замаскированный под .pdf
    files = [("files", ("fake.pdf", make_valid_jpeg(), "application/octet-stream"))]
    resp = _upload(client, files)
    body = resp.json()
    assert "mime_extension_mismatch" in body["categories"]


def test_double_extension_rejected_end_to_end(client):
    files = [("files", ("invoice.pdf.exe", b"MZ" + b"0" * 40, "application/octet-stream"))]
    resp = _upload(client, files)
    body = resp.json()
    assert "double_extension" in body["categories"]


def test_diagnostics_can_be_refetched(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    resp = _upload(client, files)
    batch_id = resp.json()["batch_id"]
    resp2 = client.get(f"/api/batches/{batch_id}/diagnostics")
    assert resp2.status_code == 200
    assert resp2.json()["file_count"] == 1


def test_immediate_deletion_by_user(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    resp = _upload(client, files)
    batch_id = resp.json()["batch_id"]
    del_resp = client.post(f"/api/batches/{batch_id}/delete")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True
