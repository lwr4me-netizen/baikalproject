from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.db import Base, engine
from app.rate_limit import limiter
from app.routers import admin, download, payments, upload

# Структурированные логи: НИКОГДА не логируем имена файлов, содержимое документов или ПДн.
structlog.configure(processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()])
log = structlog.get_logger()

settings = get_settings()

app = FastAPI(
    title="ArbitrPack API",
    description="Техническая подготовка и проверка документов перед подачей в «Мой Арбитр». "
    "Не является юридической консультацией и не гарантирует принятие документов судом.",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def secure_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/health/db")
def health_db():
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


app.include_router(upload.router)
app.include_router(payments.router)
app.include_router(download.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup():
    # В production миграции выполняются отдельно через alembic (см. Makefile `make migrate`).
    # create_all безопасен как idempotent fallback для dev/test окружений.
    if settings.environment in ("development", "test"):
        Base.metadata.create_all(bind=engine)
    log.info("arbitrpack_api_started", environment=settings.environment, payment_provider=settings.payment_provider)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=str(request.url.path), error_type=exc.__class__.__name__)
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера."})
