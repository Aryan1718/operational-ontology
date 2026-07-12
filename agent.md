# Agent Instructions

## 1. Purpose

This file gives coding agents the minimum project context, source-of-truth rules, implementation boundaries, and document map required to work safely in this repository.

Read this file before making changes. Then read the task-specific context document identified below before writing code.

---

## 2. Project naming rule

The project name has **not been decided**.

Do not invent or assume a product name. Use neutral terms such as:

- the project
- the system
- the platform
- the application
- the ontology layer
- the Ontology Manager

Some existing context filenames contain an earlier temporary project-name prefix. That prefix is only a legacy filename and is **not** an approved product name.

Do not use the temporary name in:

- application titles
- UI labels
- package names
- API namespaces
- database names
- environment variables
- README positioning
- code comments that describe the product

Do not rename existing context files unless explicitly requested, because other prompts or scripts may still reference their current paths.

---

## 3. Project overview

This project is a lightweight, open-source operational data system inspired by the core concepts demonstrated by Palantir Foundry Ontology.

It is **not** a Palantir clone and must not claim an official Palantir integration.

The purpose is to learn and demonstrate how raw operational data can become:

```text
business objects
+ typed properties
+ relationships
+ derived functions
+ governed actions
+ permissions
+ audit history
+ safe AI-accessible tools
```

The selected use case is **supply-chain disruption response**.

The system should help operators understand and respond to questions such as:

- Which parts are affected by a supplier delay?
- Which products depend on those parts?
- Which customer orders are at risk?
- Which warehouses have alternative inventory?
- Which purchase orders can be expedited?
- Which mitigation option should be recommended?
- Which human role must approve the proposed action?
- What changed after an approved action executed?

The main value of the project is the ontology and operational layer, not a generic dashboard or CRUD application.

---

## 4. Core workflow

The primary end-to-end scenario is:

```text
Supplier delay detected
â†’ RiskEvent created
â†’ impacted Parts discovered
â†’ impacted Products discovered
â†’ impacted CustomerOrders discovered
â†’ available Inventory checked
â†’ mitigation options generated
â†’ MitigationPlan created
â†’ Planner submits the plan
â†’ Operations Manager approves or rejects the plan
â†’ approved mitigation steps execute
â†’ operational records change transactionally
â†’ every action and affected object is audited
â†’ AI explains the recommendation and result
```

A narrow, complete vertical slice of this workflow is more valuable than many disconnected features.

---

## 5. Important system distinction

This must not become a normal application whose business behavior is represented only by endpoints such as:

```text
GET /orders
PATCH /inventory/:id
PATCH /purchase-orders/:id
```

Read APIs may retrieve operational objects, but important writes must be expressed as governed business actions, for example:

```text
POST /actions/createRiskEvent
POST /actions/generateMitigationPlan
POST /actions/approveMitigationPlan
POST /actions/reallocateInventory
POST /actions/expeditePurchaseOrder
```

The ontology must describe what an object means, how it connects to other objects, which functions may be run, which actions are available, which roles may use them, and how execution is audited.

---

## 6. System boundaries

Preserve the following separation of responsibilities.

### PostgreSQL

PostgreSQL stores runtime and operational records:

- suppliers, parts, products, and warehouses
- relationship and bill-of-material records
- inventory positions
- customer orders and order lines
- shipments
- purchase orders and purchase-order lines
- risk events
- mitigation plans and steps
- inventory transfers
- action executions
- audit records
- optional AI tool-call history

PostgreSQL is the source of truth for actual business state. It is not the source of truth for ontology metadata in Version 1.

### `ontology/ontology.yaml`

The YAML file stores declarative ontology metadata:

- ontology identity and version
- object types
- stored and derived properties
- backing table and column mappings
- link types
- functions
- governed actions
- parameters and validation metadata
- state transitions
- roles and permissions
- audit, transaction, idempotency, and AI restrictions
- UI labels, categories, icons, and ordering

The YAML must not contain executable application code.

### Backend handlers

Backend code implements:

- ontology function handlers
- action handlers
- parameter and state validation
- authorization
- transaction boundaries
- idempotency enforcement
- audit recording
- handler registration
- MCP tool adapters

Stable handler names in the YAML must resolve to registered backend implementations.

### Ontology runtime

The runtime is responsible for:

