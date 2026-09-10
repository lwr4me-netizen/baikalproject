from app.config import get_rules
from app.security import has_double_extension, safe_filename
from app.validators.file_checks import check_batch_totals, check_file
from app.validators.image_checks import inspect_image
from app.validators.pdf_checks import inspect_pdf
from tests.factories import (
    make_corrupted_image,
    make_corrupted_pdf,
    make_encrypted_pdf,
    make_low_dpi_jpeg,
    make_oversized_blob,
    make_valid_jpeg,
    make_valid_pdf,
    make_valid_png,
)


def test_allowed_extensions_accepted():
    issues = check_file(filename="doc.pdf", data=make_valid_pdf())
    assert not any(i.rule_code == "disallowed_extension" for i in issues)


def test_disallowed_extension_rejected():
    issues = check_file(filename="malware.exe", data=b"MZ" + b"0" * 100)
    codes = [i.rule_code for i in issues]
    assert "disallowed_extension" in codes
    assert issues[0].severity == "critical"


def test_double_extension_rejected():
    assert has_double_extension("document.pdf.exe")
    issues = check_file(filename="document.pdf.exe", data=b"anything")
    assert issues[0].rule_code == "double_extension"
    assert issues[0].severity == "critical"


def test_oversized_file_rejected():
    rules = get_rules()["files"]
    blob = make_oversized_blob(rules["max_file_size_mb"] + 1)
    issues = check_file(filename="huge.pdf", data=blob)
    assert any(i.rule_code == "oversized_file" for i in issues)


def test_batch_total_size_rejected():
    rules = get_rules()["files"]
    total = (rules["max_batch_size_mb"] + 1) * 1024 * 1024
    issues = check_batch_totals(total_size_bytes=total, file_count=2)
    assert any(i.rule_code == "batch_too_large" for i in issues)


def test_too_many_files_rejected():
    rules = get_rules()["files"]
    issues = check_batch_totals(total_size_bytes=100, file_count=rules["max_files_per_batch"] + 1)
    assert any(i.rule_code == "batch_too_large" for i in issues)


def test_mime_extension_mismatch_detected():
    # реальный JPEG, но с расширением .pdf — подмена типа файла
    issues = check_file(filename="fake.pdf", data=make_valid_jpeg())
    assert any(i.rule_code == "mime_extension_mismatch" for i in issues)


def test_corrupted_pdf_detected():
    info = inspect_pdf(make_corrupted_pdf(), "broken.pdf")
    assert info.ok is False
    assert any(i.rule_code == "corrupted_file" for i in info.issues)


def test_encrypted_pdf_detected():
    info = inspect_pdf(make_encrypted_pdf(), "secret.pdf")
    assert info.ok is False
    assert info.encrypted is True
    assert any(i.rule_code == "encrypted_pdf" for i in info.issues)


def test_valid_pdf_page_count():
    info = inspect_pdf(make_valid_pdf(pages=3), "ok.pdf")
    assert info.ok is True
    assert info.page_count == 3


def test_blank_pdf_flagged_as_possibly_blank():
    info = inspect_pdf(make_valid_pdf(pages=1), "blank.pdf")
    assert info.possibly_blank_pages == [1]
    assert any(i.rule_code == "possibly_blank_page" and i.severity == "warning" for i in info.issues)


def test_corrupted_image_detected():
    info = inspect_image(make_corrupted_image(), "broken.jpg")
    assert info.ok is False
    assert any(i.rule_code == "corrupted_file" for i in info.issues)


def test_valid_image_ok():
    info = inspect_image(make_valid_jpeg(), "scan.jpg")
    assert info.ok is True
    assert info.width == 800


def test_low_effective_dpi_flags_recommendation():
    info = inspect_image(make_low_dpi_jpeg(), "lowres.jpg")
    assert any(i.rule_code == "low_scan_quality" and i.severity == "warning" for i in info.issues)


def test_safe_filename_normalization():
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("отчёт (копия).pdf") == "отчёт (копия).pdf"
    dangerous = safe_filename('bad<>:"|?*name.pdf')
    assert not any(c in dangerous for c in '<>:"|?*')


def test_safe_filename_handles_long_names():
    long_name = ("a" * 300) + ".pdf"
    result = safe_filename(long_name)
    assert len(result) <= 180
    assert result.endswith(".pdf")
