SHELL := /bin/bash

.PHONY: setup dev up down logs backend frontend test lint format migrate seed

setup:
	./scripts/setup.sh

dev:
	./scripts/dev.sh

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

backend:
	cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

test:
	./scripts/test.sh

lint:
	cd backend && python -m ruff check .
	cd frontend && npm run lint

format:
	cd backend && python -m ruff format .
	cd frontend && npm run lint -- --fix

migrate:
	./scripts/migrate.sh

seed:
	./scripts/seed.sh
