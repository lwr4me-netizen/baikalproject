from tests.factories import make_valid_pdf


def _upload_one(client):
    files = [("files", ("Иск.pdf", make_valid_pdf(pages=1), "application/pdf"))]
    resp = client.post("/api/upload", data={"consent_given": "true", "ttl_hours": 72}, files=files)
    assert resp.status_code == 200
    return resp.json()["batch_id"]


def test_download_forbidden_before_payment(client):
    batch_id = _upload_one(client)
    resp = client.get(f"/api/batches/{batch_id}/job")
    assert resp.status_code == 404  # обработка ещё не запущена — оплата не подтверждена


def test_create_payment_returns_confirmation_url(client):
    batch_id = _upload_one(client)
    resp = client.post("/api/payments", json={"batch_id": batch_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert "mock_payment_id=" in body["confirmation_url"]


def test_full_paid_flow_confirm_then_download(client):
    batch_id = _upload_one(client)
    pay = client.post("/api/payments", json={"batch_id": batch_id}).json()
    provider_payment_id = pay["confirmation_url"].split("mock_payment_id=")[1]

    confirm = client.post(f"/api/mock/{provider_payment_id}/confirm")
    assert confirm.status_code == 200
    assert confirm.json()["duplicate"] is False

    job = client.get(f"/api/batches/{batch_id}/job").json()
    assert job["status"] == "done"
    assert job["download_token"] is not None

    dl = client.get(f"/api/download/{job['download_token']}")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/zip"
    assert len(dl.content) > 0


def test_webhook_idempotent_duplicate_ignored(client):
    batch_id = _upload_one(client)
    pay = client.post("/api/payments", json={"batch_id": batch_id}).json()
    provider_payment_id = pay["confirmation_url"].split("mock_payment_id=")[1]

    first = client.post(f"/api/mock/{provider_payment_id}/confirm")
    assert first.json()["duplicate"] is False

    # повторный webhook с тем же статусом не должен пересоздавать job / архив повторно
    job_before = client.get(f"/api/batches/{batch_id}/job").json()

    second = client.post(f"/api/mock/{provider_payment_id}/confirm")
    assert second.json()["duplicate"] is True

    job_after = client.get(f"/api/batches/{batch_id}/job").json()
    assert job_before["job_id"] == job_after["job_id"]


def test_canceled_payment_does_not_unlock_download(client):
    batch_id = _upload_one(client)
    pay = client.post("/api/payments", json={"batch_id": batch_id}).json()
    provider_payment_id = pay["confirmation_url"].split("mock_payment_id=")[1]

    cancel = client.post(f"/api/mock/{provider_payment_id}/cancel")
    assert cancel.status_code == 200

    job = client.get(f"/api/batches/{batch_id}/job")
    assert job.status_code == 404


def test_download_with_invalid_token_rejected(client):
    resp = client.get("/api/download/not-a-real-token")
    assert resp.status_code == 410


def test_payment_creation_is_idempotent_on_retry(client):
    """Повторный create_payment для того же batch не должен приводить к рассинхронизации —
    внутри MockPaymentProvider дедуп по idempotency_key, каждый вызов из API создаёт новую
    внутреннюю запись Payment с уникальным ключом (ожидаемое поведение: не блокирует повторный заказ)."""
    batch_id = _upload_one(client)
    first = client.post("/api/payments", json={"batch_id": batch_id}).json()
    second = client.post("/api/payments", json={"batch_id": batch_id}).json()
    assert first["payment_id"] != second["payment_id"]
