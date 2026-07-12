# Ontology API Design Context

## File Description

This file defines the API layer for **Operational Ontology**, a Palantir Foundry Ontology-inspired supply-chain disruption response system. It is implementation context for a coding agent.

The API exposes ontology metadata, objects, links, read-only functions, governed actions, mitigation-plan workflows, action executions, and audit history. It does not redefine Function Engine or Action Engine business logic.

---

## 1. Core Design

The API must expose the system as an ontology rather than unrestricted CRUD:

```text
Objects   = business entities
Links     = declared relationships
Functions = read-only calculations and recommendations
Actions   = governed operations that can change business data
```

Do not expose generic business-write endpoints such as:

```http
PATCH /api/v1/inventory/:inventoryId
```

Use registered actions instead:

```http
POST /api/v1/actions/reallocateInventory
```

Request flow:

```text
Client
→ Authentication
→ Trusted ActorContext
→ Thin API controller
→ Ontology Runtime
→ Authorization and validation
→ Object / Link / Function / Action Engine
→ Permission-aware response
```

Controllers must not contain supply-chain business logic or directly update operational tables.

---

## 2. Common API Contract

### Base path

```text
/api/v1
```

### Conventions

- JSON request and response bodies
- `camelCase` fields
- UTC ISO 8601 timestamps
- Bearer-token authentication
- Cursor pagination
- Server-generated request ID when absent

```http
Authorization: Bearer <token>
X-Request-Id: req_abc123
```

The server derives a trusted context from authentication:

```json
{
  "actorId": "user-123",
  "actorType": "USER",
  "roles": ["planner"]
}
```

Never trust actor identity, roles, or permissions from a request body.

### Success response

```json
{
  "data": {},
  "meta": {
    "requestId": "req_abc123",
    "timestamp": "2026-07-11T22:30:00Z"
  }
}
```

### Paginated response metadata

```json
{
  "nextCursor": "cursor_xyz",
  "hasMore": true
}
```

### Error response

```json
{
  "error": {
    "code": "OBJECT_NOT_FOUND",
    "message": "Supplier S-999 was not found.",
    "details": {}
  },
  "meta": {
    "requestId": "req_abc123",
    "timestamp": "2026-07-11T22:30:00Z"
  }
}
```

Core error codes:

```text
INVALID_REQUEST
UNAUTHENTICATED
FORBIDDEN
OBJECT_NOT_FOUND
LINK_NOT_FOUND
FUNCTION_NOT_FOUND
ACTION_NOT_FOUND
ACTION_NOT_ALLOWED
VALIDATION_FAILED
IDEMPOTENCY_CONFLICT
CONFLICT
FUNCTION_EXECUTION_FAILED
ACTION_EXECUTION_FAILED
INTERNAL_ERROR
```

HTTP guidance:

```text
200 success
201 object or execution created
202 long-running execution accepted
400 invalid request shape
401 unauthenticated
403 forbidden
404 ontology resource not found
409 conflict
422 business validation failed
500 unexpected failure
```

---

## 3. GET versus POST

```text
Simple retrieval       → GET
Complex structured search → POST
Read-only calculation  → POST function endpoint
Business modification  → POST action endpoint
```

Use POST for searches with multiple filters, sorting rules, date ranges, or object types because a JSON body is easier to validate and extend.

---

## 4. Ontology Metadata APIs

These read-only endpoints describe what exists in the ontology:

```http
GET /api/v1/ontology
GET /api/v1/ontology/object-types
GET /api/v1/ontology/object-types/:objectType
GET /api/v1/ontology/link-types
GET /api/v1/ontology/link-types/:linkType
GET /api/v1/ontology/functions
GET /api/v1/ontology/functions/:functionName
GET /api/v1/ontology/action-types
GET /api/v1/ontology/action-types/:actionType
GET /api/v1/ontology/roles
GET /api/v1/ontology/roles/:roleName
```

Requirements:

- Load definitions from the ontology registry/configuration.
- Filter metadata according to actor permissions.
- Do not expose restricted properties, actions, functions, or role details.
- Ontology definitions are edited through project configuration, not public APIs, for the MVP.

---

## 5. Object and Link APIs

### Objects

```http
GET  /api/v1/objects/:objectType/:objectId
POST /api/v1/objects/:objectType/search
POST /api/v1/objects/search
```

One-type search body:

```json
{
  "query": "delayed supplier",
  "filters": [
    {
      "property": "status",
      "operator": "equals",
      "value": "delayed"
    }
  ],
  "sort": [
    {
      "property": "reliabilityScore",
      "direction": "asc"
    }
  ],
  "limit": 20,
  "cursor": null
}
```

