# BAIKALPROJECT — платформа цифровых аппаратов технической подготовки документов

BAIKALPROJECT — платформа, на которой работают два независимых цифровых аппарата ("вендинг-машины") технической
проверки документов перед электронной подачей в суд:

- **ArbitrPack** (`product_code=ARBITRPACK`) — для «Мой Арбитр» (арбитражные суды), маршрут `/upload`.
- **JusticePack** (`product_code=JUSTICEPACK`) — для ГАС «Правосудие» (суды общей юрисдикции), маршрут
  `/services/justicepack`. См. `docs/justicepack/`.

Оба принимают файлы пользователя (PDF/JPG/PNG), выполняют техническую диагностику (повреждённость, шифрование,
дубликаты, размер, MIME-подмену и т.д.), показывают бесплатный отчёт о найденных проблемах, а после оплаты —
собирают итоговый ZIP-архив с безопасными автоматическими исправлениями (удаление метаданных/EXIF) и выдают
временную ссылку на скачивание. **Правила, лимиты и тарифы двух аппаратов независимо проверены по разным приказам
и физически разделены в конфигурации** (`packages/validation-rules/rules.yaml` для ArbitrPack,
`config/rules/gas_pravosudie.yaml` для JusticePack) — см. `docs/justicepack/official-requirements.md` за таблицей
подтверждённых отличий.

**Это не юридическая консультация и не гарантия принятия документов судом.** Оба сервиса выполняют только
техническую подготовку и проверку файлов перед самостоятельной подачей пользователем.

## Статус проекта

Рабочий вертикальный сценарий (выбор аппарата → загрузка → диагностика → mock-оплата → сборка архива → скачивание →
TTL-удаление) реализован для **обоих** продуктов, покрыт автотестами (73 backend-теста, см. «Тесты» ниже) и пройден
вручную через два независимых Playwright E2E-сценария против реально запущенных backend+frontend
(`tests/e2e/full-flow.spec.ts` — ArbitrPack, `tests/e2e/justicepack-flow.spec.ts` — JusticePack + регрессия
ArbitrPack). Интеграция с реальным тестовым магазином ЮKassa реализована и покрыта тестами на замоканных
HTTP-вызовах — реальные ключи владельцем не предоставлены (см. `docs/deployment.md`, раздел 5); оплата JusticePack
использует ту же интеграцию с собственным тарифом.

Домен (`baikalproject.pro`) и VPS (Timeweb Cloud, `201.24.54.96`) владельцем уже выделены — пошаговый runbook именно
под это развёртывание находится в `docs/deployment.md`. Оба продукта разворачиваются на одной инфраструктуре
(один VPS, один backend-процесс, один frontend) — разделение чисто продуктовое, через `product_code`.

## Структура репозитория

```text
arbitrpack/
  apps/
    web/                  # Next.js + TypeScript frontend
    api/                  # FastAPI backend
  packages/
    validation-rules/     # rules.yaml — правила профиля ARBITRPACK, вне кода
  config/
    rules/gas_pravosudie.yaml  # правила профиля JUSTICEPACK — физически отдельный файл, см. app/products.py
  infrastructure/
    docker/Caddyfile       # reverse proxy + HTTPS для продакшена (baikalproject.pro)
  docs/                   # requirements-sources, threat-model, deployment, analytics, economics, marketing
    justicepack/          # baseline-audit, official-requirements, market-validation, yandex-launch (JusticePack)
  tests/
    e2e/                  # Playwright: full-flow.spec.ts (ArbitrPack), justicepack-flow.spec.ts (JusticePack)
  scripts/
    ttl_cleanup.py         # CLI для TTL-очистки (запускается по cron)
  docker-compose.yml       # локальная разработка — порты БД/MinIO/API/Web опубликованы на localhost
  docker-compose.prod.yml  # продакшен — наружу только 80/443 через Caddy, см. docs/deployment.md
  .env.example
  README.md
  SECURITY.md
  PRIVACY.md
  OFFER-DRAFT.md
  Makefile
```

## Быстрый старт (локально, без Docker)

```bash
make setup   # venv + pip install + npm install

# Терминал 1 — backend с mock-платежами и локальным диском вместо MinIO
cd apps/api && source .venv/bin/activate
ARBITRPACK_ENVIRONMENT=development \
ARBITRPACK_DATABASE_URL="sqlite:////tmp/arbitrpack_dev.db" \
ARBITRPACK_S3_USE_LOCAL_FALLBACK=true \
ARBITRPACK_PAYMENT_PROVIDER=mock \
ARBITRPACK_ADMIN_TOKEN=devtoken \
uvicorn app.main:app --reload --port 8000

# Терминал 2 — frontend
cd apps/web && npm run dev
```

