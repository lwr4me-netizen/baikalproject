"""Сборка итогового ZIP-архива: безопасные имена, защита от zip-slip, детерминированный порядок,
применение безопасных авто-исправлений (снятие EXIF/метаданных) для платного прогона."""
from __future__ import annotations

import io
import zipfile

from app.products import DEFAULT_PRODUCT_CODE, get_product
from app.security import safe_filename
from app.services.diagnostics import FileDiagnostic
from app.validators.image_checks import strip_exif
from app.validators.pdf_checks import strip_pdf_metadata

MAX_UNCOMPRESSED_TOTAL_BYTES = 500 * 1024 * 1024  # защита от zip bomb на выходе


def build_archive(
    diagnostics: list[FileDiagnostic], *, apply_autofixes: bool, product_code: str = DEFAULT_PRODUCT_CODE
) -> tuple[bytes, list[str]]:
    """Возвращает (zip_bytes, список_операций_для_отчёта)."""
    product = get_product(product_code)
    operations: list[str] = []
    buf = io.BytesIO()

    # безопасная сортировка: по имени файла, детерминированно
    ordered = sorted(diagnostics, key=lambda d: d.safe_name.lower())

    used_names: set[str] = set()
    total_uncompressed = 0

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, d in enumerate(ordered, start=1):
            # пропускаем файлы с критической ошибкой — они не попадают в архив, это отражено в отчёте
            if any(i.severity == "critical" for i in d.issues):
                continue

            data = d.data
            ext = d.safe_name.rsplit(".", 1)[-1].lower() if "." in d.safe_name else ""

            if apply_autofixes:
                if ext == "pdf":
                    try:
                        data = strip_pdf_metadata(data)
                        operations.append(f'Удалены метаданные PDF: "{d.original_filename}"')
                    except Exception:
                        pass
                elif ext in ("jpg", "jpeg", "png"):
                    try:
                        pil_fmt = "JPEG" if ext in ("jpg", "jpeg") else "PNG"
                        data = strip_exif(data, pil_fmt)
                        operations.append(f'Удалён EXIF из изображения: "{d.original_filename}"')
                    except Exception:
                        pass

            # безопасное имя в архиве: нормализованное + префикс порядкового номера, без путей
            arcname = safe_filename(f"{idx:02d}_{d.safe_name}")
            arcname = arcname.replace("/", "_").replace("\\", "_").lstrip("/")
            if ".." in arcname:
                arcname = arcname.replace("..", "_")
            while arcname in used_names:
                arcname = f"dup_{arcname}"
            used_names.add(arcname)

            total_uncompressed += len(data)
            if total_uncompressed > MAX_UNCOMPRESSED_TOTAL_BYTES:
                raise ValueError("Суммарный размер архива превышает защитный лимит (возможная zip-bomb ситуация)")

            zf.writestr(arcname, data)

        manifest_lines = [f"{name}" for name in sorted(used_names)]
        zf.writestr("00_МАНИФЕСТ.txt", f"{product.archive_manifest_title}:\n" + "\n".join(manifest_lines))

    if apply_autofixes and not operations:
        operations.append("Автоматических исправлений не потребовалось.")

    return buf.getvalue(), operations
