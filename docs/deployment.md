# Развёртывание на VPS (production)

Этот документ покрывает раздел 16E ТЗ: инструкция VPS-развёртывания, production checklist, rollback plan,
backup policy, список необходимых аккаунтов/ключей.

**Оба продукта (ArbitrPack и JusticePack) разворачиваются этой же инструкцией** — это один backend-процесс, одна
БД, один frontend-контейнер; разделение чисто продуктовое, через `product_code`, а не через отдельную
инфраструктуру. Никаких дополнительных шагов деплоя для JusticePack не требуется сверх обычного `docker compose
up` — новый ruleset (`config/rules/gas_pravosudie.yaml`) уже часть образа `api` (`apps/api/Dockerfile` копирует
`config/` наравне с `packages/`; это было НЕ так до launch-readiness аудита этой сессии — первая версия
Dockerfile не копировала `config/`, из-за чего JusticePack отдавал 500 на каждый запрос в контейнере при полностью
рабочем dev-режиме без Docker; исправлено и с этого коммита проверяется отдельным шагом в CI, см.
`.github/workflows/ci.yml` — смок-тест теперь реально загружает файл с `product_code=JUSTICEPACK`, а не только
дёргает `/health`). Единственное функциональное отличие — production checklist ниже теперь нужно пройти по разу
на КАЖДЫЙ продукт (два отдельных тарифа, два отдельных ручных прохождения сценария).

## 1. Реквизиты этого развёртывания (заполнено по факту)

| Параметр | Значение |
|---|---|
| Домен | `baikalproject.pro` (reg.ru) |
| VPS | Timeweb Cloud, проект `BAIKALPRODESIGN` |
| Публичный IPv4 | `201.24.54.96` |
| Требуется от VPS | Docker + Docker Compose plugin (`docker compose version` ≥ v2), открытые порты 80/443 |

## 2. Шаг 1 — DNS (сделать один раз, на reg.ru)

В личном кабинете reg.ru → домен `baikalproject.pro` → «Управление DNS» → добавить записи:

```
A     @      201.24.54.96
A     www    201.24.54.96      (необязательно, если хотите, чтобы www тоже открывался)
```

Проверить, что запись применилась (может занять от нескольких минут до нескольких часов):

```bash
nslookup baikalproject.pro
# или на самом сервере, после SSH:
dig +short baikalproject.pro
```

Caddy (шаг 4 ниже) не выпустит HTTPS-сертификат, пока DNS не укажет на сервер, — остальные шаги можно готовить
параллельно, а перезапуск `caddy` с реальным сертификатом сделать, когда DNS применится.

## 3. Шаг 2 — открыть порты на сервере (Timeweb)

На скриншоте вашей панели видно, что группа правил Firewall ещё не создана. Зайдите в проект → сервер
`BAIKALPRODESIGN` → вкладка «Сеть» → Firewall → «Настроить» и создайте группу с разрешёнными входящими:

```
TCP 22    — SSH (по возможности ограничьте источник вашим IP)
TCP 80    — HTTP (нужен для выпуска сертификата Let's Encrypt)
TCP 443   — HTTPS
```

Всё остальное (5432, 9000, 9001, 8000, 3000) наружу открывать не нужно — в `docker-compose.prod.yml` (см. ниже)
эти порты и так не публикуются на хост, доступ к ним только изнутри Docker-сети.

## 4. Шаг 3 — код на сервер и первый запуск

Откройте вкладку «Консоль» в панели Timeweb (браузерный терминал, SSH-клиент не нужен) и выполните:

