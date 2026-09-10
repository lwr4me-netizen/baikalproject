"""Абстракция объектного хранилища: MinIO/S3 в проде, локальный диск как fallback для тестов
без поднятого MinIO (ARBITRPACK_S3_USE_LOCAL_FALLBACK=true). Buckets закрытые, публичного доступа нет —
доступ только через подписанные временные ссылки."""
from __future__ import annotations

import io
import os
import pathlib
import shutil
from abc import ABC, abstractmethod

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.config import get_settings


class StorageBackend(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def presigned_url(self, key: str, expires_seconds: int) -> str: ...


class S3StorageBackend(StorageBackend):
    def __init__(self) -> None:
        s = get_settings()
        self._bucket = s.s3_bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url,
            aws_access_key_id=s.s3_access_key,
            aws_secret_access_key=s.s3_secret_key,
            region_name=s.s3_region,
            config=BotoConfig(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    def presigned_url(self, key: str, expires_seconds: int) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )


class LocalDiskStorageBackend(StorageBackend):
    """Только для локальной разработки/тестов без MinIO. Не предназначен для production."""

    def __init__(self) -> None:
        s = get_settings()
        self._root = pathlib.Path(s.local_storage_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> pathlib.Path:
        # защита от path traversal даже во внутреннем ключе
        safe = key.replace("..", "_").lstrip("/")
        p = (self._root / safe).resolve()
        if not str(p).startswith(str(self._root.resolve())):
            raise ValueError("Insecure storage key")
        return p

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def presigned_url(self, key: str, expires_seconds: int) -> str:
        # В локальном режиме реального подписанного URL нет — используется собственный DownloadToken API.
        return f"local://{key}"


def get_storage() -> StorageBackend:
    s = get_settings()
    if s.s3_use_local_fallback or s.environment == "test":
        return LocalDiskStorageBackend()
    return S3StorageBackend()
