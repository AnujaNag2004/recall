.PHONY: setup dev-web dev-api up down lint typecheck test check

setup:  ## Install all dependencies
	npm install
	cd apps/api && uv sync

dev-web:  ## Run the web app on :3000
	npm run dev:web

dev-api:  ## Run the API on :8000
	cd apps/api && uv run uvicorn app.main:app --reload --port 8000

up:  ## Run the whole stack in Docker
	docker compose up --build

down:  ## Stop the Docker stack
	docker compose down

lint:
	npm run lint:web
	cd apps/api && uv run ruff check . && uv run ruff format --check .

typecheck:
	npm run typecheck:web
	cd apps/api && uv run mypy

test:
	npm run test:web
	npm run test:db
	cd apps/api && uv run pytest

check: lint typecheck test  ## Everything CI runs, except the production build
