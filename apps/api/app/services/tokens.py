"""Временные подписанные ссылки на скачивание. Сам токен не хранится — хранится только его хэш,
как для пароля. Токен передаётся пользователю один раз в ответе API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import DownloadToken
from app.security import generate_download_token, hash_token


def issue_download_token(db: Session, *, job_id: str, ttl_seconds: int) -> str:
    token = generate_download_token()
    record = DownloadToken(
        job_id=job_id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
    )
    db.add(record)
    db.commit()
    return token


def resolve_download_token(db: Session, token: str) -> DownloadToken | None:
    record = db.query(DownloadToken).filter(DownloadToken.token_hash == hash_token(token)).first()
    if record is None:
        return None
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        # SQLite (используется в тестах) не хранит tzinfo — трактуем как UTC, как и было записано.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return record
