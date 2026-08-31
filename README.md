# Ontology-Driven Operations Reference

An independent reference implementation of a lightweight operational ontology inspired by Palantir Foundry Ontology concepts.

This repository demonstrates how supply-chain data can be modeled as connected business objects with typed properties, relationships, read-only functions, governed actions, permissions, execution evidence, audit history, and safe AI-accessible tools.

> [!IMPORTANT]
> This is not a Palantir product, clone, integration, or endorsed implementation. Palantir Foundry Ontology is used only as conceptual inspiration for building a smaller open-source operational layer.

## Reference Links

Conceptual inputs:

- [Palantir Foundry Ontology overview](https://www.palantir.com/docs/foundry/ontology/overview/)
- [Palantir Ontology core concepts](https://www.palantir.com/docs/foundry/ontology/core-concepts/)
- [Palantir Ontology system architecture](https://www.palantir.com/docs/foundry/architecture-center/ontology-system/)
- [Palantir Action Types overview](https://www.palantir.com/docs/foundry/action-types/overview/)
- [Palantir Ontology MCP overview](https://www.palantir.com/docs/foundry/ontology-mcp/overview/)
- [Model Context Protocol architecture](https://modelcontextprotocol.io/docs/learn/architecture)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

Project context:

- [agent.md](agent.md)
- [Ontology implementation context](docs/operational-ontology_ontology_implementation_context.md)
- [Backend implementation context](docs/operational-ontology_backend_implementation_context.md)
- [Database context](docs/operational-ontology_database_context.md)
- [AI and MCP integration context](docs/operational-ontology_ai_mcp_integration_design_context.md)

## What This Implements

The project focuses on a supply-chain disruption response workflow:

```text
Supplier delay detected
-> RiskEvent created
-> impacted Parts discovered
-> impacted Products discovered
-> impacted CustomerOrders discovered
-> available Inventory checked
-> mitigation options generated
-> MitigationPlan created
-> Planner submits the plan
-> Operations Manager approves or rejects the plan
-> approved mitigation steps execute
-> operational records change transactionally
-> actions and affected objects are audited
-> AI explains the recommendation and result
```

The important idea is that operational data is not exposed only as tables and generic CRUD endpoints. The ontology defines what objects mean, how they relate, what can be calculated, who can act, and which changes must be governed.

## Ontology Model

The ontology layer describes:

- business object types such as `Supplier`, `Part`, `Product`, `Warehouse`, `InventoryPosition`, `CustomerOrder`, `RiskEvent`, and `MitigationPlan`
- stored properties mapped to PostgreSQL tables and columns
- relationships between operational objects
- read-only functions for impact analysis, inventory availability, stockout risk, order ranking, and mitigation recommendation
- governed actions such as `createRiskEvent`, `generateMitigationPlan`, `approveMitigationPlan`, `reallocateInventory`, and `expeditePurchaseOrder`
- role-based permissions for `Viewer`, `Planner`, `OperationsManager`, `Admin`, and restricted `AIAgent`

The active ontology definition lives at:

- [backend/app/ontology/ontology.yaml](backend/app/ontology/ontology.yaml)

## Architecture

```text
PostgreSQL
  stores operational records, action executions, and audit evidence

Ontology YAML
  declares objects, links, functions, actions, roles, and permissions

FastAPI backend
  loads and validates ontology metadata, enforces authorization,
  executes read-only functions, dispatches governed actions, and records audit data

Next.js frontend
  provides the Ontology Manager and operational workspace surfaces

MCP / AI layer
  exposes approved ontology capabilities without allowing autonomous critical writes
```

> [!NOTE]
> Important writes should go through governed action routes. The system should not become unrestricted operational CRUD such as `PATCH /inventory/:id`.

## Current Implementation

Implemented repository surfaces include:

- FastAPI application startup with ontology registry loading
- Pydantic-based ontology metadata validation
- immutable ontology registry
- shared authorization service and permission registry
- object, link, function, action, action-execution, audit-log, assistant, and ontology API route groups
- registered function and action handler validation at startup
- PostgreSQL wiring through SQLAlchemy and Alembic
- deterministic seed command entry point
- MCP server wiring for approved ontology tools
- Next.js application shell for the Ontology Manager workspace
- Docker Compose stack for PostgreSQL, backend, and frontend

The reference implementation is still intended to remain narrow: a complete supplier-delay vertical slice is more valuable than many disconnected dashboard features.

## API Shape

The backend groups ontology behavior under `/api/v1`:

```text
GET  /health

GET  /api/v1/ontology/...
POST /api/v1/objects/...
GET  /api/v1/links/...
POST /api/v1/functions/...
POST /api/v1/actions/...
GET  /api/v1/action-executions/...
POST /api/v1/audit-logs/...
POST /api/v1/assistant/...
```

Function routes are for read-only operational insight. Action routes are for governed state changes with permission checks, validation, execution records, and audit evidence.

## Repository Structure

```text
backend/         FastAPI backend, ontology runtime, handlers, models, migrations
frontend/        Next.js Ontology Manager and workspace UI
docs/            implementation context for each system layer
infrastructure/  deployment and environment support
scripts/         setup, development, migration, seed, and test helpers
tests/           shared end-to-end test scaffolding
```

## Tech Stack

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL
- PyYAML
- MCP Python SDK
- Next.js 15
- React 18
- TypeScript
- Tailwind CSS
- TanStack Query
- React Flow
- pytest, Ruff, mypy, Vitest, Playwright

## Getting Started

Prerequisites:

- Python 3.12+
- Node.js 20+
- npm
- Docker and Docker Compose

Install dependencies:

```bash
./scripts/setup.sh
```

On Windows PowerShell:

```powershell
./scripts/setup.ps1
```

Run the full local stack:

```bash
docker compose up --build
```

Run services manually:

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm run dev
```

Local URLs:

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000>
- Health: <http://localhost:8000/health>
- API docs: <http://localhost:8000/docs>

## Common Commands

From the repository root:

```bash
make setup
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

## Implementation Boundaries

- PostgreSQL is the source of truth for operational state.
- Ontology YAML is the source of truth for metadata.
- Backend handlers contain executable business logic.
- Functions must remain read-only.
- Operational writes must go through governed actions.
- Permissions must be enforced server-side.
- AI may read, traverse, calculate, recommend, and draft when allowed.
- AI must not autonomously approve plans, execute plans, move inventory, expedite purchase orders, prioritize shipments, resolve risks, or publish ontology changes.

