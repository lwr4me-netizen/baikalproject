# Threat model — ArbitrPack

Дата: 2026-09-09. Модель по упрощённой STRIDE-методологии для MVP.

## Активы

1. Загруженные пользователем документы (потенциально содержат ПДн — ФИО, адреса, реквизиты дел).
2. Итоговые архивы (результат обработки).
3. Метаданные платежей (без данных карт — их обрабатывает ЮKassa, не ArbitrPack).
4. База данных (метаданные батчей, аналитика, аудит).
5. Секреты (ключи ЮKassa, admin-токен, secret_key приложения).

## Границы доверия

- Браузер пользователя ↔ Frontend (Next.js) — недоверенная сеть (интернет).
- Frontend ↔ Backend API — тот же периметр, но backend — единственная точка, которой доверяют операции с БД/хранилищем.
- Backend ↔ ЮKassa — внешний доверенный (в рамках PCI DSS ЮKassa) провайдер, взаимодействие по HTTPS + Basic Auth (shop_id/secret_key) + Idempotence-Key.
- Backend ↔ PostgreSQL/MinIO — внутренняя сеть Docker Compose, не выставлена наружу в production (см. docs/deployment.md).

## STRIDE по ключевым потокам

### 1. Загрузка файла

| Угроза | Реализованная защита |
|---|---|
| Spoofing MIME (подмена типа файла) | `python-magic` проверка содержимого + сверка с расширением (`mime_extension_mismatch`) |
| Tampering — path traversal через имя файла | `safe_filename()` нормализует, `os.path.basename`, storage backend дополнительно валидирует ключ |
| Tampering — двойное расширение (`invoice.pdf.exe`) | `has_double_extension()`, критическая ошибка, файл отклоняется |
| DoS — очень большой файл / много файлов (zip-bomb-подобная нагрузка на диск/CPU) | `max_file_size_mb=30`, `max_batch_size_mb=300`, `max_files_per_batch=50` — все из rules.yaml |
| DoS — флуд запросов на /api/upload | `slowapi` rate limit (`30/hour` на IP, конфигурируемо) |
| Information Disclosure — содержимое файла в логах | Структурированные логи (structlog) логируют только `event_type`, `batch_id`, счётчики — никогда имена файлов/контент (см. тесты `test_logs_do_not_contain_filenames`) |
| Repudiation — отсутствие журнала операций | `AuditEvent` на каждую значимую операцию (без контента) |

### 2. Формирование и выдача архива

| Угроза | Реализованная защита |
|---|---|
| Zip-slip (запись файла архива вне целевой директории при распаковке пользователем) | Все `arcname` нормализуются, отбрасываются `..`/абсолютные пути, добавляется порядковый префикс (`app/services/archive.py`); тест `test_archive_arcnames_never_contain_path_traversal` |
| Zip-bomb на выходе (чрезмерно большой распакованный размер) | Лимит `MAX_UNCOMPRESSED_TOTAL_BYTES=500MB` при сборке |
| Elevation of Privilege — скачивание чужого архива по предсказуемому URL | `DownloadToken`: случайный `secrets.token_urlsafe(32)`, хранится только SHA-256 хэш токена, TTL 15 минут (конфигурируемо), токен одноразового показа |
| Публичный доступ к бакету S3/MinIO | Bucket приватный, доступ только через backend (`boto3` с ключами приложения), presigned URL не используется напрямую для платных архивов — вместо этого собственный `DownloadToken`, что даёт контроль над TTL и отзывом |

### 3. Платежи

| Угроза | Реализованная защита |
|---|---|
| Spoofing webhook (злоумышленник шлёт поддельный `payment.succeeded`) | Backend НИКОГДА не доверяет телу webhook — всегда перезапрашивает `provider.get_status()` по официальному API ЮKassa (см. R-9 в requirements-sources.md) |
| Replay — повторная отправка одного и того же webhook | Идемпотентность через уникальный индекс `(provider, provider_payment_id, status)` в `ProcessedWebhookEvent` |
| Tampering суммы платежа | Backend сверяет `amount_value`/`currency` из `get_status()` с ожидаемыми значениями в собственной таблице `Payment` перед выдачей результата |
| Выдача платного результата без подтверждённой оплаты | `ProcessingJob` (платный, `is_paid_run=True`) создаётся только внутри обработчика webhook при `status == "succeeded"`; нет иного пути его создать |
| DoS на /api/payments/webhook | `slowapi` rate limit `120/minute` |
| Секреты ЮKassa в репозитории | Ключи только через переменные окружения (`.env`, не в git), `YooKassaConfigError` при отсутствии — приложение не стартует в режиме yookassa без ключей |

### 4. Хранение и удаление данных

| Угроза | Реализованная защита |
|---|---|
| Бессрочное хранение персональных данных | TTL обязателен при загрузке (24ч/72ч/168ч), `sweep_expired_batches()` запускается по расписанию (cron/systemd timer, см. deployment.md) |
| Пользователь не может удалить данные по требованию | `POST /api/batches/{id}/delete` — немедленное удаление, отдельный `AuditEvent(event_type="files_deleted")` |
| Утечка через резервные копии БД | docs/deployment.md: backup политика описывает, что бэкапится ТОЛЬКО схема/метаданные (без содержимого документов, которое живёт в S3/MinIO с собственным TTL, не входящим в бэкап БД) |

## Сетевые и инфраструктурные меры

- Secure HTTP-заголовки: `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`, `Strict-Transport-Security` (в production).
- Cookies сессии: `HttpOnly`, `SameSite=Lax`, `Secure` в production.
- CORS ограничен `ARBITRPACK_FRONTEND_BASE_URL` (никаких wildcard origin).
- PostgreSQL и MinIO не публикуются наружу в production docker-compose (см. deployment.md — порты закрываются на уровне firewall/compose override).
- Reverse proxy (Nginx/Caddy) терминирует TLS — инструкция в deployment.md.

## Явно не реализовано в MVP (риски, принимаемые сознательно)

- **Антивирусное сканирование** — интерфейс подготовлен (см. `app/validators/` можно расширить хуком перед `storage.put()`), но ClamAV не подключён физически в MVP: нет daemon в docker-compose. Помечено как `OWNER ACTION REQUIRED` в финальном отчёте — подключение `clamd` описано в deployment.md как рекомендация перед реальным запуском с публичным трафиком.
- **CSRF-токены** — состояние приложения не использует классические HTML-формы с cookie-based сессией для мутирующих действий за пределами upload/delete/payments, которые и так защищены `SameSite=Lax` + CORS allowlist; отдельный CSRF-токен не реализован в MVP. Оценка риска: низкая (нет сторонних доменов, которые могли бы инициировать кросс-сайтовые POST от имени пользователя с ощутимым ущербом, так как ключевые операции идемпотентны и не меняют состояние в пользу атакующего).
- **WAF / DDoS-защита на уровне сети** — вне периметра приложения, требует настройки на VPS/CDN владельцем.
