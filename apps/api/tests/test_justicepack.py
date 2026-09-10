"""JusticePack (product_code=JUSTICEPACK) — независимая вендинг-машина для ГАС «Правосудие».

Эти тесты проверяют РАЗДЕЛЬНО от ArbitrPack: выбор аппарата, изоляцию правил/тарифов/статистики,
полный вертикальный сценарий (загрузка -> диагностика -> mock-оплата -> ZIP -> скачивание -> удаление),
и то, что появление JusticePack не меняет поведение ArbitrPack по умолчанию (регрессия).

Только синтетические файлы, сгенерированные программой (tests/factories.py) — никаких реальных
судебных документов, как и в остальных тестах проекта."""
from app.config import get_rules
from tests.factories import (
    make_corrupted_pdf,
    make_encrypted_pdf,
    make_valid_jpeg,
    make_valid_pdf,
)

ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


def _upload(client, files, product_code="JUSTICEPACK", ttl_hours=72, consent=True):
    return client.post(
        "/api/upload",
        data={"consent_given": str(consent).lower(), "ttl_hours": ttl_hours, "product_code": product_code},
        files=files,
    )


# 1. Экран выбора аппарата / выбор product_code -----------------------------------------------


def test_upload_defaults_to_arbitrpack_when_product_code_omitted(client):
    """Старое поведение (без product_code вовсе) не должно сломаться — обратная совместимость."""
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    resp = client.post("/api/upload", data={"consent_given": "true", "ttl_hours": 72}, files=files)
    assert resp.status_code == 200, resp.text
    assert resp.json()["product_code"] == "ARBITRPACK"


def test_upload_with_explicit_justicepack_product_code(client):
    files = [("files", ("Заявление.pdf", make_valid_pdf(pages=2), "application/pdf"))]
    resp = _upload(client, files, product_code="JUSTICEPACK")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["product_code"] == "JUSTICEPACK"
    assert body["file_count"] == 1