Cross-object search adds:

```json
{
  "objectTypes": ["Supplier", "RiskEvent", "PurchaseOrder"]
}
```

Object rules:

- Resolve object types and backing sources from ontology metadata.
- Only allow declared searchable, filterable, and sortable properties.
- Validate operators against property data types.
- Apply property-level permission projection.
- Never accept client-provided SQL, table names, or column names.

### Links

```http
GET  /api/v1/objects/:objectType/:objectId/links
GET  /api/v1/objects/:objectType/:objectId/links/:linkType
POST /api/v1/objects/:objectType/:objectId/links/:linkType/search
```

Declared link kinds:

```text
stored   direct database relationship
derived  computed by a registered read-only function
path     declared traversal through intermediate object types
```

Link rules:

- Confirm the link belongs to the source object type.
- Follow only relationships declared in ontology metadata.
- Do not provide unrestricted graph-depth traversal in the MVP.
- Return linked results consistently as an objects array.

---

## 6. Function APIs

Functions calculate, find, rank, explain, or recommend. They must not modify operational data.

```http
POST /api/v1/functions/:functionName
POST /api/v1/objects/:objectType/:objectId/functions/:functionName
```

Request:

```json
{
  "parameters": {
    "delayDays": 5
  }
}
```

Response shape:

```json
{
  "data": {
    "functionName": "findImpactedOrders",
    "result": {}
  },
  "meta": {
    "requestId": "req_123",
    "executedAt": "2026-07-11T22:30:00Z"
  }
}
```

Execution flow:

```text
Resolve function
→ Check permission
→ Validate parameters
→ Execute Function Engine
→ Project permitted result fields
→ Return result
```

The object-scoped route automatically supplies the object reference.

---

## 7. Action APIs

Actions are the only public API mechanism allowed to change operational data.

```http
POST /api/v1/actions/:actionType
POST /api/v1/objects/:objectType/:objectId/actions/:actionType
```

Example:

```http
POST /api/v1/actions/reallocateInventory
Authorization: Bearer <token>
Idempotency-Key: reallocate-ORD-881-WH-202
```

```json
{
  "parameters": {
    "fromWarehouseId": "WH-202",
    "toWarehouseId": "WH-101",
    "partId": "PART-501",
    "quantity": 150
  },
  "reason": "Prevent stockout for customer order ORD-881"
}
```

Execution flow:

```text
Resolve action definition
→ Authenticate and authorize actor
→ Validate parameters
→ Evaluate preconditions and business rules
→ Check idempotency
→ Execute Action Engine transaction
→ Record affected objects
→ Write audit records
→ Return execution result
```

Response includes:

```text
executionId
actionType
status
affectedObjects
result
```

Action statuses:

```text
pending
awaitingApproval
running
succeeded
failed
rejected
partiallyCompleted
```

---

## 8. Action Idempotency

Every action request requires:

```http
Idempotency-Key: <caller-generated-key>
```

Persist:

```text
actorId
actionType
idempotencyKey
requestPayloadHash
executionId
executionResult
```

Behavior:

```text
Same key + same actor/action/payload
→ Return original result

Same key + different payload
→ 409 IDEMPOTENCY_CONFLICT
```

This is mandatory for inventory movement, purchase-order creation, risk-event creation, and mitigation execution.

---

## 9. Mitigation Plan Workflow

A mitigation plan contains both:

```text
Human-readable recommendation
+
Machine-readable ordered action steps
```

Confirmed workflow:

```text
RiskEvent
→ recommendMitigationPlan function
→ createMitigationPlan action
→ Planner reviews plan
→ approveMitigationPlan action
→ executeMitigationPlan action
→ Plan Executor invokes registered actions
→ Every step and object change is audited
```

Example recommendation result:

```json
{
  "summary": "Move 150 units from WH-202 to WH-101 to protect ORD-881.",
  "reason": "WH-202 has sufficient excess inventory.",
  "steps": [
    {
      "sequence": 1,
      "actionType": "reallocateInventory",
      "parameters": {
        "partId": "PART-501",
        "fromWarehouseId": "WH-202",
        "toWarehouseId": "WH-101",
        "quantity": 150
      }
    },
    {
      "sequence": 2,
      "actionType": "expediteShipment",
      "parameters": {
        "customerOrderId": "ORD-881"
      }
    }
  ]
}
```

Lifecycle actions:

