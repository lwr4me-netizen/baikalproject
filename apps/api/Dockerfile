# Собирается с контекстом сборки = корень репозитория (см. docker-compose.yml),
# т.к. приложению нужен packages/validation-rules (профиль ARBITRPACK) и config/rules
# (профиль JUSTICEPACK), оба лежащие на уровень выше apps/api — см. app/products.py.
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY apps/api/requirements.txt ./apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt

COPY apps/api ./apps/api
COPY packages ./packages
COPY config ./config
COPY scripts ./scripts

WORKDIR /app/apps/api
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
