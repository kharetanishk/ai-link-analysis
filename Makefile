.PHONY: help install dev-api dev-web test lint format build up down logs

help:            ## Show available commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install:         ## Install backend and frontend dependencies
	cd apps/api && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd apps/web && npm ci

dev-api:         ## Run the API with auto-reload on http://localhost:4000
	cd apps/api && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload

dev-web:         ## Run the UI with hot reload on http://localhost:5173
	cd apps/web && npm run dev

test:            ## Run lint and all tests
	cd apps/api && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/pytest -q
	cd apps/web && npm run typecheck

format:          ## Auto-format backend code
	cd apps/api && .venv/bin/ruff check --fix . && .venv/bin/ruff format .

build:           ## Build the Docker image
	docker compose build

up:              ## Start the app in Docker on http://localhost:4000
	docker compose up -d --build

down:            ## Stop the Docker app
	docker compose down

logs:            ## Follow the Docker app logs
	docker compose logs -f --tail=100
