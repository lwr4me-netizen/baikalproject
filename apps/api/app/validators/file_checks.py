"""Базовые проверки файла: MIME по содержимому, расширение, размер, двойное расширение,
пустой файл. Правила читаются из rules.yaml (packages/validation-rules)."""
from __future__ import annotations

from dataclasses import dataclass

import magic

from app.config import get_rules
from app.products import DEFAULT_PRODUCT_CODE, get_product
from app.security import has_double_extension

MIME_TO_EXT = {
    "application/pdf": {"pdf"},
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
}


@dataclass
class Issue:
    rule_code: str
    severity: str
    message: str
    auto_fixable: bool = False


def detect_mime(data: bytes) -> str:
    return magic.from_buffer(data, mime=True)


def check_file(*, filename: str, data: bytes, product_code: str = DEFAULT_PRODUCT_CODE) -> list[Issue]:
    rules = get_rules(product_code)["files"]
    issues: list[Issue] = []

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if has_double_extension(filename):
        issues.append(
            Issue(
                "double_extension",
                "critical",
                f'Имя файла "{filename}" содержит подозрительное двойное расширение и отклонено из соображений безопасности.',
            )
        )
        return issues  # дальнейшие проверки бессмысленны для явно опасного файла

    if ext not in rules["allowed_extensions"]:
        issues.append(
            Issue(
                "disallowed_extension",
                "critical",
                f'Формат ".{ext or "?"}" не поддерживается. Разрешены: {", ".join(rules["allowed_extensions"])}.',
            )
        )
        return issues

    if len(data) < rules["min_file_size_bytes"]:
        issues.append(Issue("empty_file", "critical", f'Файл "{filename}" пуст или повреждён (0 байт).'))
        return issues

    max_bytes = rules["max_file_size_mb"] * 1024 * 1024
    if len(data) > max_bytes:
        issues.append(
            Issue(
                "oversized_file",
                "critical",
                f'Файл "{filename}" превышает допустимый размер {rules["max_file_size_mb"]} МБ '
                f"(фактически {len(data) / (1024 * 1024):.1f} МБ).",
            )
        )

    detected = detect_mime(data)
    expected_exts = MIME_TO_EXT.get(detected)
    if expected_exts is None or ext not in expected_exts:
        issues.append(
            Issue(
                "mime_extension_mismatch",
                "critical",
                f'Содержимое файла "{filename}" ({detected}) не соответствует его расширению ".{ext}". '
                "Возможна подмена типа файла.",
            )
        )

    return issues


def check_batch_totals(
    *, total_size_bytes: int, file_count: int, product_code: str = DEFAULT_PRODUCT_CODE
) -> list[Issue]:
    rules = get_rules(product_code)["files"]
    product = get_product(product_code)
    issues: list[Issue] = []
    max_batch_bytes = rules["max_batch_size_mb"] * 1024 * 1024
    if total_size_bytes > max_batch_bytes:
        issues.append(
            Issue(
                "batch_too_large",
                "critical",
                f'Общий размер загрузки превышает техническое ограничение сервиса '
                f'({rules["max_batch_size_mb"]} МБ). Это ограничение {product.display_name}, '
                f'а не требование {product.target_system}.',
            )
        )
    if file_count > rules["max_files_per_batch"]:
        issues.append(
            Issue(
                "batch_too_large",
                "critical",
                f'Слишком много файлов в одной загрузке (максимум {rules["max_files_per_batch"]}).',
            )
        )
    return issues
