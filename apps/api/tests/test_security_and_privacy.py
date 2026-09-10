import io
import logging

from tests.factories import make_valid_pdf


def test_logs_do_not_contain_filenames(client, capsys):
    """Структурированные логи (structlog) не должны содержать оригинальных имён файлов."""
    secret_name = "СОВЕРШЕННО_СЕКРЕТНОЕ_ИМЯ_ФАЙЛА_xyz123.pdf"
    files = [("files", (secret_name, make_valid_pdf(), "application/pdf"))]
    resp = client.post("/api/upload", data={"consent_given": "true", "ttl_hours": 72}, files=files)
    assert resp.status_code == 200

    captured = capsys.readouterr()
    assert secret_name not in captured.out
    assert secret_name not in captured.err


def test_audit_events_never_store_filenames(client):
    from app.models import AuditEvent
    from tests.conftest import TestingSessionLocal

    secret_name = "приватный_документ_ФИО_Иванов.pdf"
    files = [("files", (secret_name, make_valid_pdf(), "application/pdf"))]
    resp = client.post("/api/upload", data={"consent_given": "true", "ttl_hours": 72}, files=files)
    batch_id = resp.json()["batch_id"]

    db = TestingSessionLocal()
    events = db.query(AuditEvent).filter(AuditEvent.batch_id == batch_id).all()
    for e in events:
        assert secret_name not in str(e.payload)
    db.close()


def test_report_contains_signature_disclaimer(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    resp = client.post("/api/upload", data={"consent_given": "true", "ttl_hours": 72}, files=files)
    body = resp.json()
    assert "missing_signature_reminder" in body["categories"]


def test_admin_metrics_require_token(client):
    resp = client.get("/api/admin/metrics")
    assert resp.status_code == 401


def test_admin_metrics_accessible_with_token(client):
    resp = client.get("/api/admin/metrics", headers={"Authorization": "Bearer test-admin-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert "conversion_to_payment" in body


def test_security_headers_present(client):
    resp = client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"


def test_invalid_ttl_choice_rejected(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    resp = client.post("/api/upload", data={"consent_given": "true", "ttl_hours": 999999}, files=files)
    assert resp.status_code == 400
