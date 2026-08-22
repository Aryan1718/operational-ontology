# Ontology-Driven Operational System Reference Implementation

This repository is an independent open-source reference implementation for an ontology-driven operational system focused on supply-chain disruption response.

It explores how raw operational data can be modeled as connected business objects, typed properties, governed actions, permissions, audit history, and later safe AI-accessible tools. The design is inspired by publicly documented ontology concepts, but this repository is not affiliated with, endorsed by, or integrated with Palantir.

## What This Repository Is For

The project is meant to demonstrate a narrow vertical slice of this workflow:

```text
Supplier delay detected
-> RiskEvent created
-> impacted Parts discovered
-> impacted Products discovered
-> impacted CustomerOrders discovered
-> available Inventory checked
-> mitigation options generated
-> MitigationPlan created
-> planner submits the plan
-> operations manager approves or rejects the plan
-> approved mitigation steps execute
-> operational records change transactionally
-> every action and affected object is audited
-> AI explains the recommendation and result
```

The main value is the ontology and operational layer, not a generic CRUD application.

## Core Principles

- PostgreSQL stores operational facts.
- Ontology metadata defines business meaning, relationships, functions, actions, and permissions.
- Read-only functions derive operational insight.
- Governed actions are the only path for important writes.
- Audit history records what changed, who changed it, and why.
- AI access must use approved ontology capabilities and must not bypass human approval.

## Current Status

The repository currently provides the project skeleton and development wiring for the backend, frontend, and local database. The full supply-chain workflow is documented in the repository context files but is not yet implemented end to end.

Implemented now:

- FastAPI backend startup and `GET /health`
- environment-based backend configuration
- Next.js application shell
- centralized frontend API client pattern
- Docker Compose setup for `postgres`, `backend`, and `frontend`
- local setup scripts and baseline tooling

Planned next layers:

- PostgreSQL-backed operational schema and deterministic seed data
- ontology metadata loader, validator, and immutable registry
- read-only ontology functions
- governed actions with authorization, idempotency, transactions, and audit
- read-only Ontology Manager
- MCP-based AI integration with `AIAgent` restrictions

## Technology Stack

Backend:

- Python 3.12+
- FastAPI
- Pydantic Settings
- SQLAlchemy
- Alembic
- PostgreSQL
- PyYAML
- MCP Python SDK

Frontend:

- Next.js 15
- React 18
- TypeScript
- Tailwind CSS
- TanStack Query
- React Hook Form
- Zod
- React Flow

Testing and tooling:

- pytest
- Ruff
- mypy
- Vitest
- React Testing Library
- Playwright
- Docker Compose

Source references:

- [backend/pyproject.toml](backend/pyproject.toml)
- [frontend/package.json](frontend/package.json)
- [docker-compose.yml](docker-compose.yml)

## Architecture Overview

The intended architecture keeps operational data, ontology metadata, runtime behavior, and AI access clearly separated:

```text
PostgreSQL
  = operational records and execution history

ontology/ontology.yaml
  = object types, properties, links, functions, actions, roles, permissions

backend handlers and runtime
  = validation, authorization, function execution, action execution, audit

frontend
  = read-only ontology understanding and governed operational workflows

MCP / AI layer
  = approved read and draft capabilities with human approval preserved
```

Important boundary:

- important writes should be expressed as governed actions such as `createRiskEvent`, `generateMitigationPlan`, or `approveMitigationPlan`
- this repository should not collapse into unrestricted endpoint-driven CRUD like `PATCH /inventory/:id`

## Repository Structure

```text
backend/         FastAPI application and planned ontology runtime
frontend/        Next.js application
docs/            implementation context and design documents
infrastructure/  deployment and environment support files
scripts/         local setup and helper scripts
tests/           end-to-end and shared test scaffolding
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- npm
- Docker and Docker Compose

### Install dependencies

Windows PowerShell:

```powershell
./scripts/setup.ps1
```

Shell:

```bash
./scripts/setup.sh
```

The setup script installs:

- backend package plus dev dependencies
- frontend npm dependencies

### Run locally without Docker

Start the backend:

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Start the frontend in a second shell:

```bash
cd frontend
npm run dev
```

Available local endpoints:

- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

### Run with Docker

```bash
docker compose up --build
```

The compose stack starts:

- `postgres`
- `backend`
- `frontend`

Migrations and seed data are not yet run automatically.

## Common Commands

From the repository root:

```bash
make up
make down
make logs
make backend
make frontend
make test
make lint
make format
make migrate
make seed
```

Source reference:

- [Makefile](Makefile)

## Documentation Map

The repository design is defined primarily in the `docs/` context files. Start with these:

- [agent.md](agent.md)
- [docs/operational-ontology_backend_implementation_context.md](docs/operational-ontology_backend_implementation_context.md)
- [docs/operational-ontology_frontend_application_design_context.md](docs/operational-ontology_frontend_application_design_context.md)
- [docs/operational-ontology_lightweight_ontology_manager_implementation_context.md](docs/operational-ontology_lightweight_ontology_manager_implementation_context.md)
- [docs/operational-ontology_ai_mcp_integration_design_context.md](docs/operational-ontology_ai_mcp_integration_design_context.md)
- [docs/operational-ontology_ontology_implementation_context.md](docs/operational-ontology_ontology_implementation_context.md)
- [docs/operational-ontology_database_context.md](docs/operational-ontology_database_context.md)
- [docs/deterministic_supply_chain_seed_data_implementation_context.md](docs/deterministic_supply_chain_seed_data_implementation_context.md)

These documents define the intended object model, runtime boundaries, action rules, permissions, frontend behavior, and AI safety model.

## External Reference Material

Conceptual ontology references:

- Palantir Ontology overview: <https://www.palantir.com/docs/foundry/ontology/overview/>
- Palantir Ontology core concepts: <https://www.palantir.com/docs/foundry/ontology/core-concepts/>
- Palantir Ontology system architecture: <https://www.palantir.com/docs/foundry/architecture-center/ontology-system/>
- Palantir Action Types overview: <https://www.palantir.com/docs/foundry/action-types/overview/>
- Palantir Ontology MCP overview: <https://www.palantir.com/docs/foundry/ontology-mcp/overview/>

MCP and agent references:

- Model Context Protocol architecture: <https://modelcontextprotocol.io/docs/learn/architecture>
- Model Context Protocol Python SDK: <https://github.com/modelcontextprotocol/python-sdk>
- OpenAI Agents SDK for Python: <https://openai.github.io/openai-agents-python/>

These references are conceptual inputs only. This repository implements its own smaller open-source architecture.

## Contributing

Before making changes:

- read [agent.md](agent.md)
- read the task-specific context document in `docs/`
- preserve the ontology, action, permission, and AI boundaries
- avoid unrelated refactors
- avoid turning the system into unrestricted operational CRUD

When contributing implementation changes, prefer updating the relevant context documents if repository contracts or paths materially change.

## License

No license file is currently present in the repository. Add one explicitly before treating the project as broadly redistributable.
