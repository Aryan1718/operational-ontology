# Backend Implementation Plan

## File Purpose

This file is the implementation context for the backend of **Operational Ontology**.

The backend implements a Palantir Foundry Ontology-inspired operational layer for the supply-chain disruption response use case. It should expose business objects, relationships, derived functions, governed actions, permissions, execution history, and audit logs.

This is not a normal CRUD-only backend. The main backend behavior must pass through the ontology runtime.

---

## Backend Stack

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL
- pytest

The frontend remains Next.js/React and communicates with the backend through HTTP APIs.

---

## Main Backend Flow

```text
FastAPI Route
    ↓
ActorContext and Authorization
    ↓
Ontology Runtime
    ├── Object Runtime
    ├── Link Runtime
    ├── Function Engine
    └── Action Engine
    ↓
Repository Layer
    ↓
PostgreSQL
```

The ontology metadata file defines what exists. Python handlers define how functions and actions execute.

```text
ontology.yaml
    ↓
Ontology Loader
    ↓
Validated Ontology Registry
    ↓
Registered Python Handlers
```

---

## Backend Folder Structure

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── router.py
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── health.py
│   │       ├── ontology.py
│   │       ├── objects.py
│   │       ├── links.py
│   │       ├── functions.py
│   │       ├── actions.py
│   │       ├── action_executions.py
│   │       └── audit_logs.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── exceptions.py
│   │   ├── logging.py
│   │   └── security.py
│   │
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── seed.py
│   │
│   ├── models/
│   │   ├── supply_chain.py
│   │   ├── risk.py
│   │   ├── mitigation.py
│   │   ├── action_execution.py
│   │   └── audit_log.py
│   │
│   ├── schemas/
│   │   ├── common.py
│   │   ├── ontology.py
│   │   ├── objects.py
│   │   ├── functions.py
│   │   ├── actions.py
│   │   └── audit.py
│   │
│   ├── ontology/
│   │   ├── ontology.yaml
│   │   ├── loader.py
│   │   ├── registry.py
│   │   ├── validator.py
│   │   └── actor_context.py
│   │
│   ├── runtime/
│   │   ├── object_runtime.py
│   │   ├── link_runtime.py
│   │   ├── function_engine.py
│   │   ├── action_engine.py
│   │   └── authorization_service.py
│   │
│   ├── repositories/
│   │   ├── object_repository.py
│   │   ├── supply_chain_repository.py
│   │   ├── risk_repository.py
│   │   ├── mitigation_repository.py
│   │   ├── action_execution_repository.py
│   │   └── audit_repository.py
│   │
│   ├── functions/
│   │   ├── registry.py
│   │   ├── impact.py
│   │   ├── inventory.py
│   │   ├── ranking.py
│   │   └── mitigation.py
│   │
│   ├── actions/
│   │   ├── registry.py
│   │   ├── risk_actions.py
│   │   ├── mitigation_actions.py
│   │   ├── inventory_actions.py
│   │   ├── shipment_actions.py
│   │   └── purchase_order_actions.py
│   │
│   ├── services/
│   │   ├── audit_service.py
│   │   └── action_execution_service.py
│   │
│   └── mcp/
│       ├── server.py
│       └── tools.py
│
├── migrations/
│   └── versions/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── alembic.ini
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Folder Responsibilities

### `api/`

Contains FastAPI routes and request dependencies.

Routes must:

- accept and validate HTTP requests
- create or receive the `ActorContext`
- call the correct runtime or engine
- convert results into HTTP responses

Routes must not contain supply-chain business logic.

### `core/`

Contains application-wide configuration, security helpers, logging, and shared exceptions.

### `db/`

Contains SQLAlchemy database setup, sessions, and seed execution.

### `models/`

Contains SQLAlchemy database models for operational tables, risk events, mitigation plans, action executions, and audit logs.

### `schemas/`

Contains Pydantic request, response, ontology metadata, function, and action schemas.

Pydantic schemas should remain separate from SQLAlchemy models.

### `ontology/`

Contains the ontology metadata and startup logic.

Responsibilities:

- load `ontology.yaml`
- validate object, link, function, action, and permission definitions
- verify referenced handlers exist
- build one immutable ontology registry
- fail application startup when metadata is invalid

### `runtime/`

Contains the shared ontology execution layer.

#### Object Runtime

- fetch one ontology object
- search ontology objects
- map database records to ontology properties
- apply property projections and permissions

#### Link Runtime

- fetch linked objects
- validate link traversal
- resolve stored and derived relationships
- apply authorization to linked results

#### Function Engine

- authorize function execution
- validate inputs
- resolve the registered function handler
- execute read-only derived logic
- return validated output

Functions must not modify operational data.

#### Action Engine

- authorize action execution
- validate parameters
- enforce idempotency
- run business validation
- start database transactions
- lock records when required
- execute registered handlers
- record execution status
- create audit logs
- roll back all changes when execution fails

#### Authorization Service

One shared service must check:

- object access
- link traversal
- function execution
- action execution
- audit-log access
- AI/MCP tool access

### `repositories/`

Contains database queries and persistence logic.

Repositories must not make permission or workflow decisions.

### `functions/`

Contains registered read-only ontology function handlers.

Main groups:

- impact analysis
- inventory and supply calculations
- order ranking
- mitigation recommendation
- mitigation validation

### `actions/`

Contains registered governed action handlers.