Откройте http://localhost:3000 — экран выбора аппарата («Мой Арбитр» / «ГАС Правосудие») → загрузка → бесплатный
отчёт → «Оплатить» (mock) → скачивание архива. Прямые ссылки: `/upload` (ArbitrPack), `/services/justicepack`
(JusticePack).

## Быстрый старт (Docker Compose — рекомендуется для полной проверки)

```bash
cp .env.example .env   # заполните значения (или оставьте dev-заглушки для локального теста)
make up
```

Поднимает: PostgreSQL, MinIO, `migrate` (прогоняет Alembic один раз), `api` (FastAPI), `web` (Next.js). Все сервисы
имеют health checks; `api` и `web` стартуют только после успешных зависимостей.

- Frontend: http://localhost:3000
- API: http://localhost:8000 (документация OpenAPI: http://localhost:8000/docs)
- MinIO Console: http://localhost:9001

```bash
make down               # остановить стек
make clean-test-data    # очистить локальные тестовые артефакты
```

Это — dev-профиль (`docker-compose.yml`), удобный локально: порты Postgres/MinIO/API/Web опубликованы на
`localhost`. Для реального сервера используется отдельный `docker-compose.prod.yml` (без публикации этих портов,
плюс Caddy на 80/443) — пошаговая инструкция под конкретный домен и VPS в `docs/deployment.md`.

## Тесты

```bash
make test   # backend: pytest, unit + integration + API, с покрытием
```

Актуальный результат прогона в этой сессии: **73 теста, 73 успешных, 0 неуспешных, 90% покрытия строк backend**
(`apps/api`, `--cov=app`) — 49 исходных тестов ArbitrPack (не изменены, ноль регрессий) + 24 новых теста
JusticePack (`apps/api/tests/test_justicepack.py`: выбор аппарата, изоляция правил, полный платный сценарий,
разделение аналитики, регрессия ArbitrPack). Команда воспроизведения указана выше.

Дополнительно вручную пройдены ДВА сквозных сценария через Playwright против реально запущенных `uvicorn` +
`next start` на этой машине — оба зелёные:

```bash
# backend и frontend должны быть подняты (см. «Быстрый старт» выше)
cd tests/e2e && npm install && npx playwright test
# → full-flow.spec.ts (ArbitrPack) + justicepack-flow.spec.ts (выбор аппарата → JusticePack → оплата →
#   скачивание, плюс отдельный тест регрессии ArbitrPack через UI) — 3 passed
```

Обнаруженные ограничения тестирования — см. финальный отчёт в конце этого README.

## Платежи

`app/payments/base.py` определяет интерфейс `PaymentProvider`. Есть две реализации:

- `MockPaymentProvider` — по умолчанию, для локальной разработки и тестов, не требует ключей.
- `YooKassaPaymentProvider` — тестовый магазин ЮKassa. Требует переменные окружения `ARBITRPACK_YOOKASSA_SHOP_ID` /
  `ARBITRPACK_YOOKASSA_SECRET_KEY` (получаются в личном кабинете тестового магазина, см. `docs/deployment.md`).
  Без них приложение выбрасывает понятную ошибку при старте с `ARBITRPACK_PAYMENT_PROVIDER=yookassa`, а не тихо
  работает с пустыми ключами.

Webhook **никогда не доверяется напрямую** — после получения события backend всегда перезапрашивает актуальный
статус через официальный API ЮKassa и только затем принимает решение о выдаче результата. Идемпотентность повторных
webhook обеспечена уникальным индексом на `(provider, provider_payment_id, status)`.

## Правила валидации — конфигурация, не код

Все лимиты (форматы, размеры файлов, TTL, цена и т.д.) вынесены в YAML, ОТДЕЛЬНО на продукт — `app/products.py`
хранит реестр `product_code -> путь к файлу правил`, оба файла физически разделены (это намеренное архитектурное
решение, не параметризация одним шаблоном — см. `docs/justicepack/official-requirements.md`, раздел про
подтверждённые отличия):

- `packages/validation-rules/rules.yaml` — профиль `ARBITRPACK` («Мой Арбитр»), источники — `docs/requirements-sources.md`.
- `config/rules/gas_pravosudie.yaml` — профиль `JUSTICEPACK` (ГАС «Правосудие»), источники —
  `docs/justicepack/official-requirements.md`.

