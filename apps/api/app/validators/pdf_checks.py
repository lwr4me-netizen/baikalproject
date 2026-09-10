"""Диагностика PDF: повреждённость, шифрование, число страниц, эвристика пустых страниц."""
from __future__ import annotations

import io
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.validators.file_checks import Issue


@dataclass
class PdfInfo:
    ok: bool
    encrypted: bool = False
    page_count: int | None = None
    possibly_blank_pages: list[int] | None = None
    issues: list[Issue] | None = None


def inspect_pdf(data: bytes, filename: str = "") -> PdfInfo:
    issues: list[Issue] = []
    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, Exception) as exc:  # pypdf может кидать разные исключения на мусорных файлах
        issues.append(
            Issue(
                "corrupted_file",
                "critical",
                f'Файл "{filename}" повреждён или не является корректным PDF ({exc.__class__.__name__}).',
            )
        )
        return PdfInfo(ok=False, issues=issues)

    if reader.is_encrypted:
        # пробуем открыть пустым паролем — некоторые PDF помечены encrypted, но без реального пароля
        try:
            reader.decrypt("")
        except Exception:
            pass
    if reader.is_encrypted:
        issues.append(
            Issue(
                "encrypted_pdf",
                "critical",
                f'Файл "{filename}" защищён паролем. Снимите защиту перед подачей — суд не сможет открыть зашифрованный документ.',
            )
        )
        return PdfInfo(ok=False, encrypted=True, issues=issues)

    try:
        page_count = len(reader.pages)
    except Exception as exc:
        issues.append(
            Issue(
                "corrupted_file",
                "critical",
                f'Не удалось прочитать структуру страниц файла "{filename}" ({exc.__class__.__name__}).',
            )
        )
        return PdfInfo(ok=False, issues=issues)

    possibly_blank: list[int] = []
    for idx, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            text = ""
        has_images = bool(page.images) if hasattr(page, "images") else False
        if not text and not has_images:
            possibly_blank.append(idx)

    if possibly_blank:
        pages_str = ", ".join(str(p) for p in possibly_blank)
        issues.append(
            Issue(
                "possibly_blank_page",
                "warning",
                f'Файл "{filename}": возможно пустые страницы ({pages_str}). Проверьте перед подачей.',
            )
        )

    return PdfInfo(ok=True, encrypted=False, page_count=page_count, possibly_blank_pages=possibly_blank, issues=issues)


def strip_pdf_metadata(data: bytes) -> bytes:
    """Безопасное авто-исправление: удаление метаданных документа (автор, программа-создатель и т.п.)."""
    from pypdf import PdfWriter

    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