```http
POST /api/v1/actions/createMitigationPlan
POST /api/v1/actions/approveMitigationPlan
POST /api/v1/actions/executeMitigationPlan
```

Plan Executor requirements:

1. Load an approved plan.
2. Validate plan and step states.
3. Execute steps in the declared order.
4. Send every step through the existing Action Engine.
5. Use a stable idempotency key for each plan step.
6. Save each step result and final plan status.
7. Never run arbitrary SQL, scripts, prompts, or unregistered instructions.

A valid step references a registered action:

```json
{
  "stepId": "STEP-1",
  "sequence": 1,
  "actionType": "reallocateInventory",
  "parameters": {},
  "status": "pending"
}
```

Plan statuses:

```text
draft
approved
executing
completed
partiallyCompleted
failed
rejected
```

Step statuses:

```text
pending
running
completed
failed
skipped
```

---

## 10. Available Actions, Executions, and Audit

### Available actions for an object

```http
GET /api/v1/objects/:objectType/:objectId/available-actions
```

Evaluate actor permissions, object state, action preconditions, and business rules. Return whether each relevant action is allowed and, when not allowed, a safe reason.

This endpoint helps the UI, but the Action Engine must repeat all checks during execution.

### Action execution records

```http
GET  /api/v1/action-executions/:executionId
POST /api/v1/action-executions/search
```

Execution searches may filter by action type, status, actor, affected object, mitigation plan, and timestamp.

### Audit records

```http
POST /api/v1/audit/search
POST /api/v1/objects/:objectType/:objectId/audit/search
```

Audit records capture:

```text
actor
action type
affected object
permitted before/after values
reason
request ID
execution ID
timestamp
```

Distinction:

```text
Action execution = technical lifecycle of an operation
Audit record     = business history of who changed what and why
```

One execution may create multiple audit records. Redact restricted properties from audit responses.

---

## 11. Suggested Module Boundaries

Adapt names to the selected backend framework while preserving responsibilities:

```text
api/
  middleware/
    authentication
    requestContext
    errorHandler
  ontology/
  objects/
  links/
  functions/
  actions/
  executions/
  audit/
  schemas/
  presenters/
```

The API should depend on runtime interfaces such as:

```text
OntologyRegistry
ObjectRuntime
LinkRuntime
FunctionEngine
ActionEngine
AuthorizationService
ActionExecutionRepository
AuditRepository
```

Controllers should not directly depend on individual operational-table repositories.

---

## 12. Required Rules

1. Resolve all object types, links, functions, and actions through the ontology registry.
2. Reject unknown ontology identifiers.
3. Validate every request body with a schema validator.
4. Validate search properties and operators using ontology metadata.
5. Create actor context only from trusted authentication data.
6. Enforce authorization inside runtime services, not only in the frontend.
7. Apply property-level response projection.
8. Require idempotency keys for actions.
9. Run multi-write actions inside database transactions.
10. Never accept arbitrary SQL, table names, columns, scripts, or action code.
11. Never allow mitigation steps to bypass the Action Engine.
12. Store execution and audit records for important writes.
13. Never expose stack traces or internal database details in API errors.

---

## 13. Minimum Tests

Test at least:

- Standard success/error contracts and request IDs.
- Authentication and permission failures.
- Unknown object types, links, functions, and actions.
- Restricted property projection.
- Invalid search fields and operators.
- Function parameter validation and read-only behavior.
- Action rollback when business validation fails.
- Idempotent retry and idempotency conflict behavior.
- A successful action producing execution and audit records.
- Rejection of unregistered mitigation-plan steps.
- Prevention of executing an unapproved plan.
- Plan-step execution through the Action Engine.
- Retrying plan execution without repeating completed steps.
- Correct `partiallyCompleted` result after partial failure.

---

## 14. Implementation Order

```text
1. Shared request context, response, errors, and authentication
2. Ontology metadata endpoints
3. Object retrieval and structured search
4. Link retrieval and linked-object search
5. Function endpoints
6. Action endpoints and idempotency
7. Available-actions endpoint
8. Execution and audit endpoints
9. Mitigation Plan Executor
10. Integration and permission tests
```

---

## Final Principles

- Ontology metadata is the API contract source of truth.
- Controllers stay thin.
- Functions remain read-only.
- All business writes use governed actions.
- Complex searches use POST with structured JSON.
- Operational lists use cursor pagination.
- Permissions are checked during every function and action execution.
- Mitigation plans combine readable explanations with structured action steps.
- Plan steps execute only through registered actions.
- Important decisions remain traceable through executions and audit records.