```bash
# 1. Установить Docker (официальный скрипт работает и на Ubuntu, и на Debian)
curl -fsSL https://get.docker.com | sh
docker compose version   # проверка, что плагин compose встал

# 2. Получить код проекта. Проще всего — с вашего компьютера, куда вы скачали архив из чата:
#    scp arbitrpack.zip root@201.24.54.96:/root/
#    (выполняется в терминале ВАШЕГО компьютера, не в консоли Timeweb)
# Затем здесь, в консоли Timeweb:
apt-get update && apt-get install -y unzip
cd /root && unzip arbitrpack.zip && cd arbitrpack

# 3. Настроить .env
cp .env.example .env
ARBITRPACK_SECRET_KEY=$(openssl rand -hex 32)
ARBITRPACK_ADMIN_TOKEN=$(openssl rand -hex 24)
POSTGRES_PW=$(openssl rand -hex 16)
MINIO_PW=$(openssl rand -hex 16)
sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PW}|" .env
sed -i "s|MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=${MINIO_PW}|" .env
sed -i "s|ARBITRPACK_SECRET_KEY=.*|ARBITRPACK_SECRET_KEY=${ARBITRPACK_SECRET_KEY}|" .env
sed -i "s|ARBITRPACK_ADMIN_TOKEN=.*|ARBITRPACK_ADMIN_TOKEN=${ARBITRPACK_ADMIN_TOKEN}|" .env
sed -i "s|ARBITRPACK_FRONTEND_BASE_URL=.*|ARBITRPACK_FRONTEND_BASE_URL=https://baikalproject.pro|" .env
sed -i "s|ARBITRPACK_API_BASE_URL=.*|ARBITRPACK_API_BASE_URL=https://baikalproject.pro|" .env
sed -i "s|NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=https://baikalproject.pro|" .env
cat .env | grep -v PASSWORD | grep -v SECRET | grep -v TOKEN   # быстрая визуальная проверка не-секретных значений

# 4. Поднять прод-стек (используется docker-compose.prod.yml — без публикации портов БД/MinIO/API/Web наружу)
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f api   # Ctrl+C когда увидите "arbitrpack_api_started"
```

Первый запуск `caddy` выпустит сертификат Let's Encrypt автоматически, как только DNS из шага 2 применится и порты
80/443 открыты. Проверка:

```bash
curl -I https://baikalproject.pro
```

**Примечание по маршрутизации:** в `infrastructure/docker/Caddyfile` под `/api/*` уходит на `api:8000`, всё
остальное — на `web:3000`. Эндпоинт `/health` у API не имеет префикса `/api`, поэтому в проде извне он не проксируется
Caddy намеренно (это внутренняя диагностика, а не публичный API) — проверяйте здоровье API изнутри сервера:
`docker compose -f docker-compose.prod.yml exec api curl -f http://localhost:8000/health`.

## 5. Переключение на ЮKassa (после mock-провайдера)

1. Зарегистрировать тестовый магазин: https://yookassa.ru/my/onboarding/testing
2. Получить `shopId` и `secretKey` в личном кабинете.
3. В `.env` на сервере: `ARBITRPACK_PAYMENT_PROVIDER=yookassa`, `ARBITRPACK_YOOKASSA_SHOP_ID=...`, `ARBITRPACK_YOOKASSA_SECRET_KEY=...`
4. В личном кабинете ЮKassa указать URL webhook: `https://baikalproject.pro/api/payments/webhook`
5. `docker compose -f docker-compose.prod.yml up -d --build api` (перезапуск api с новыми переменными).
6. Пройти полный сценарий тестовой оплатой (тестовая карта из документации ЮKassa) перед переключением на боевой магазин.
7. Только после этого запрашивать боевой (production) магазин у ЮKassa — отдельная процедура верификации юрлица/ИП,
   выполняется владельцем.

**OWNER ACTION REQUIRED:** реальные ключи ЮKassa, верификация магазина — не может быть выполнено сессией.

## 6. Production checklist

- [ ] `.env` заполнен реальными секретами, файл не в git (`.gitignore` уже это обеспечивает).
- [ ] Развёрнуто через `docker-compose.prod.yml` (не `docker-compose.yml`, который для локальной разработки и
      публикует порты БД/MinIO/API/Web на хост) — тогда `ARBITRPACK_ENVIRONMENT=production` уже выставлен внутри
      файла, порты постгреса/MinIO/api/web наружу не торчат, а TTL-демон включён по умолчанию (см. пункт ниже).
- [ ] HTTPS настроен и работает (`curl -I https://baikalproject.pro` → 200) — сертификат Caddy выпускается сам при
      условии, что DNS уже применился и 80/443 открыты в firewall (шаги 2–3 выше).
- [ ] `ARBITRPACK_FRONTEND_BASE_URL`/`ARBITRPACK_API_BASE_URL`/`NEXT_PUBLIC_API_BASE_URL` указывают на
      `https://baikalproject.pro` (в `docker-compose.prod.yml` `NEXT_PUBLIC_API_BASE_URL` для сборки фронтенда
      берётся из `ARBITRPACK_FRONTEND_BASE_URL` — держите их одинаковыми в `.env`).
- [ ] TTL-очистка работает — в `docker-compose.prod.yml` сервис `ttl-cleanup` запускается автоматически (без
      `--profile`, в отличие от dev-файла) и крутится в фоне каждые 15 минут.
