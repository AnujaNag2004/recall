.PHONY: setup dev-web dev-api up down lint typecheck test check gen-api check-ai pick-models eval seed e2e

setup:  ## Install all dependencies
	npm install
	cd apps/api && uv sync
	cd apps/mcp && uv sync

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
	cd apps/mcp && uv run pytest

check: lint typecheck test  ## Everything CI runs, except the production build

gen-api:  ## Regenerate the web app's API types from the FastAPI schema
	cd apps/api && PYTHONPATH=. uv run python scripts/export_openapi.py > ../web/src/lib/api/openapi.json
	cd apps/web && npx openapi-typescript src/lib/api/openapi.json -o src/lib/api/schema.d.ts

check-ai:  ## List the models your keys can use, and try each provider
	cd apps/api && PYTHONPATH=. uv run python scripts/check_ai.py

pick-models:  ## Fill the model ID settings in .env, from what your keys can use
	cd apps/api && PYTHONPATH=. uv run python scripts/pick_models.py

eval:  ## Measure the AI on labeled data. Needs real API keys, and takes a while.
	cd apps/api && PYTHONPATH=. uv run python evals/run_evals.py

seed:  ## Create the demo account's data. Needs DEMO_EMAIL set and that user to exist.
	cd apps/api && PYTHONPATH=. uv run python ../../supabase/seed/seed_demo.py

e2e:  ## Browser tests of the whole product on a local rig. No accounts needed.
	cd apps/web && npm run test:e2e
