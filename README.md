# Ontology-Inspired Operations Skeleton

This repository contains the initial full-stack skeleton for an ontology-inspired operational platform focused on supply-chain disruption response. The current phase establishes project structure, local development tooling, Docker-based startup, and a minimal working frontend-to-backend health integration.

The selected stack is:

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, pytest
- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS, TanStack Query, React Hook Form, Zod, React Flow, Vitest, React Testing Library, MSW, Playwright

## Current status

This phase includes only the monorepo skeleton and health-check integration.

Implemented now:

- FastAPI app startup and `GET /health`
- environment-based backend configuration and CORS setup
- Next.js application shell with placeholder routes
- centralized frontend API client and backend health query
- Docker Compose wiring for `postgres`, `backend`, and `frontend`
- repository scripts, Makefile commands, and baseline checks

Not implemented in this phase:

- supply-chain database models
- Alembic migration revisions
- deterministic seed records
- ontology definitions or runtime behavior
- function logic
- governed action logic
- authorization or authentication
- audit execution behavior
- MCP tools
- AI provider or assistant workflows

## Repository layout

```text
.
├── backend/
├── docs/
├── frontend/
├── infrastructure/
├── scripts/
├── tests/
│   └── e2e/
├── docker-compose.yml
├── Makefile
├── AGENTS.md
├── README.md
└── agent.md
```

## Context documents

Read the repository guidance in `agent.md`, then use the relevant files under `docs/`, including:

- `docs/operational-ontology_backend_implementation_context.md`
- `docs/operational-ontology_frontend_application_design_context.md`
- `docs/ontology_api_design_context.md`
- `docs/operational-ontology_ontology_implementation_context.md`
- `docs/operational-ontology_lightweight_ontology_manager_implementation_context.md`
- `docs/ontology_functions_implementation_context.md`
- `docs/ontology_actions_implementation_context.md`
- `docs/ontology_permissions_implementation_context.md`
- `docs/deterministic_supply_chain_seed_data_implementation_context.md`
- `docs/operational-ontology_ai_mcp_integration_design_context.md`
- `docs/operational-ontology_database_context.md`

## Prerequisites

- Python 3.12+
- Node.js 20+
- npm
- Docker and Docker Compose

## Environment setup

1. Copy `.env.example` to `.env` and adjust values as needed.
2. Copy `backend/.env.example` to `backend/.env` if you want backend-local overrides.
3. Copy `frontend/.env.example` to `frontend/.env.local` if you want frontend-local overrides.

## Local startup without Docker

1. Run `./scripts/setup.sh` or `./scripts/setup.ps1`.
2. Start the backend:

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. Start the frontend in a second shell:

```bash
cd frontend
npm run dev
```

Frontend: `http://localhost:3000`  
Backend: `http://localhost:8000`  
Health: `http://localhost:8000/health`  
Docs: `http://localhost:8000/docs`

## Docker startup

```bash
docker compose up --build
```

After startup:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/health`
- Docs: `http://localhost:8000/docs`

Migrations and seed data are intentionally not run automatically in Docker because those phases are not implemented yet.

## Test and quality commands

```bash
cd backend && python -m pytest
cd backend && python -m ruff check .
cd backend && python -m mypy .
cd frontend && npm run test
cd frontend && npm run lint
cd frontend && npm run typecheck
cd frontend && npm run build
docker compose config
```