- loading and validating the YAML
- normalizing metadata
- registering resources
- resolving handlers
- querying object metadata
- traversing stored and derived links
- running functions
- authorizing actions
- dispatching actions
- recording execution and audit history
- exposing safe capabilities to the MCP layer

### Ontology Manager

Version 1 of the Ontology Manager is a **read-only control-plane interface** for understanding ontology metadata.

It may explain, search, index, and visualize ontology resources. It must not edit metadata, execute operational functions, execute actions, or display actual operational object records in Version 1.

### Object Explorer

The Object Explorer is a separate future or later application surface for inspecting actual object instances, links, available actions, and audit history.

Do not merge Object Explorer behavior into the Version 1 Ontology Manager.

### MCP and AI layer

The AI layer may safely read objects, traverse approved links, run approved read-only functions, and draft recommendations or mitigation plans.

The AI agent must not autonomously approve or execute critical operational actions.

---

## Project document index

Read only the document relevant to the current task. These files contain detailed implementation context; this file contains only routing guidance.

<!-- BEGIN MANAGED: PROJECT-DOC-REFERENCES -->
- `docs/operational-ontology_database_context.md` — Read for PostgreSQL schema, constraints, migration scope, indexes, and seed-data compatibility.
- `docs/operational-ontology_ontology_implementation_context.md` — Read for ontology metadata, YAML structure, runtime contracts, handlers, permissions, and action rules.
- `docs/ontology_permissions_implementation_context.md` — Read for shared authorization rules across objects, links, functions, actions, audit history, and AI tools.
- `docs/ontology_api_design_context.md` — Read for API routes, request contracts, response shapes, pagination, and controller boundaries.
- `docs/ontology_functions_implementation_context.md` — Read for read-only ontology function behavior, traversal logic, calculations, and handler testing boundaries.
- `docs/ontology_actions_implementation_context.md` — Read for governed action execution, transactions, idempotency, audit rules, and action-handler contracts.
- `docs/operational-ontology_lightweight_ontology_manager_implementation_context.md` — Read for read-only Ontology Manager APIs, UI behavior, validation views, and testing scope.
<!-- END MANAGED: PROJECT-DOC-REFERENCES -->
---

## 8. Source-of-truth and conflict rules

Use the most specific document for the layer being changed.

Use the project document index above to choose the task-specific source of truth.

General precedence:

1. The user's current explicit request.
2. The task-specific implementation context file.
3. This `AGENT.md` file.
4. Existing repository patterns and conventions.
5. General project background.

Do not silently resolve a real contradiction by inventing behavior.

Before treating two statements as conflicting, verify whether they concern different layers. For example:

- PostgreSQL stores operational records.
- YAML stores ontology metadata.

These statements are complementary, not contradictory.

When a task-specific document references a file or component that has already been implemented, inspect and reuse the existing implementation rather than creating a parallel version.

---

## 9. Mandatory implementation rules

### 9.1 Writes through governed actions

Do not create generic write paths for operationally important state.

Actions that write data must:

- authenticate the actor
- authorize the actor and role
- validate parameters
- validate current object state
- enforce documented state transitions
- run transactionally
- support idempotency where required
- record action execution status
- record affected objects
- record before and after values
- record changed fields
- record failure details
- record the ontology/action definition version
- avoid partial writes

### 9.2 AI safety boundary

The `AIAgent` role may inspect data, traverse approved links, run approved read-only functions, and generate draft recommendations when permitted.

It must not independently:

- approve a mitigation plan
- reject a mitigation plan on behalf of a human
- execute a mitigation plan
- move inventory
- expedite a purchase order
- prioritize a shipment
- resolve a risk event
- publish ontology changes

Human approval must remain explicit for critical actions.

### 9.3 Ontology validation

Application startup must fail on fatal ontology errors, including:

- duplicate resource keys
- unknown object types or properties
- invalid title properties
- invalid link endpoints or cardinalities
- unknown function or action references
- unknown roles or handlers
- invalid state transitions
- derived properties or links without resolvers
- enum properties without enum values
- prohibited critical permissions for `AIAgent`

Non-fatal quality warnings may be displayed in the manager validation view.

### 9.4 No duplicated ontology definitions

Do not hardcode a second object, action, function, role, or permission registry in frontend code.

Counts, labels, tables, handlers, permissions, graph edges, and settings shown by the manager must come from the loaded registry.