Каждое правило задокументировано с источником, включая честную маркировку `VERIFIED` / `PARTIALLY VERIFIED` /
`UNVERIFIED` в зависимости от того, удалось ли подтвердить его официальным первоисточником. `product_code`
проходит через всю систему — от формы загрузки до платежа, `ProcessingJob`, аналитики и админ-отчёта — со
значением по умолчанию `ARBITRPACK`, чтобы существующее поведение ArbitrPack не изменилось.

## Документация

- [`docs/requirements-sources.md`](docs/requirements-sources.md) — источники технических требований (обязательно к прочтению перед изменением правил).
- [`docs/threat-model.md`](docs/threat-model.md) — модель угроз.
- [`docs/analytics.md`](docs/analytics.md) — продуктовая аналитика.
- [`docs/economics.md`](docs/economics.md) — экономическая модель (с честными `UNKNOWN` там, где нет реальных данных).
- [`docs/marketing-yandex.md`](docs/marketing-yandex.md) — маркетинговый пакет ArbitrPack для запуска через Яндекс Поиск.
- [`docs/deployment.md`](docs/deployment.md) — развёртывание на VPS, production checklist, rollback, backup.
- [`SECURITY.md`](SECURITY.md), [`PRIVACY.md`](PRIVACY.md), [`OFFER-DRAFT.md`](OFFER-DRAFT.md).
- [`docs/justicepack/baseline-audit.md`](docs/justicepack/baseline-audit.md) — аудит репозитория перед добавлением JusticePack, план изменений с обратной совместимостью.
- [`docs/justicepack/official-requirements.md`](docs/justicepack/official-requirements.md) — источники требований ГАС «Правосудие» (приказ № 251) с честной маркировкой и таблицей отличий от ArbitrPack.
- [`docs/justicepack/market-validation.md`](docs/justicepack/market-validation.md) — экономика и валидация спроса JusticePack (честные `UNKNOWN`).
- [`docs/justicepack/yandex-launch.md`](docs/justicepack/yandex-launch.md) — маркетинговый пакет JusticePack для Яндекс Поиск.

## CI

`.github/workflows/ci.yml`: backend-тесты против настоящего PostgreSQL-сервиса (включая проверку `alembic upgrade`/
`downgrade`), сборка и типизация frontend (`next build` включает проверку TypeScript), сборка и smoke-тест Docker
образов.

---

# Финальный отчёт (честно, без приукрашивания)

## Что реализовано и работает

- Полный вертикальный сценарий: загрузка нескольких файлов (drag-and-drop) → реальная техническая диагностика PDF
  (pypdf: повреждённость, шифрование, число страниц, эвристика пустых страниц) и изображений (Pillow: повреждённость,
  эвристика качества скана) → бесплатный отчёт с разделением на критические/предупреждения/рекомендации → оплата
  (mock, полностью функциональный тестовый режим ЮKassa на замоканных HTTP-вызовах) → идемпотентный webhook →
  сборка ZIP с безопасными автоисправлениями (удаление метаданных PDF и EXIF изображений) и защитой от zip-slip/
  zip-bomb → временная подписанная ссылка на скачивание → TTL-удаление.
- 73 автотеста (unit + integration + API: 49 ArbitrPack без изменений + 24 JusticePack), 90% покрытия строк
  backend, все прогнаны и зелёные в этой сессии.
- Docker Compose с PostgreSQL, MinIO, автоматическими health checks и прогоном Alembic-миграций перед стартом API.
- Две Alembic-миграции сгенерированы и протестированы (upgrade → downgrade → upgrade проходит для каждой): исходная
  схема и добавление `product_code` (с `server_default='ARBITRPACK'`, не требует бэкофилла).
- CI (GitHub Actions): backend против настоящего Postgres, frontend build+lint+typecheck, сборка и smoke-тест Docker образов.
- Playwright E2E: ДВА сквозных сценария (ArbitrPack, JusticePack + регрессия ArbitrPack через UI) — реально
  прогнаны против запущенных backend+frontend на этой машине, оба зелёные.
- Безопасность: allowlist форматов, MIME-по-содержимому, защита от двойных расширений и path traversal, rate
  limiting, secure headers, идемпотентные платежи с проверкой суммы/валюты, логи без содержимого документов
  (проверено тестом для обоих продуктов).
- Документация: источники требований с честной маркировкой VERIFIED/PARTIALLY VERIFIED/UNVERIFIED (для обоих
  приказов независимо), threat model, аналитика, экономическая модель-шаблон, маркетинговые пакеты ArbitrPack и
  JusticePack с честными UNKNOWN там, где нет реальных данных Яндекс.Вордстат/Директ.
