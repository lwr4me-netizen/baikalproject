SHELL := /bin/bash
API_DIR := apps/api
WEB_DIR := apps/web
VENV := $(API_DIR)/.venv

.PHONY: setup dev test lint e2e build up down clean-test-data migrate

setup: ## Установить все зависимости (backend + frontend), создать venv
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip -q
	$(VENV)/bin/pip install -r $(API_DIR)/requirements.txt -q
	cd $(WEB_DIR) && npm install --no-audit --no-fund
	@echo "Готово. Скопируйте .env.example в .env и заполните значения перед 'make up'."

dev: ## Запустить backend (uvicorn --reload) и frontend (next dev) локально без Docker
	@echo "Запустите в двух терминалах:"
	@echo "  1) cd $(API_DIR) && source .venv/bin/activate && ARBITRPACK_S3_USE_LOCAL_FALLBACK=true ARBITRPACK_PAYMENT_PROVIDER=mock uvicorn app.main:app --reload"
	@echo "  2) cd $(WEB_DIR) && npm run dev"

test: ## Прогнать backend-тесты с покрытием
	cd $(API_DIR) && source .venv/bin/activate && python -m pytest -q --cov=app --cov-report=term-missing

lint: ## Прогнать линтеры backend и frontend
	cd $(API_DIR) && source .venv/bin/activate && python -m py_compile $$(find app -name '*.py')
	cd $(WEB_DIR) && npm run lint

e2e: ## Прогнать сквозной сценарий (Playwright). Backend и frontend должны быть подняты (см. `make dev` или `make up`)
	cd tests/e2e && npm install --no-audit --no-fund && npx playwright test

build: ## Собрать Docker-образы
	docker compose build

up: ## Поднять весь стек (postgres, minio, api, web) и прогнать миграции
	docker compose up -d --build
	@echo "Frontend:  http://localhost:3000"
	@echo "API:       http://localhost:8000"
	@echo "API docs:  http://localhost:8000/docs"
	@echo "MinIO console: http://localhost:9001"

down: ## Остановить весь стек
	docker compose down

clean-test-data: ## Удалить тестовые данные (локальное хранилище, тестовая БД sqlite, __pycache__)
	rm -rf /tmp/arbitrpack-storage /tmp/arbitrpack-test-*
	rm -f $(API_DIR)/alembic_gen.db
	find . -type d -name __pycache__ -prune -exec rm -rf {} \;

migrate: ## Прогнать миграции Alembic локально (без Docker)
	cd $(API_DIR) && source .venv/bin/activate && alembic upgrade head
