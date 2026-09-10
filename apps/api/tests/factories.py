"""Генераторы безопасных синтетических тестовых файлов. Никаких реальных судебных
документов или персональных данных — только сгенерированные программой заглушки."""
from __future__ import annotations

import io

from PIL import Image
from pypdf import PdfWriter


def make_valid_pdf(pages: int = 1, with_text: bool = True) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)  # A4 в pt
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_blank_pdf(pages: int = 1) -> bytes:
    """PDF без текста и без изображений — должен сработать эвристика 'possibly_blank_page'."""
    return make_valid_pdf(pages=pages, with_text=False)


def make_encrypted_pdf(password: str = "1234") -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_corrupted_pdf() -> bytes:
    return b"%PDF-1.4\nthis is not actually a valid pdf structure at all!!!\n%%EOF-broken"


def make_valid_jpeg(width: int = 800, height: int = 1100, dpi: tuple[int, int] = (300, 300)) -> bytes:
    img = Image.new("RGB", (width, height), color=(230, 230, 230))
    out = io.BytesIO()
    img.save(out, format="JPEG", dpi=dpi)
    return out.getvalue()


def make_low_dpi_jpeg() -> bytes:
    # маленькое разрешение относительно A4 => низкий эффективный dpi по эвристике
    img = Image.new("RGB", (300, 400), color=(200, 200, 200))
    out = io.BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


def make_valid_png(width: int = 800, height: int = 1100) -> bytes:
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    out = io.BytesIO()
    img.save(out, format="PNG", dpi=(300, 300))
    return out.getvalue()


def make_corrupted_image() -> bytes:
    return b"\xff\xd8\xff\xe0not a real jpeg body at all"


def make_jpeg_with_exif_orientation(orientation: int = 6, width: int = 200, height: int = 100) -> bytes:
    """JPEG со снятым "лёжа" телефоном скана: пиксели физически landscape (width>height), но EXIF
    Orientation=6 говорит просмотрщику повернуть на 90° при отображении. Используется для регрессионного
    теста strip_exif() — до фикса удаление EXIF оставляло пиксели неповёрнутыми, "теряя" ориентацию.
    Стандартный тег EXIF Orientation — 0x0112 (274), не требует стороннего пакета — используется
    встроенный Image.Exif() из Pillow."""
    img = Image.new("RGB", (width, height), color=(180, 20, 20))
    exif = Image.Exif()
    exif[274] = orientation  # 274 = ExifTags.Base.Orientation
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def make_oversized_blob(size_mb: float) -> bytes:
    return b"0" * int(size_mb * 1024 * 1024)
