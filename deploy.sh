#!/usr/bin/env bash
# Автоматический деплой BAIKALPROJECT (ArbitrPack + JusticePack) на чистый VPS.
# Запускается НА СЕРВЕРЕ, из корня распакованного репозитория (там же, где docker-compose.prod.yml).
# Соответствует шагам из docs/deployment.md, раздел 4 ("Шаг 3 — код на сервер и первый запуск").
set -e

cd "$(dirname "$0")"

echo "=== 1. Проверка/установка Docker ==="
if ! command -v docker &> /dev/null; then
  echo "Docker не найден — устанавливаю официальным скриптом..."
  curl -fsSL https://get.docker.com | sh
else
  echo "Docker уже установлен."
fi
docker compose version

echo ""
echo "=== 2. Настройка .env ==="
if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env создан из .env.example."
else
  echo ".env уже существует — не пересоздаю, только проверю обязательные поля ниже."
fi

# Генерируем секреты только если в .env всё ещё стоят плейсхолдеры из .env.example
# (повторный запуск скрипта не перегенерирует уже настоящие секреты).
if grep -q "POSTGRES_PASSWORD=change-me" .env 2>/dev/null; then
  POSTGRES_PW=$(openssl rand -hex 16)
  sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${POSTGRES_PW}|" .env
  echo "POSTGRES_PASSWORD сгенерирован."
fi
if grep -q "MINIO_ROOT_PASSWORD=change-me" .env 2>/dev/null; then
  MINIO_PW=$(openssl rand -hex 16)
  sed -i "s|MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=${MINIO_PW}|" .env
  echo "MINIO_ROOT_PASSWORD сгенерирован."
fi
if grep -q "ARBITRPACK_SECRET_KEY=change-me" .env 2>/dev/null; then
  SECRET_KEY=$(openssl rand -hex 32)
  sed -i "s|ARBITRPACK_SECRET_KEY=.*|ARBITRPACK_SECRET_KEY=${SECRET_KEY}|" .env
  echo "ARBITRPACK_SECRET_KEY сгенерирован."
fi
if grep -q "ARBITRPACK_ADMIN_TOKEN=change-me" .env 2>/dev/null; then
  ADMIN_TOKEN=$(openssl rand -hex 24)
  sed -i "s|ARBITRPACK_ADMIN_TOKEN=.*|ARBITRPACK_ADMIN_TOKEN=${ADMIN_TOKEN}|" .env
  echo "ARBITRPACK_ADMIN_TOKEN сгенерирован."
fi

sed -i "s|ARBITRPACK_FRONTEND_BASE_URL=.*|ARBITRPACK_FRONTEND_BASE_URL=https://baikalproject.pro|" .env
sed -i "s|ARBITRPACK_API_BASE_URL=.*|ARBITRPACK_API_BASE_URL=https://baikalproject.pro|" .env
sed -i "s|NEXT_PUBLIC_API_BASE_URL=.*|NEXT_PUBLIC_API_BASE_URL=https://baikalproject.pro|" .env

echo ""
echo "=== ВАЖНО: сохраните секреты из .env в свой менеджер паролей (они не выводятся тут на экран) ==="
echo "Посмотреть их можно в любой момент командой:  cat $(pwd)/.env"

echo ""
echo "=== 3. Запуск production-стека (docker-compose.prod.yml) ==="
docker compose -f docker-compose.prod.yml up -d --build

echo ""
echo "=== 4. Ждём 15 секунд и проверяем статус контейнеров ==="
sleep 15
docker compose -f docker-compose.prod.yml ps

echo ""
echo "=== ГОТОВО ==="
echo "Если все контейнеры в статусе 'Up' — сервис поднят."
echo "HTTPS-сертификат Caddy выпустит автоматически, как только DNS на baikalproject.pro укажет на этот сервер"
echo "(проверить: curl -I https://baikalproject.pro)."
echo "Здоровье API изнутри сервера: docker compose -f docker-compose.prod.yml exec api curl -f http://localhost:8000/health"
