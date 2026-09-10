"""Диагностика изображений: повреждённость, EXIF, эвристика качества скана."""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_rules
from app.products import DEFAULT_PRODUCT_CODE
from app.validators.file_checks import Issue

# Стандартный лист A4 в дюймах (для эвристики эффективного DPI без метаданных сканера)
A4_WIDTH_IN = 8.27
A4_HEIGHT_IN = 11.69


@dataclass
class ImageInfo:
    ok: bool
    width: int | None = None
    height: int | None = None
    issues: list[Issue] | None = None


def inspect_image(data: bytes, filename: str = "", product_code: str = DEFAULT_PRODUCT_CODE) -> ImageInfo:
    issues: list[Issue] = []
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        # verify() делает объект непригодным для дальнейшего использования — переоткрываем
        img = Image.open(io.BytesIO(data))
        width, height = img.size
        img.load()
    except (UnidentifiedImageError, OSError, Exception) as exc:
        issues.append(
            Issue(
                "corrupted_file",
                "critical",
                f'Файл "{filename}" повреждён или не является корректным изображением ({exc.__class__.__name__}).',
            )
        )
        return ImageInfo(ok=False, issues=issues)

    rules = get_rules(product_code)["scanning_quality"]
    dpi = img.info.get("dpi")
    if dpi:
        effective_dpi = min(dpi[0], dpi[1])
    else:
        # эвристика: сравниваем пиксельный размер с листом A4, если явного DPI в метаданных нет
        effective_dpi = min(width / A4_WIDTH_IN, height / A4_HEIGHT_IN)

    if effective_dpi < rules["recommended_min_dpi"]:
        issues.append(
            Issue(
                "low_scan_quality",
                "warning",
                f'Файл "{filename}": похоже, разрешение скана ниже рекомендованного '
                f'({rules["recommended_min_dpi"]}–{rules["recommended_max_dpi"]} dpi). '
                "Текст и подписи могут быть нечитаемы.",
            )
        )

    return ImageInfo(ok=True, width=width, height=height, issues=issues)


def strip_exif(data: bytes, fmt: str) -> bytes:
    """Безопасное авто-исправление: удаление EXIF/метаданных изображения (геолокация, устройство и т.п.).

    ВАЖНО: перед удалением EXIF нужно физически повернуть пиксели по EXIF Orientation (частый тег у фото,
    снятых на телефон в портретной ориентации) — иначе после удаления EXIF теряется и подсказка для
    просмотрщика, и картинка окончательно остаётся повёрнутой в итоговом архиве. Баг найден и исправлен
    в рамках launch-readiness аудита (QA-агент воспроизвёл сценарий эмпирически, 0% покрытия до фикса)."""
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img) or img
    img_no_exif = Image.new(img.mode, img.size)
    img_no_exif.putdata(list(img.getdata()))
    out = io.BytesIO()
    img_no_exif.save(out, format=fmt)
    return out.getvalue()