- **JusticePack (второй аппарат) — реализован end-to-end:** независимый профиль правил
  (`config/rules/gas_pravosudie.yaml`, 9 правил GAS-R1..R9 с провенансом), `product_code` сквозным полем во всех
  таблицах (`UploadBatch`, `Payment`, `ProcessingJob`, `AnalyticsEvent`, `AuditEvent`) и во всех ключевых ответах
  API, независимый тариф, независимый маршрут `/services/justicepack`, экран выбора аппарата на `/`, изоляция
  статистики в `GET /api/admin/metrics` (обязательный `by_product` breakdown + опциональный строгий фильтр
  `?product_code=`), нулевая регрессия для ArbitrPack (все 49 исходных тестов и исходный E2E-сценарий проходят
  без изменений).

## Что протестировано, а что нет

**Протестировано реально (прогонами в этой сессии):** вся backend-логика валидации для ОБОИХ продуктов, платёжный
флоу на mock- и замоканном YooKassa-адаптере (независимо для ArbitrPack и JusticePack — отдельный тариф, отдельный
`product_code` в `Payment`/`ProcessingJob`), TTL-очистка, сборка архива и защита от zip-slip, безопасность логов
(включая новый тест на отсутствие имён файлов в audit-событиях JusticePack), миграции Alembic (upgrade/downgrade
для обеих миграций, включая добавление `product_code`), сборка frontend с проверкой типов (7 маршрутов, включая
новый `/services/justicepack`), ДВА полных сквозных сценария в браузере через Playwright (ArbitrPack и
JusticePack), изоляция аналитики между продуктами (проверено и unit-тестом, и вручную через `curl
/api/admin/metrics` против реально запущенного backend — см. коммит с этой сессией).

**НЕ протестировано (честно, это ограничения, а не "почти готово"):**

1. **Реальный API ЮKassa** — адаптер написан по официальной документации и протестирован на замоканных HTTP-ответах,
   но ни один реальный запрос к `api.yookassa.ru` не был выполнен, так как ключи тестового магазина не были
   предоставлены владельцем. Риск: реальный API может отличаться нюансами от документации на момент реальной
   интеграции — владельцу нужно пройти реальный тестовый платёж перед продакшеном (шаги — в `docs/deployment.md`).
2. **CI не запускался на реальном GitHub** (workflow-файл написан и синтаксически провалидирован локальными
   прогонами тех же команд, что в нём перечислены, но сам GitHub Actions runner в рамках этой сессии не вызывался —
   нет доступа к реальному репозиторию на GitHub).
3. **Docker Compose стек целиком** — в этой песочнице Docker-демон удалось запустить, но исходящий сетевой доступ к
   `registry-1.docker.io` заблокирован политикой окружения сессии (подтверждено: попытка `docker build` вернула
   403 от политики egress-прокси при попытке скачать базовый образ `python:3.12-slim`) — это ограничение среды
   разработки, а не проблема Dockerfile. Поэтому `docker build`/`docker compose up` не были физически прогнаны в
   этой сессии. Вместо этого весь сценарий (backend + frontend) реально запущен и протестирован Playwright
   напрямую (`uvicorn` + `next start`, без контейнеров) — см. выше. `docker compose config` (не требует сети —
   только парсинг YAML и интерполяция переменных) реально прогнан в этой сессии для обоих файлов —
   `docker-compose.yml` и `docker-compose.prod.yml` — и подтвердил корректность синтаксиса, интерполяции переменных
   и (для prod-файла) что порты Postgres/MinIO/API/Web действительно не публикуются наружу, а build-arg для
   `NEXT_PUBLIC_API_BASE_URL` у сервиса `web` корректно резолвится в реальный домен. **Честная поправка**: в
   предыдущей сессии здесь утверждалось, что Dockerfile'ы "проверены вручную на корректность путей и контекста
   сборки" — эта проверка была неполной. Независимый launch-readiness аудит (5 параллельных ревьюеров, отчёт в
   `docs/launch-readiness-review.md`) обнаружил реальный баг: `apps/api/Dockerfile` копировал `packages/`, но не
   `config/` — из-за этого JusticePack (правила которого лежат в `config/rules/gas_pravosudie.yaml`) отдавал бы 500
   на каждый запрос в любом контейнеризованном развёртывании, при этом полностью работая в режиме без Docker
   (`uvicorn` напрямую из чекаута репозитория, как и было реально протестировано Playwright выше) — то есть именно
   тот класс бага, который "docker build не запускался в песочнице" не мог поймать, а ручная проверка путей —
   пропустила. Исправлено (`COPY config ./config` добавлена в Dockerfile), и CI теперь дополнительно реально
   загружает файл через `/api/upload` для обоих `product_code` внутри собранного образа, а не только дёргает
   `/health` (см. `.github/workflows/ci.yml`) — чтобы этот класс регрессии стал видимым в CI, а не только в проде.
   `docker build`/`docker compose up` по-прежнему не были физически прогнаны в этой сессии (тот же egress-блок) —
   это первые команды, которые нужно выполнить владельцу на машине с доступом к Docker Hub (см. `docs/deployment.md`).
