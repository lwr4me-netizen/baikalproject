# Baseline-аудит BAIKALPROJECT перед разработкой JusticePack

Дата: 2026-09-09 (продолжение сессии, второй этап после запуска ArbitrPack). Выполнено ДО каких-либо изменений кода.

## 1. Структура репозитория (на момент аудита)

```text
arbitrpack/                       # корень репозитория (внутреннее имя каталога; продукт называется BAIKALPROJECT)
  apps/
    api/                          # FastAPI backend
      app/
        routers/                  # upload.py, payments.py, download.py, admin.py
        validators/                # file_checks.py, pdf_checks.py, image_checks.py
        payments/                 # base.py (интерфейс), mock.py, yookassa.py
        services/                 # diagnostics.py, archive.py, tokens.py, analytics.py, ttl_cleanup.py
        models.py                 # SQLAlchemy: UserSession, UploadBatch, UploadedFile, ValidationRule,
                                   # ValidationResult, ProcessingJob, Payment, ProcessedWebhookEvent,
                                   # DownloadToken, AuditEvent, AnalyticsEvent, ConsentRecord
        config.py                 # get_settings(), get_rules() — ЖЁСТКО читает один файл rules.yaml
      tests/                      # 49 тестов, 90% покрытия
      alembic/                    # 1 миграция (initial schema)
    web/                          # Next.js 14 (App Router) + TypeScript
      app/page.tsx                # лендинг (жёстко про «Мой Арбитр»)
      app/upload/page.tsx
      app/result/[batchId]/page.tsx
      lib/api.ts
  packages/validation-rules/rules.yaml   # ЕДИНЫЙ набор правил, без понятия "продукт"/"профиль"
  docker-compose.yml, docker-compose.prod.yml, infrastructure/docker/Caddyfile
  docs/ (requirements-sources, threat-model, analytics, economics, marketing-yandex, deployment)
```

## 2. Статус ArbitrPack на момент аудита

Полностью рабочий вертикальный сценарий: загрузка → диагностика → mock/YooKassa-оплата → идемпотентный webhook →
сборка ZIP с безопасными автоисправлениями → TTL-ограниченная ссылка на скачивание → удаление. Frontend — 5 экранов
на русском, единственный "продукт" в системе, весь UI и все тексты жёстко ссылаются на «Мой Арбитр».

## 3. Результаты тестов ДО изменений (зафиксировано в этой сессии)

```bash
cd apps/api && source .venv/bin/activate && python -m pytest -q --cov=app --cov-report=term-missing
# 49 passed, 3 warnings, 90% coverage — идентично результату первой сессии (регрессий с прошлого прогона нет)

cd apps/web && npm run build
# ✓ Compiled successfully, 6 маршрутов, typecheck проходит без ошибок
```

Эти 49 тестов и билд — контрольная точка (baseline). Любое изменение ниже обязано не уменьшить это число.

## 4. Что жёстко завязано на ArbitrPack (риск при добавлении второго аппарата)

| Место | Проблема | Требуемое изменение |
|---|---|---|
| `app/config.py::get_rules()` | Один захардкоженный путь к `packages/validation-rules/rules.yaml`, нет параметра профиля | Ввести реестр профилей, не ломая существующий вызов без аргументов (default = ARBITRPACK) |
| `app/validators/file_checks.py`, `pdf_checks.py`, `image_checks.py` | Читают правила через глобальный `get_rules()` без указания продукта | Добавить необязательный параметр `product_code` с default ARBITRPACK — обратная совместимость сохраняется |
| `app/models.py` | Ни в одной таблице нет `product_code` | Добавить колонку с default `ARBITRPACK` в существующих таблицах (новая Alembic-миграция, не ломает старые данные) |
| `app/routers/upload.py::upload_batch` | Нет параметра выбора продукта; бесплатная диагностика жёстко на ArbitrPack-правилах | Добавить обязательный form-параметр `product_code` |
| `app/services/analytics.py::VALID_EVENTS` | События не разделены по продукту | Добавить `product_code` в `AnalyticsEvent`, фильтрация в `/api/admin/metrics` |
| `packages/validation-rules/rules.yaml` | Единственный файл, привязан к тарифу/лимитам «Мой Арбитр» | Не трогать (нулевой риск регрессии) — это теперь официально ruleset профиля `ARBITR_MY_ARBITR`. Новый профиль `GAS_PRAVOSUDIE` получает отдельный файл `config/rules/gas_pravosudie.yaml` |
| `apps/web/app/page.tsx`, `layout.tsx` | Тексты и заголовки — только про «Мой Арбитр» | Добавить экран выбора аппарата `/` → `/services/arbitrpack` (алиас на существующий `/upload`) или `/services/justicepack`, не ломая текущий `/upload` |
| `app/payments/*` | `PaymentProvider` не знает о продукте — цена берётся из одного места (`rules.yaml: pricing`) | Тариф должен определяться профилем: `get_price(product_code)` |

## 5. Незавершённые заглушки / TODO / mock в текущем коде

- `MockPaymentProvider` — намеренный mock для dev/test, не баг.
- Эндпоинты `/api/mock/{id}/confirm|cancel` — намеренно dev-only, защищены проверкой `payment_provider == "mock"`.
- В `docs/requirements-sources.md` — ряд правил ArbitrPack помечены `PARTIALLY VERIFIED`/`UNVERIFIED` (честно, не TODO).
- Настоящих `TODO`/`FIXME` комментариев в коде не найдено (`grep -rn "TODO\|FIXME" apps/api/app apps/web/app` — пусто).

## 6. Компоненты, пригодные для прямого переиспользования в JusticePack без изменений

- Хранилище (`app/storage.py`) — не завязано на продукт, работает как есть.
- Токены скачивания (`app/services/tokens.py`) — универсальны.
- ZIP-сборщик (`app/services/archive.py`) — универсален (работает с любым списком `FileDiagnostic`).
- Платёжные адаптеры (`app/payments/mock.py`, `yookassa.py`) — универсальны, продукт передаётся через `metadata`.
- Rate limiting, secure headers, TTL-очистка — общеплатформенные, без изменений.
- Модели `UserSession`, `ConsentRecord`, `DownloadToken`, `ProcessedWebhookEvent` — без изменений.

## 7. Риски регрессии при введении JusticePack

1. Изменение сигнатуры `get_rules()`/валидаторов — если сделать `product_code` обязательным, все 49 существующих
   тестов и роутер `upload.py` сломаются. **Меры:** параметр всегда опциональный, default `ARBITRPACK`.
2. Добавление колонки `product_code` в существующие таблицы — Alembic migration должна иметь `server_default`,
   чтобы не требовать бэкофилла и не ронять существующие (пустые в dev/test) данные.
3. Общий upload-роут теперь принимает `product_code` от клиента — если фронтенд ArbitrPack не будет его передавать,
   запрос будет отклонён. **Меры:** дать `product_code` умолчание на уровне API-схемы (`Form("ARBITRPACK")`), а
   существующий `apps/web` для ArbitrPack явно проставить `ARBITRPACK`, чтобы поведение было явным, а не случайным.
4. Общий `/api/admin/metrics` — если не отфильтровать по продукту, цифры JusticePack и ArbitrPack смешаются.
   **Меры:** обязательный query-параметр `product_code` в admin-эндпоинте.

## 8. Вывод

Baseline зафиксирован: 49/49 тестов, 90% покрытия backend, чистая сборка frontend. Архитектура допускает безопасное
расширение без переписывания — план ниже (раздел «План изменений» в этом же коммите) следует принципу: любое
изменение существующего кода обратно совместимо по умолчанию, JusticePack — additive, а не replace.