### 9.5 Reuse the repository

Before adding infrastructure, inspect the repository for:

- selected frontend and backend frameworks
- authentication middleware
- API conventions
- validation libraries
- database tooling
- ontology loader and registry
- UI component library
- graph dependencies
- test framework
- lint and formatting rules

Extend existing layers. Do not create a parallel application or duplicate infrastructure.

### 9.6 Avoid unrelated changes

Do not:

- upgrade unrelated dependencies
- reformat unrelated files
- rename broad parts of the repository
- add speculative abstractions
- add future-phase features to Version 1
- fabricate analytics or validation warnings for the demo

---

## 10. Preferred technical direction

Follow existing repository choices first.

When the repository has not made a decision, prefer:

```text
Language: TypeScript
Frontend: Next.js App Router and React
Styling: existing Tailwind setup or existing design system
Backend: existing Node.js service or Next.js server routes
Database: PostgreSQL
Validation: Zod
YAML parsing: a safe YAML parser
Graph visualization: existing graph library or React Flow
Testing: existing unit/integration framework and Playwright for key UI flows
AI integration: MCP tools backed by ontology services
```

The architecture is more important than the specific framework. Do not replace a working repository choice merely to match these preferences.

---

## 11. Recommended implementation order

For a new or incomplete repository, work in this order unless the current task says otherwise:

1. Inspect repository structure and existing conventions.
2. Implement or verify PostgreSQL migrations.
3. Add representative seed data for the disruption scenario.
4. Implement `ontology/ontology.yaml`.
5. Implement strict schema and semantic validation.
6. Implement the immutable ontology registry and handler registry.
7. Implement object reads and link traversal.
8. Implement read-only ontology functions.
9. Implement governed actions with authorization, transactions, idempotency, and audit.
10. Implement the read-only Ontology Manager.
11. Implement the Object Explorer and operational action surfaces in a later phase.
12. Expose approved read and draft capabilities through MCP.
13. Build the end-to-end supplier-delay demonstration.

Do not build UI screens that depend on nonexistent contracts. Establish the underlying source of truth first.

---

## 12. Expected demonstration

A complete demonstration should be able to show:

1. A supplier delay is recorded as a governed risk event.
2. The system follows object relationships to affected parts and products.
3. It identifies impacted customer orders.
4. It evaluates inventory across warehouses and relevant purchase orders.
5. It generates a mitigation recommendation with an explanation.
6. A planner creates and submits a mitigation plan.
7. An authorized operations manager approves the plan.
8. Approved steps execute through governed actions.
9. Operational state is changed transactionally.
10. The action, affected objects, and before/after state are visible in audit history.
11. The AI can explain the evidence and reasoning without bypassing approval controls.

---

## 13. Testing expectations

Tests should cover the layer being changed.

### Database

- migration applies successfully
- foreign keys and uniqueness constraints work
- invalid domain values are rejected
- required indexes exist
- seed data satisfies all constraints

### Ontology

- YAML parses safely
- structural validation works
- cross-resource references are validated
- handler names resolve
- registry is immutable
- invalid fixtures fail with useful paths and messages
- prohibited AI permissions are rejected

### Functions and actions

- authorization is enforced
- state transitions are enforced
- validation rejects stale or invalid data
- transactions prevent partial writes
- idempotency prevents duplicate execution
- success and failure are audited

### Ontology Manager

- lists and detail pages come from registry data
- search includes nested metadata
- dependency indexes are correct
- graph projection is deterministic
- unknown resources return structured errors
- no mutation endpoint or execution control exists
- production build and existing tests pass

---

## 14. Definition of done

A task is complete only when:

- the implementation follows the correct context document
- source-of-truth boundaries are preserved
- no temporary project name is introduced
- important writes use governed actions
- permissions are enforced server-side
- critical writes are transactional and audited
- AI restrictions are preserved
- validation errors are clear and actionable
- tests cover the new behavior
- existing tests continue to pass
- the implementation does not include out-of-scope future features
- relevant documentation is updated when contracts or paths change

---

## 15. Final principle

The project should demonstrate that operational data is more than rows and endpoints.

```text
PostgreSQL stores the operational facts.
The ontology gives those facts business meaning.
Functions derive operational insight.
Actions govern change.
Permissions control authority.
Audit history creates accountability.
AI uses approved capabilities without bypassing human control.
```