4. **Антивирусное сканирование** — не подключено (ClamAV), см. `SECURITY.md`.
5. **Требования приказа Судебного департамента № 252** (ArbitrPack) подтверждены двумя независимыми вторичными
   источниками (совпадающими дословно по цифрам), но не прочитаны из первоисточника КонсультантПлюс напрямую
   (платный доступ) — помечено `PARTIALLY VERIFIED` в `docs/requirements-sources.md`. Рекомендация владельцу —
   сверить перед реальным запуском.
6. **Требования приказа Судебного департамента № 251** (JusticePack) прочитаны через агрегатор sudact.ru, который
   в данном случае воспроизводит постатейный текст, а не только пересказ — помечено `PARTIALLY VERIFIED` (не
   `VERIFIED`, так как это не прямой доступ к pravo.gov.ru) в `docs/justicepack/official-requirements.md`.
   Рекомендация владельцу — сверить перед реальным запуском, как и для приказа № 252.
7. **Соответствие 152-ФЗ** — реализованы общепринятые технические меры (TTL, отсутствие ПДн в логах, согласие) для
   обоих продуктов, но это не юридическое заключение. Нужна консультация юриста (см. `PRIVACY.md`).
8. **JusticePack как отдельный бизнес** — willingness-to-pay для этой аудитории НЕ проверен (нет рекламного
   бюджета/реального трафика в рамках сессии) — см. `docs/justicepack/market-validation.md`, раздел 3, честно
   помечено `UNKNOWN`/`OWNER ACTION REQUIRED`. Тариф 399 ₽ — независимый от ArbitrPack плейсхолдер, не результат
   исследования цены для этой аудитории.
9. **SEO-страница-справочник** `/services/justicepack/trebovaniya`, упомянутая в market-validation.md как план —
   НЕ реализована в этой сессии (контентная работа сверх согласованного объёма вертикального среза JusticePack).

## Команды воспроизведения тестов

```bash
cd apps/api && source .venv/bin/activate
python -m pytest -q --cov=app --cov-report=term-missing   # → 73 passed, 90% coverage
cd ../../tests/e2e && npm install && npx playwright test   # требует запущенных backend (8000) и frontend (3000)
# → 3 passed: full-flow.spec.ts (ArbitrPack), justicepack-flow.spec.ts × 2 (JusticePack + регрессия ArbitrPack)
```

## OWNER ACTION REQUIRED (не может быть выполнено сессией)

- Домен (`baikalproject.pro`, reg.ru) и VPS (Timeweb Cloud, `201.24.54.96`) уже есть — осталось направить DNS
  A-запись на этот IP и открыть firewall на 22/80/443 (см. `docs/deployment.md`, шаги 2–3).
- Реальные ключи тестового/боевого магазина ЮKassa (общие для обоих продуктов, если не решено иначе).
- Доступ к рекламному кабинету Яндекс.Директ и Вордстату (для замены `UNKNOWN` в `docs/marketing-yandex.md` /
  `docs/economics.md` (ArbitrPack) и `docs/justicepack/yandex-launch.md` / `docs/justicepack/market-validation.md`
  (JusticePack) на реальные цифры — раздельно на продукт).
- Юридически значимые реквизиты для `OFFER-DRAFT.md` и `PRIVACY.md`, их проверка юристом (покрывает оба продукта).
- Подтверждение итоговых тарифов: 399 ₽ по умолчанию для ArbitrPack И независимо 399 ₽ по умолчанию для
  JusticePack — оба плейсхолдеры, оба требуют отдельного решения владельца.
- Willingness-to-pay тест для аудитории JusticePack (см. `docs/justicepack/market-validation.md`, раздел 3) — не
  может быть проведён сессией, требует реальных пользователей.
- Ручное прохождение полного сценария на продакшене для КАЖДОГО продукта перед запуском платной рекламы этого
  продукта (раздел 12 ТЗ ArbitrPack, аналогичное требование для JusticePack) — требует реального домена и
  реальных/тестовых платёжных ключей, которых сейчас нет.
- Юридическая/фактическая вычитка `docs/justicepack/official-requirements.md` перед публикацией любой SEO-страницы
  с пересказом приказа № 251.
- Решение о подключении ClamAV перед приёмом публичного трафика.