- [ ] Backup PostgreSQL настроен (см. ниже).
- [ ] Пройден полный ручной сценарий на проде ДЛЯ КАЖДОГО продукта отдельно: выбор аппарата → загрузка →
      диагностика → тестовая оплата → обработка → скачивание → удаление (ArbitrPack `/upload` и JusticePack
      `/services/justicepack`).
- [ ] `GET /api/admin/metrics?product_code=ARBITRPACK` и `?product_code=JUSTICEPACK` проверены отдельно —
      статистика не смешана (см. `by_product` в ответе без параметра).
- [ ] Оферта и политика конфиденциальности проверены юристом и содержат реальные реквизиты (см. `OFFER-DRAFT.md`, `PRIVACY.md`).
- [ ] `ARBITRPACK_ADMIN_TOKEN` — длинная случайная строка, известна только владельцу.

## 7. Rollback plan

1. Каждый деплой — отдельный git-тег/коммит. Перед деплоем зафиксировать текущий работающий коммит:
   `git rev-parse HEAD > /opt/arbitrpack/.last_good_commit`
2. Если новый деплой сломан:
   ```bash
   cd /opt/arbitrpack
   git checkout $(cat .last_good_commit)
   docker compose -f docker-compose.prod.yml up -d --build
   ```
3. Миграции Alembic пишутся с рабочим `downgrade()` (автогенерация Alembic создаёт его автоматически) — при
   необходимости отката схемы: `docker compose run --rm api alembic downgrade -1`. **Внимание**: откат схемы вниз
   при уже накопленных данных может быть разрушительным — предпочтительно откатывать код, а не схему, если
   миграция только добавляла таблицы/колонки.
4. Хранить резервную копию `.env` и `docker-compose.prod.yml` предыдущей рабочей версии вне репозитория (например,
   в защищённом менеджере секретов), т.к. `.env` не в git.

## 8. Backup policy

**Что бэкапится:** только PostgreSQL (метаданные — батчи, платежи, аналитика, аудит). Пользовательские документы
и итоговые архивы **намеренно не входят в backup** — они и так подлежат TTL-удалению, и создание резервных копий
персональных данных пользователей увеличивало бы поверхность риска без явной пользы (пользователь не ожидает, что
удалённый им файл "всплывёт" из бэкапа).

```bash
# Ежедневный дамп (пример cron-задачи на хосте, вне контейнера)
0 3 * * * docker exec arbitrpack-postgres-1 pg_dump -U arbitrpack arbitrpack | gzip > /opt/backups/arbitrpack_$(date +\%F).sql.gz
# Ротация: хранить 14 дней
find /opt/backups -name 'arbitrpack_*.sql.gz' -mtime +14 -delete
```

**OWNER ACTION REQUIRED:** решить, где хранить бэкапы (отдельный сервер/S3 вне основного MinIO) и настроить
шифрование бэкапов при хранении вне сервера.

## 9. Список необходимых аккаунтов и ключей (сводка)

| Что | Кто предоставляет | Статус |
|---|---|---|
| Домен | `baikalproject.pro` (reg.ru) — зарегистрирован | OWNER ACTION REQUIRED: добавить A-запись `@` → `201.24.54.96` (шаг 2 выше) |
| VPS | Timeweb Cloud, `201.24.54.96`, проект `BAIKALPRODESIGN` — уже поднят | OWNER ACTION REQUIRED: firewall (шаг 3) + первый деплой (шаг 4) |
| Тестовый магазин ЮKassa (shopId/secretKey) | владелец, регистрация на yookassa.ru | OWNER ACTION REQUIRED |
| Боевой магазин ЮKassa (после верификации юрлица/ИП) | владелец | OWNER ACTION REQUIRED |
| Аккаунт Яндекс.Директ + доступ к Вордстату | владелец | OWNER ACTION REQUIRED |
| Юридически значимые реквизиты для оферты (наименование, ОГРНИП/ОГРН, адрес) | владелец | OWNER ACTION REQUIRED |
| Подтверждение тарифа (цена 399 ₽ или другая) | владелец | OWNER ACTION REQUIRED |
| ARBITRPACK_ADMIN_TOKEN, ARBITRPACK_SECRET_KEY, пароли Postgres/MinIO | генерируются автоматически (`openssl rand`), но должны быть сохранены владельцем в менеджере секретов | можно сделать сейчас |