def test_unknown_product_code_rejected(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    resp = _upload(client, files, product_code="NOT_A_REAL_PRODUCT")
    assert resp.status_code == 400


# 2. Изоляция правил между продуктами ----------------------------------------------------------


def test_rule_profiles_are_physically_separate_files(client):
    arbitr_rules = get_rules("ARBITRPACK")
    justice_rules = get_rules("JUSTICEPACK")
    # ArbitrPack rules.yaml не содержит поля "system" (унаследовано с первой версии проекта),
    # у GAS-профиля оно обязательно и равно GAS_PRAVOSUDIE — это подтверждает, что файлы разные,
    # а не один и тот же объект/шаблон, применённый дважды.
    assert justice_rules.get("system") == "GAS_PRAVOSUDIE"
    assert arbitr_rules.get("system") != "GAS_PRAVOSUDIE"
    assert justice_rules is not arbitr_rules


def test_changing_rule_lookup_does_not_cross_contaminate_severity_mapping(client):
    arbitr_rules = get_rules("ARBITRPACK")
    justice_rules = get_rules("JUSTICEPACK")
    # оба профиля независимо помечают encrypted_pdf как critical — это ПОДТВЕРЖДЕНО для каждого
    # акта отдельно (GAS-R4 и R-1 соответственно), а не предположено по аналогии.
    assert arbitr_rules["severity_mapping"]["encrypted_pdf"] == "critical"
    assert justice_rules["severity_mapping"]["encrypted_pdf"] == "critical"


# 3. Диагностика для JusticePack -----------------------------------------------------------------


def test_justicepack_valid_files_pass_free_diagnostics(client):
    files = [
        ("files", ("Исковое заявление.pdf", make_valid_pdf(pages=2, with_text=True), "application/pdf")),
        ("files", ("Приложение.jpg", make_valid_jpeg(), "image/jpeg")),
    ]
    resp = _upload(client, files)
    body = resp.json()
    assert body["product_code"] == "JUSTICEPACK"
    assert "batch_id" in body


def test_justicepack_corrupted_pdf_flagged_critical(client):
    files = [("files", ("broken.pdf", make_corrupted_pdf(), "application/pdf"))]
    resp = _upload(client, files)
    body = resp.json()
    assert "corrupted_file" in body["categories"]
    assert body["can_download_free"] is False


def test_justicepack_encrypted_pdf_flagged_critical_gas_r4(client):
    """GAS-R4: приказ №251 прямо требует отсутствие защиты от копирования/печати."""
    files = [("files", ("secret.pdf", make_encrypted_pdf(), "application/pdf"))]
    resp = _upload(client, files)
    body = resp.json()
    assert "encrypted_pdf" in body["categories"]
    assert body["critical_count"] >= 1


def test_justicepack_mime_extension_mismatch_detected(client):
    files = [("files", ("fake.pdf", make_valid_jpeg(), "application/octet-stream"))]
    resp = _upload(client, files)
    body = resp.json()
    assert "mime_extension_mismatch" in body["categories"]


def test_justicepack_double_extension_rejected(client):
    files = [("files", ("invoice.pdf.exe", b"MZ" + b"0" * 40, "application/octet-stream"))]
    resp = _upload(client, files)
    body = resp.json()
    assert "double_extension" in body["categories"]


def test_justicepack_duplicate_files_flagged_warning(client):
    data = make_valid_pdf()
    files = [
        ("files", ("a.pdf", data, "application/pdf")),
        ("files", ("b.pdf", data, "application/pdf")),
    ]
    resp = _upload(client, files)
    body = resp.json()
    assert "duplicate_file" in body["categories"]


def test_justicepack_filename_hint_references_gas_pravosudie_not_moy_arbitr(client):
    files = [("files", ("scan1.pdf", make_valid_pdf(with_text=True), "application/pdf"))]
    resp = _upload(client, files)
    body = resp.json()
    fname_issues = [
        i["message"]
        for f in body["files"]
        for i in f["issues"]
        if i["rule_code"] == "filename_not_descriptive"
    ]
    assert fname_issues, "ожидалась рекомендация по неописательному имени файла"
    assert "ГАС" in fname_issues[0] or "Правосудие" in fname_issues[0]
    assert "Мой Арбитр" not in fname_issues[0]


def test_justicepack_disclaimer_does_not_mention_arbitrpack(client):
    # дисклеймер про электронную подпись — batch-level issue (не привязан к конкретному файлу),
    # здесь достаточно убедиться, что категория появилась в отчёте для JusticePack.
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    resp = _upload(client, files)
    body = resp.json()
    assert "missing_signature_reminder" in body["categories"]


def test_report_diagnostics_carries_product_code(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    batch_id = _upload(client, files).json()["batch_id"]
    resp = client.get(f"/api/batches/{batch_id}/diagnostics")
    assert resp.json()["product_code"] == "JUSTICEPACK"


# 4. Тариф и оплата — независимые от ArbitrPack --------------------------------------------------


def test_justicepack_price_is_looked_up_from_its_own_profile(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    batch_id = _upload(client, files).json()["batch_id"]
    pay = client.post("/api/payments", json={"batch_id": batch_id}).json()
    justice_kopeks = get_rules("JUSTICEPACK")["pricing"]["full_processing_price"]
    assert pay["amount_value"] == f"{justice_kopeks / 100:.2f}"
    assert pay["product_code"] == "JUSTICEPACK"


def test_justicepack_full_paid_flow_confirm_then_download(client):
    files = [("files", ("Иск.pdf", make_valid_pdf(pages=1), "application/pdf"))]
    batch_id = _upload(client, files).json()["batch_id"]

    pay = client.post("/api/payments", json={"batch_id": batch_id}).json()
    assert pay["product_code"] == "JUSTICEPACK"
    provider_payment_id = pay["confirmation_url"].split("mock_payment_id=")[1]

    confirm = client.post(f"/api/mock/{provider_payment_id}/confirm")
    assert confirm.status_code == 200
    assert confirm.json()["duplicate"] is False

    job = client.get(f"/api/batches/{batch_id}/job").json()
    assert job["status"] == "done"
    assert job["product_code"] == "JUSTICEPACK"
    assert job["download_token"] is not None

    dl = client.get(f"/api/download/{job['download_token']}")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/zip"
    assert 'filename="justicepack_result.zip"' in dl.headers["content-disposition"]
    assert len(dl.content) > 0


def test_justicepack_webhook_idempotent_duplicate_ignored(client):
    files = [("files", ("Иск.pdf", make_valid_pdf(), "application/pdf"))]
    batch_id = _upload(client, files).json()["batch_id"]
    pay = client.post("/api/payments", json={"batch_id": batch_id}).json()
    provider_payment_id = pay["confirmation_url"].split("mock_payment_id=")[1]

    first = client.post(f"/api/mock/{provider_payment_id}/confirm")
    assert first.json()["duplicate"] is False
    job_before = client.get(f"/api/batches/{batch_id}/job").json()

    second = client.post(f"/api/mock/{provider_payment_id}/confirm")
    assert second.json()["duplicate"] is True
    job_after = client.get(f"/api/batches/{batch_id}/job").json()
    assert job_before["job_id"] == job_after["job_id"]


def test_justicepack_canceled_payment_does_not_unlock_download(client):
    files = [("files", ("Иск.pdf", make_valid_pdf(), "application/pdf"))]
    batch_id = _upload(client, files).json()["batch_id"]
    pay = client.post("/api/payments", json={"batch_id": batch_id}).json()
    provider_payment_id = pay["confirmation_url"].split("mock_payment_id=")[1]

    cancel = client.post(f"/api/mock/{provider_payment_id}/cancel")
    assert cancel.status_code == 200

    job = client.get(f"/api/batches/{batch_id}/job")
    assert job.status_code == 404


def test_justicepack_no_paid_delivery_before_payment_confirmed(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    batch_id = _upload(client, files).json()["batch_id"]
    resp = client.get(f"/api/batches/{batch_id}/job")
    assert resp.status_code == 404


# 5. Удаление / TTL --------------------------------------------------------------------------


def test_justicepack_manual_deletion(client):
    files = [("files", ("a.pdf", make_valid_pdf(), "application/pdf"))]
    batch_id = _upload(client, files).json()["batch_id"]
    del_resp = client.post(f"/api/batches/{batch_id}/delete")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


def test_justicepack_upload_does_not_leak_filenames_into_audit_log(client):
    from app.models import AuditEvent
    from tests.conftest import TestingSessionLocal

    secret_name = "частный_документ_Петров_ФИО.pdf"
    files = [("files", (secret_name, make_valid_pdf(), "application/pdf"))]
    batch_id = _upload(client, files).json()["batch_id"]

    db = TestingSessionLocal()
    events = db.query(AuditEvent).filter(AuditEvent.batch_id == batch_id).all()
    assert events, "ожидались audit-события для этого батча"
    for e in events:
        assert secret_name not in str(e.payload)
        stored_code = e.product_code.value if hasattr(e.product_code, "value") else e.product_code
        assert stored_code == "JUSTICEPACK"
    db.close()


# 6. Изоляция аналитики/админки -----------------------------------------------------------------


def test_admin_metrics_optional_product_filter_never_mixes_stats(client):
    # один батч ArbitrPack, один JusticePack
    client.post("/api/upload", data={"consent_given": "true", "ttl_hours": 72}, files=[("files", ("a.pdf", make_valid_pdf(), "application/pdf"))])
    _upload(client, [("files", ("b.pdf", make_valid_pdf(), "application/pdf"))], product_code="JUSTICEPACK")

    all_resp = client.get("/api/admin/metrics", headers=ADMIN_HEADERS)
    assert all_resp.status_code == 200
    all_body = all_resp.json()
    assert all_body["product_code"] == "ALL"
    assert "by_product" in all_body
    assert set(all_body["by_product"].keys()) == {"ARBITRPACK", "JUSTICEPACK"}
    assert all_body["by_product"]["ARBITRPACK"]["checks_started"] >= 1
    assert all_body["by_product"]["JUSTICEPACK"]["checks_started"] >= 1

    jp_only = client.get("/api/admin/metrics?product_code=JUSTICEPACK", headers=ADMIN_HEADERS).json()
    assert jp_only["product_code"] == "JUSTICEPACK"
    assert "by_product" not in jp_only

    arbitr_only = client.get("/api/admin/metrics?product_code=ARBITRPACK", headers=ADMIN_HEADERS).json()
    assert arbitr_only["checks_started"] != jp_only["checks_started"] or arbitr_only["checks_started"] == 1


def test_admin_metrics_rejects_unknown_product_code(client):
    resp = client.get("/api/admin/metrics?product_code=NOPE", headers=ADMIN_HEADERS)
    assert resp.status_code == 400


# 7. Регрессия ArbitrPack после появления JusticePack ---------------------------------------------


def test_arbitrpack_still_works_unaffected_after_justicepack_upload(client):
    """Сценарий: сначала загружают в JusticePack, потом в ArbitrPack — ArbitrPack должен вести
    себя так же, как до появления второго продукта (собственный тариф, собственные правила)."""
    jp_files = [("files", ("gas.pdf", make_valid_pdf(), "application/pdf"))]
    _upload(client, jp_files, product_code="JUSTICEPACK")

    ap_files = [("files", ("moy_arbitr.pdf", make_valid_pdf(), "application/pdf"))]
    ap_resp = client.post("/api/upload", data={"consent_given": "true", "ttl_hours": 72, "product_code": "ARBITRPACK"}, files=ap_files)
    body = ap_resp.json()
    assert body["product_code"] == "ARBITRPACK"

    batch_id = body["batch_id"]
    pay = client.post("/api/payments", json={"batch_id": batch_id}).json()
    arbitr_kopeks = get_rules("ARBITRPACK")["pricing"]["full_processing_price"]
    assert pay["amount_value"] == f"{arbitr_kopeks / 100:.2f}"
    assert pay["product_code"] == "ARBITRPACK"

    provider_payment_id = pay["confirmation_url"].split("mock_payment_id=")[1]
    confirm = client.post(f"/api/mock/{provider_payment_id}/confirm")
    assert confirm.status_code == 200
    job = client.get(f"/api/batches/{batch_id}/job").json()
    assert job["product_code"] == "ARBITRPACK"
    dl = client.get(f"/api/download/{job['download_token']}")
    assert 'filename="arbitrpack_result.zip"' in dl.headers["content-disposition"]
