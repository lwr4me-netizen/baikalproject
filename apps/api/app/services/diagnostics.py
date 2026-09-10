"""Оркестрация диагностики: прогоняет каждый файл через проверки, находит дубликаты по SHA-256
внутри батча, формирует итоговый список ValidationResult (в памяти, ORM-объекты создаёт вызывающий код)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.products import DEFAULT_PRODUCT_CODE, get_product
from app.security import safe_filename, sha256_bytes
from app.validators.file_checks import Issue, check_batch_totals, check_file
from app.validators.image_checks import inspect_image
from app.validators.pdf_checks import inspect_pdf


@dataclass
class FileDiagnostic:
    original_filename: str
    safe_name: str
    size_bytes: int
    sha256: str
    content_type: str
    page_count: int | None
    issues: list[Issue] = field(default_factory=list)
    data: bytes = b""  # держим в памяти только на время обработки запроса, не логируется


def diagnose_batch(
    files: list[tuple[str, bytes]], product_code: str = DEFAULT_PRODUCT_CODE
) -> tuple[list[FileDiagnostic], list[Issue]]:
    """files: список (original_filename, raw_bytes). Возвращает (диагностика по файлам, проблемы уровня батча).
    product_code выбирает профиль правил (ARBITRPACK по умолчанию — обратная совместимость)."""
    product = get_product(product_code)
    diagnostics: list[FileDiagnostic] = []
    seen_hashes: dict[str, str] = {}  # sha256 -> первое имя файла с этим хэшем
    batch_issues: list[Issue] = []

    total_size = sum(len(d) for _, d in files)
    batch_issues.extend(
        check_batch_totals(total_size_bytes=total_size, file_count=len(files), product_code=product_code)
    )

    for original_name, data in files:
        issues = check_file(filename=original_name, data=data, product_code=product_code)
        ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
        page_count = None
        content_type = f"application/{ext}" if ext else "application/octet-stream"

        # если базовая проверка уже провалилась критически (повреждённое расширение/mime и т.п.),
        # глубокую проверку содержимого всё равно пробуем, если формат распознаваем — это не вредит.
        has_blocking_critical = any(i.severity == "critical" for i in issues)

        if ext == "pdf" and not has_blocking_critical:
            pdf_info = inspect_pdf(data, original_name)
            issues.extend(pdf_info.issues or [])
            page_count = pdf_info.page_count
            content_type = "application/pdf"
        elif ext in ("jpg", "jpeg", "png") and not has_blocking_critical:
            img_info = inspect_image(data, original_name, product_code=product_code)
            issues.extend(img_info.issues or [])
            content_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"

        digest = sha256_bytes(data)
        if digest in seen_hashes:
            issues.append(
                Issue(
                    "duplicate_file",
                    "warning",
                    f'Файл "{original_name}" дублирует ранее загруженный файл "{seen_hashes[digest]}" (идентичное содержимое).',
                )
            )
        else:
            seen_hashes[digest] = original_name

        safe_name = safe_filename(original_name)
        if safe_name == original_name and "." in original_name:
            # эвристика "неописательного имени" — короткие технические имена вроде IMG_0001.jpg, scan1.pdf
            stem = original_name.rsplit(".", 1)[0].lower()
            if len(stem) <= 4 or stem.startswith(("img_", "scan", "doc", "dsc")):
                issues.append(
                    Issue(
                        "filename_not_descriptive",
                        "recommendation",
                        f'Имя файла "{original_name}" не описывает содержание. {product.filename_rule_label} '
                        "требует, чтобы название отражало содержание и количество листов документа "
                        '(например: «Исковое заявление на 3л.pdf»). Переименуйте файл вручную.',
                    )
                )

        diagnostics.append(
            FileDiagnostic(
                original_filename=original_name,
                safe_name=safe_name,
                size_bytes=len(data),
                sha256=digest,
                content_type=content_type,
                page_count=page_count,
                issues=issues,
                data=data,
            )
        )

    # дисклеймер про электронную подпись — см. docs/requirements-sources.md R-6 (ArbitrPack) /
    # docs/justicepack/official-requirements.md GAS-R8 (JusticePack)
    batch_issues.append(
        Issue(
            "missing_signature_reminder",
            "recommendation",
            "Документы, требующие электронной подписи, должны быть подписаны вами отдельно "
            f"(например, средствами КриптоПро). {product.signature_disclaimer}",
        )
    )

    return diagnostics, batch_issues


def summarize(diagnostics: list[FileDiagnostic], batch_issues: list[Issue]) -> dict:
    all_issues = list(batch_issues) + [i for d in diagnostics for i in d.issues]
    critical = [i for i in all_issues if i.severity == "critical"]
    warning = [i for i in all_issues if i.severity == "warning"]
    recommendation = [i for i in all_issues if i.severity == "recommendation"]
    files_needing_fix = {
        d.original_filename for d in diagnostics if any(i.severity in ("critical", "warning") for i in d.issues)
    }
    return {
        "file_count": len(diagnostics),
        "critical_count": len(critical),
        "warning_count": len(warning),
        "recommendation_count": len(recommendation),
        "categories": sorted({i.rule_code for i in all_issues}),
        "files_needing_fix": sorted(files_needing_fix),
        "auto_fixable_count": sum(1 for i in all_issues if i.auto_fixable),
    }