Main groups:

- risk-event actions
- mitigation-plan lifecycle actions
- inventory reallocation
- shipment changes
- purchase-order changes

Handlers should contain action-specific rules. Shared transaction, idempotency, authorization, and audit behavior belongs in the Action Engine.

### `services/`

Contains shared supporting services that do not belong directly inside an ontology handler.

### `mcp/`

Contains the later AI/MCP integration.

The MCP layer must call the same ontology runtimes and engines used by the HTTP API. It must not bypass permissions or write directly to PostgreSQL.

---

## API Groups

```text
GET  /health

GET  /ontology
GET  /ontology/object-types
GET  /ontology/link-types
GET  /ontology/function-types
GET  /ontology/action-types

POST /objects/search
GET  /objects/{object_type}/{object_id}
GET  /objects/{object_type}/{object_id}/links
GET  /objects/{object_type}/{object_id}/available-actions

POST /functions/{function_name}/execute

POST /actions/{action_name}/execute
GET  /action-executions/{execution_id}

POST /audit-logs/search
```

POST may be used for search and execution requests containing larger or structured parameter bodies.

---

## Implementation Phases

### Phase 1: Backend Foundation

- initialize FastAPI project
- configure environment settings
- connect PostgreSQL
- configure SQLAlchemy and Alembic
- add shared errors, logging, and health endpoint
- seed the supplier-delay demo scenario

### Phase 2: Ontology Loader and Registry

- create Pydantic metadata schemas
- load `ontology.yaml`
- validate metadata references
- register function and action handlers
- fail startup for invalid definitions

### Phase 3: Actor Context and Permissions

- create trusted `ActorContext`
- implement roles such as viewer, planner, and admin
- create the shared Authorization Service
- separate authentication, authorization, and business validation

### Phase 4: Object and Link Runtime

- fetch objects through ontology metadata
- search objects using allowed properties
- return linked objects
- enforce permission-based projections

### Phase 5: Function Engine

Implement the shared engine first, then add the defined functions for:

- impacted parts
- impacted products
- impacted customer orders
- stockout risk
- alternative warehouses
- order ranking
- mitigation recommendation
- mitigation validation

### Phase 6: Action Engine

Implement the shared engine first, then add actions for:

- creating a risk event
- generating a mitigation plan
- submitting a mitigation plan
- approving or rejecting a mitigation plan
- executing mitigation steps
- reallocating inventory
- updating shipments
- expediting purchase orders

### Phase 7: Audit and Execution History

Every governed action should record:

- actor
- action type
- target object
- request parameters
- execution status
- previous values
- new values
- reason
- timestamp
- error details when failed

### Phase 8: API Routes

Create thin FastAPI routes over the completed runtimes and engines.

Do not create separate business logic inside route handlers.

### Phase 9: Complete Vertical Workflow

The first complete workflow must be:

```text
Supplier delay detected
→ create RiskEvent
→ find impacted parts
→ find impacted products
→ find impacted customer orders
→ check warehouse inventory
→ recommend mitigation
→ generate MitigationPlan
→ planner submits plan
→ authorized user approves plan
→ execute approved steps
→ update operational records
→ save execution history and audit logs
```

This workflow should work before expanding secondary features.

### Phase 10: MCP and AI Integration

Expose only approved ontology capabilities as MCP tools.

Initial safe tools:

- search objects
- get object
- get linked objects
- run read-only functions
- generate a draft mitigation recommendation

The AI must not directly approve plans, execute high-impact actions, or write to database tables.

---

## Testing Priorities

### Unit Tests

- ontology metadata validation
- permission decisions
- deterministic function results
- action parameter validation
- handler registration

### Integration Tests

- repository queries
- object and link mapping
- action transactions
- audit-log creation
- idempotent retries
- record locking and inventory concurrency

### End-to-End Tests

- full supplier-delay workflow
- unauthorized action rejection
- failed action rollback
- repeated request with the same idempotency key
- approved mitigation execution

---

## Important Implementation Rules

1. `ontology.yaml` describes the ontology; it does not execute business logic.
2. Python handlers implement functions and actions.
3. Functions are read-only.
4. Important writes must pass through the Action Engine.
5. API routes and MCP tools must use the same runtime.
6. Authorization must be checked before returning data or executing logic.
7. Action writes, execution history, and audit records must share one transaction.
8. Repeated action requests must be protected with idempotency keys.
9. Inventory-changing actions must use database locking where required.
10. The backend must fail during startup if ontology definitions or handler references are invalid.

---

## Recommended Build Order

```text
1. FastAPI foundation and PostgreSQL setup
2. Database migrations and demo seed
3. Ontology schemas, loader, validator, and registry
4. ActorContext and Authorization Service
5. Object Runtime
6. Link Runtime
7. Function Engine and function handlers
8. Action Engine and action handlers
9. Audit and action-execution history
10. FastAPI routes
11. Complete supplier-delay workflow
12. MCP integration
13. Final integration and end-to-end tests
```

---

## Backend Definition of Done

The backend MVP is complete when:

- ontology metadata loads and validates during startup
- users can inspect ontology definitions
- users can fetch objects and linked objects
- functions can calculate supply-chain impact
- governed actions enforce permissions and validation
- mitigation plans follow the defined lifecycle
- approved mitigation steps update operational records safely
- every important action creates execution and audit records
- the full supplier-delay scenario works end to end
