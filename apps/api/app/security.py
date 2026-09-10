"""Общие security-утилиты: безопасные имена файлов, хэширование, токены."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import unicodedata

_UNSAFE_CHARS = re.compile(r"[^A-Za-zА-Яа-яЁё0-9 ._\-\(\)]")
_DANGEROUS_EXT_RE = re.compile(
    r"\.(exe|sh|bat|cmd|js|php|py|jar|com|scr|vbs|ps1|msi|dll|apk)(\.|$)", re.IGNORECASE
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_hex_of_stream(chunks) -> str:
    h = hashlib.sha256()
    for chunk in chunks:
        h.update(chunk)
    return h.hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_download_token() -> str:
    return secrets.token_urlsafe(32)


def generate_idempotency_key() -> str:
    return secrets.token_hex(16)


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def has_double_extension(filename: str) -> bool:
    """Обнаружение опасных двойных расширений вида `document.pdf.exe` или `document.exe.pdf`:
    любое вхождение исполняемого/скриптового расширения где-либо в цепочке точек, а не только в конце."""
    if filename.count(".") < 2:
        return False
    return bool(_DANGEROUS_EXT_RE.search(filename))


def safe_filename(original: str, fallback_ext: str = "") -> str:
    """Нормализует имя файла: убирает путь, транслитерирует опасные символы,
    защищает от path traversal (никогда не используется как storage key)."""
    name = unicodedata.normalize("NFKC", original)
    name = os.path.basename(name)
    name = name.replace("\x00", "")
    name = _UNSAFE_CHARS.sub("_", name)
    name = name.strip(" .")
    if not name:
        name = f"file{fallback_ext}"
    if len(name) > 180:
        base, dot, ext = name.rpartition(".")
        keep = 180 - len(ext) - 1 if dot else 180
        name = (base[:keep] + dot + ext) if dot else name[:180]
    return name


def hash_ip(ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{ip}".encode("utf-8")).hexdigest()
