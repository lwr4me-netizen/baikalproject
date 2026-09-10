"""Централизованная конфигурация приложения. Секреты берутся только из окружения."""
from __future__ import annotations

import pathlib
from functools import lru_cache

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.products import DEFAULT_PRODUCT_CODE, get_product

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
# Сохранено для обратной совместимости (использовалось до введения реестра продуктов
# app.products.PRODUCTS) — теперь это просто путь профиля ARBITRPACK по умолчанию.
RULES_PATH = REPO_ROOT / "packages" / "validation-rules" / "rules.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ARBITRPACK_", extra="ignore")

    environment: str = Field(default="development")  # development | test | production
    secret_key: str = Field(default="dev-insecure-secret-change-me")

    database_url: str = Field(default="postgresql+psycopg://arbitrpack:arbitrpack@localhost:5432/arbitrpack")

    s3_endpoint_url: str = Field(default="http://localhost:9000")
    s3_access_key: str = Field(default="minioadmin")
    s3_secret_key: str = Field(default="minioadmin")
    s3_bucket: str = Field(default="arbitrpack-files")
    s3_region: str = Field(default="us-east-1")
    s3_use_local_fallback: bool = Field(default=False)  # если True — хранить на локальном диске (для тестов без MinIO)
    local_storage_dir: str = Field(default="/tmp/arbitrpack-storage")

    payment_provider: str = Field(default="mock")  # mock | yookassa
    yookassa_shop_id: str = Field(default="")
    yookassa_secret_key: str = Field(default="")
    yookassa_api_base: str = Field(default="https://api.yookassa.ru/v3")

    frontend_base_url: str = Field(default="http://localhost:3000")
    api_base_url: str = Field(default="http://localhost:8000")

    download_token_ttl_seconds: int = Field(default=900)  # 15 минут на подписанную ссылку
    max_upload_concurrency: int = Field(default=10)

    rate_limit_uploads_per_hour: str = Field(default="30/hour")
    rate_limit_webhook_per_minute: str = Field(default="120/minute")
    # Найдено в launch-readiness аудите: у /api/admin/metrics не было своего лимита, что вместе с
    # нестойкой к тайминг-атакам проверкой токена (уже исправлено на constant_time_eq) давало
    # атакующему неограниченное число попыток подобрать ARBITRPACK_ADMIN_TOKEN.
    rate_limit_admin_per_minute: str = Field(default="60/minute")

    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_rules(product_code: str = DEFAULT_PRODUCT_CODE) -> dict:
    """Загружает набор правил профиля продукта. По умолчанию (без аргумента) — ARBITRPACK,
    это сохраняет поведение, на которое опирались все вызовы до введения JusticePack.
    Правила физически разделены по файлам на продукт (см. app.products.PRODUCTS) —
    НЕ параметризованы одним общим шаблоном (раздел 2/4 ТЗ JusticePack)."""
    profile = get_product(product_code)
    with open(profile.rules_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
