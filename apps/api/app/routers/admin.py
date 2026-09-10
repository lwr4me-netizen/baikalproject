"""Защищённый отчёт продуктовой аналитики (раздел 11 ТЗ). Доступ по Bearer-токену
ARBITRPACK_ADMIN_TOKEN (задаётся в .env, отсутствует в репозитории)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import AnalyticsEvent, Payment, PaymentStatus, UploadBatch, UserSession, ValidationResult
from app.products import PRODUCTS
from app.rate_limit import limiter
from app.security import constant_time_eq

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(authorization: str | None = Header(default=None)) -> None:
    token = os.environ.get("ARBITRPACK_ADMIN_TOKEN")
    if not token:
        raise HTTPException(503, "Админ-панель не сконфигурирована (не задан ARBITRPACK_ADMIN_TOKEN).")
    # constant_time_eq вместо "!=" — найдено в launch-readiness аудите: обычное сравнение строк
    # не защищено от timing-атаки (Python сравнивает байты по порядку и выходит на первом несовпадении).
    presented = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if not authorization or not authorization.startswith("Bearer ") or not constant_time_eq(presented, token):
        raise HTTPException(401, "Неверный или отсутствующий токен доступа.")


def _visitors_for(db: Session, product_code: str | None) -> int:
    """Найдено в launch-readiness аудите: раньше `visitors` считался по ВСЕМ UserSession без
    фильтра даже внутри product_code-скоуп­ированного ответа — цифра "визитов" одного продукта на
    самом деле включала визиты другого. Теперь: без product_code — общий трафик (сессия сама по себе
    product-agnostic, может видеть оба аппарата на экране выбора), с product_code — только сессии,
    у которых есть хотя бы одно аналитическое событие именно с этим product_code."""
    if product_code is None:
        return db.query(func.count(UserSession.id)).scalar() or 0
    return (
        db.query(func.count(func.distinct(AnalyticsEvent.session_id)))
        .filter(AnalyticsEvent.product_code == product_code, AnalyticsEvent.session_id.isnot(None))
        .scalar()
        or 0
    )


def _metrics_for(db: Session, product_code: str | None) -> dict:
    """Считает метрики, опционально отфильтрованные по product_code. product_code=None — "визитов"
    считается по всем сессиям (сессия product-agnostic — см. ниже), но воронка/деньги/выдача
    в остальных полях учитывают только события/платежи/задания с этим product_code, если он задан."""
    analytics_q = db.query(AnalyticsEvent)
    payments_q = db.query(Payment)
    results_q = db.query(ValidationResult).join(UploadBatch, ValidationResult.batch_id == UploadBatch.id)
    if product_code is not None:
        analytics_q = analytics_q.filter(AnalyticsEvent.product_code == product_code)
        payments_q = payments_q.filter(Payment.product_code == product_code)
        results_q = results_q.filter(UploadBatch.product_code == product_code)

    started = (
        analytics_q.filter(AnalyticsEvent.event_name == "upload_completed")
        .with_entities(func.count(func.distinct(AnalyticsEvent.batch_id)))
        .scalar()
        or 0
    )
    completed_diag = (
        analytics_q.filter(AnalyticsEvent.event_name == "diagnostics_free_result_shown")
        .with_entities(func.count(func.distinct(AnalyticsEvent.batch_id)))
        .scalar()
        or 0
    )
    paid = payments_q.filter(Payment.status == PaymentStatus.succeeded).with_entities(func.count(Payment.id)).scalar() or 0

    total_amount = 0.0
    succeeded_payments = payments_q.filter(Payment.status == PaymentStatus.succeeded).all()
    for p in succeeded_payments:
        try:
            total_amount += float(p.amount_value)
        except ValueError:
            pass

    conversion = (paid / started) if started else 0.0
    avg_check = (total_amount / paid) if paid else 0.0

    top_issues = (
        results_q.with_entities(ValidationResult.rule_code, func.count(ValidationResult.id).label("cnt"))
        .group_by(ValidationResult.rule_code)
        .order_by(func.count(ValidationResult.id).desc())
        .limit(10)
        .all()
    )

    return {
        "visitors": _visitors_for(db, product_code),
        "checks_started": started,
        "checks_completed_free": completed_diag,
        "payments_succeeded": paid,
        "conversion_to_payment": round(conversion, 4),
        "average_check_rub": round(avg_check, 2),
        "revenue_rub": round(total_amount, 2),
        "top_issue_categories": [{"rule_code": code, "count": cnt} for code, cnt in top_issues],
    }


@router.get("/metrics")
@limiter.limit(lambda: get_settings().rate_limit_admin_per_minute)
def metrics(
    request: Request,
    product_code: str | None = Query(default=None, description="ARBITRPACK | JUSTICEPACK. Если не задан — сводка по всем + разбивка by_product."),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
):
    """Раздел 11 ТЗ / раздел «Аналитика» ТЗ JusticePack: статистика двух продуктов НИКОГДА не
    смешивается без явного разделения. По умолчанию (без product_code — обратная совместимость
    с уже существующим вызовом) отчёт содержит как объединённые цифры визитов/сессий (которые
    product-agnostic: сессия может видеть оба аппарата на экране выбора), так и обязательную
    разбивку `by_product` с полностью раздельными воронками/деньгами/выдачей по каждому продукту.
    Передайте `?product_code=ARBITRPACK` или `?product_code=JUSTICEPACK`, чтобы получить отчёт
    строго по одному продукту (остальные поля отражают только его данные)."""
    if product_code is not None and product_code not in PRODUCTS:
        raise HTTPException(400, f"Неизвестный product_code. Допустимые значения: {sorted(PRODUCTS)}")

    by_product = {code: _metrics_for(db, code) for code in sorted(PRODUCTS)}

    if product_code is not None:
        scoped = _metrics_for(db, product_code)
        return {
            "period": "last_30_days_and_all_time_mixed_mvp",
            "product_code": product_code,
            **scoped,
            "note": "CAC, прибыль до/после рекламных расходов считаются в docs/economics.md (ArbitrPack) и "
            "docs/justicepack/market-validation.md (JusticePack) — там нужны реальные данные рекламного "
            "кабинета (UNKNOWN, если не подставлены владельцем).",
        }

    combined = _metrics_for(db, None)
    return {
        "period": "last_30_days_and_all_time_mixed_mvp",
        "product_code": "ALL",
        **combined,
        # Разбивка по продуктам ВСЕГДА присутствует рядом с объединённой сводкой — так объединённые
        # цифры выше никогда не выдаются за данные одного продукта (раздел 2/11 ТЗ JusticePack).
        # visitors внутри by_product[X] — это сессии, реально видевшие события именно продукта X
        # (не общий трафик сайта — см. _visitors_for), в отличие от верхнего "visitors" здесь.
        "by_product": by_product,
        "note": "CAC, прибыль до/после рекламных расходов считаются в docs/economics.md (ArbitrPack) и "
        "docs/justicepack/market-validation.md (JusticePack) — там нужны реальные данные рекламного "
        "кабинета (UNKNOWN, если не подставлены владельцем).",
    }
