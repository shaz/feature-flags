# control-plane developer tasks.
# DATABASE_URL is used by migrations + the app for local runs.
DATABASE_URL ?= postgresql://fubo_flags:localdev@localhost:5432/fubo_flags
export DATABASE_URL

.PHONY: install db-up db-down migrate run test lint build

install:
	pip install -e ".[dev]"

db-up:                ## start local Postgres
	docker compose up -d

db-down:
	docker compose down

migrate:              ## apply migrations to DATABASE_URL
	bash ../migrations/apply.sh

run:                  ## run the API (expects db-up + migrate first)
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

test:
	pytest -q

lint:
	ruff check .

build:                ## build the container image
	docker build -f ../docker/control-plane.Dockerfile -t fubo-flags-control-plane ..
