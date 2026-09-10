import os
import shutil
import tempfile

# ВАЖНО: переменные окружения должны быть выставлены до первого импорта app.config.get_settings()
os.environ["ARBITRPACK_ENVIRONMENT"] = "test"
os.environ["ARBITRPACK_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ARBITRPACK_S3_USE_LOCAL_FALLBACK"] = "true"
os.environ["ARBITRPACK_PAYMENT_PROVIDER"] = "mock"
os.environ["ARBITRPACK_ADMIN_TOKEN"] = "test-admin-token"
os.environ["ARBITRPACK_SECRET_KEY"] = "test-secret-key"

os.environ["ARBITRPACK_LOCAL_STORAGE_DIR"] = tempfile.mkdtemp(prefix="arbitrpack-test-root-")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base, get_db
from app.main import app
from app.payments.mock import MockPaymentProvider
from app.rate_limit import limiter
from fastapi.testclient import TestClient

TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=TEST_ENGINE, autoflush=False, autocommit=False, future=True)


@pytest.fixture(autouse=True)
def _fresh_db_and_storage():
    Base.metadata.create_all(bind=TEST_ENGINE)
    MockPaymentProvider.reset()
    # Rate limiter — общий процесс на все тесты (in-memory storage), без сброса тесты, идущие
    # позже в сессии, начинают падать по 429 просто из-за суммарного числа запросов предыдущих
    # тестов, а не из-за собственного поведения. Сбрасываем перед каждым тестом для изоляции.
    limiter.reset()

    storage_dir = get_settings().local_storage_dir
    shutil.rmtree(storage_dir, ignore_errors=True)
    os.makedirs(storage_dir, exist_ok=True)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield

    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def client():
    return TestClient(app)
