# Ontology Actions Implementation Context

> **Short description:** This file defines how the Version 1 governed ontology actions and shared Action Engine must be implemented for the supply-chain disruption workflow. It gives Codex the action lifecycle, permissions, validation rules, idempotency behavior, transaction boundaries, concurrency controls, audit requirements, handler contracts, edge cases, testing requirements, and the strict boundary between read-only functions and operational writes.

---

## 1. Purpose

Use this document when implementing the backend Action Engine and action handlers declared in `ontology/ontology.yaml`.

The ontology metadata already defines the stable action names, public parameters, target objects, allowed roles, state transitions, and governance settings. This file defines the executable behavior behind those stable handler names.

The required Version 1 actions are:

```text
createRiskEvent
acknowledgeRiskEvent
generateMitigationPlan
submitMitigationPlan
approveMitigationPlan
rejectMitigationPlan
executeMitigationPlan
reallocateInventory
completeInventoryTransfer
expeditePurchaseOrder
prioritizeShipment
resolveRiskEvent
```

This document is intentionally focused on action execution. It must not become a database redesign, ontology editor specification, function-calculation specification, frontend specification, or generic workflow platform.

---

## 2. Read this with the existing project context

Before implementing these actions, read the repository's actual versions of:

```text
AGENT.md or agent.md
supplygraph_database_context.md
SupplyGraph_Ontology_Implementation_Context.md
ontology_functions_implementation_context.md
```

Use the repository's actual filenames and paths when capitalization differs.

Source-of-truth responsibilities:

```text
PostgreSQL
= actual operational state and execution history

ontology/ontology.yaml
= action metadata, public contracts, roles, and state transitions

ontology_functions_implementation_context.md
= read-only impact, recommendation, scoring, and validation logic

this document
= Version 1 Action Engine and action-handler behavior

backend action handlers
= executable governed write logic
```

When this document and `ontology.yaml` describe the same action, preserve the stable action key, handler name, public parameter schema, target object type, role metadata, and state transitions from the ontology definition.

If implementation requires a public contract change, update `ontology.yaml`, its schema validation, registry tests, and action tests in the same change. Do not silently invent a second contract inside handler code.

---

## 3. Core action boundary

An ontology action may:

- create an operational object;
- update approved operational properties;
- change an object's workflow state;
- create or update stored links required by the action;
- call read-only ontology functions;
- acquire database locks;
- execute transactionally;
- reserve operational resources;
- record execution and audit history;
- dispatch approved child actions as part of a parent workflow.

An ontology action must never:

- bypass authentication or role authorization;
- accept undeclared parameters;
- perform a state transition not declared by the ontology;
- write through a generic object-update endpoint;
- trust stale recommendations without revalidation;
- allow an AI agent to approve or execute critical operations;
- commit partial business changes after a required step fails;
- rely only on frontend validation;
- use an LLM as the source of inventory, cost, timing, or feasibility truth;
- hide a business mutation inside a read-only function.

Canonical distinction:

```text
recommendMitigationPlan function
= calculates a possible response

generateMitigationPlan action
= persists a draft plan and steps
```

```text
validateMitigationPlan function
= reports current feasibility

submit / approve / execute actions
= enforce governance and persist state changes
```

```text
findAlternativeWarehouses function
= identifies safe transfer options

reallocateInventory action
= reserves inventory and creates the transfer
```

---

## 4. Action groups and workflow

### 4.1 Risk-event lifecycle

```text
createRiskEvent
acknowledgeRiskEvent
resolveRiskEvent
```

### 4.2 Mitigation-plan lifecycle

```text
generateMitigationPlan
submitMitigationPlan
approveMitigationPlan
rejectMitigationPlan
executeMitigationPlan
```

### 4.3 Operational mitigation actions

```text
reallocateInventory
expeditePurchaseOrder
prioritizeShipment
```

### 4.4 Transfer completion

```text
completeInventoryTransfer
```

Expected end-to-end workflow:

```text
createRiskEvent
        ↓
RiskEvent = open
        ↓
acknowledgeRiskEvent
        ↓
RiskEvent = acknowledged
        ↓
generateMitigationPlan
        ↓
MitigationPlan = draft
        ↓
submitMitigationPlan
        ↓
MitigationPlan = pending_approval
        ↓
approveMitigationPlan
        ↓
MitigationPlan = approved
        ↓
executeMitigationPlan
        ↓
operational child actions execute
        ↓
MitigationPlan = completed
RiskEvent = mitigated
        ↓
completeInventoryTransfer when physical stock arrives
        ↓
resolveRiskEvent after impact and unfinished work are gone
        ↓
RiskEvent = resolved
```

Rejected path:

```text
pending_approval
        ↓
rejectMitigationPlan
        ↓
rejected
```

A rejected plan is terminal in Version 1. Generate a new plan instead of reopening or editing the rejected plan.

---

## 5. Confirmed Version 1 semantics

The implementation must preserve these decisions:

1. All important operational writes happen through governed actions.
2. All 12 actions require idempotency protection.
3. Critical actions require a human-readable reason.
4. Plans are revalidated before submission, approval, and execution.
5. A plan submitter cannot approve the same plan.
6. Approval does not reserve inventory or execute operational changes.
7. `executeMitigationPlan` executes required plan steps transactionally.
8. Child operational actions reuse the parent transaction during plan execution.
9. `reallocateInventory` reserves source inventory and creates an approved transfer.
10. Destination on-hand inventory changes only when `completeInventoryTransfer` succeeds.
11. A completed mitigation plan means all approved operational commands were successfully applied.
12. Physical transfers may remain approved or in transit after the plan is completed.
13. A mitigated risk means mitigation commands were applied.
14. A resolved risk means no current risk-caused impact or unfinished mitigation remains.
15. AI may generate a draft plan only; it may not submit, approve, reject, execute, move inventory, expedite a purchase order, prioritize a shipment, complete a transfer, or resolve a risk.
16. The implementation is deterministic and database-backed. AI text is explanatory evidence, not operational truth.

---

## 6. Shared Action Engine

Do not repeat authentication, authorization, idempotency, transaction setup, audit creation, and error mapping inside every handler.

Implement one shared Action Engine responsible for the execution pipeline.

Recommended high-level flow:

```text
1. Resolve action metadata from the ontology registry.
2. Resolve the stable backend handler.
3. Authenticate the actor.
4. Authorize the actor using ontology metadata.
5. Validate request envelope and action parameters.
6. Reject unknown parameters.
7. Validate the reason requirement.
8. Normalize parameters and calculate a parameter hash.
9. Claim the idempotency key.
10. Start the business transaction.
11. Lock affected records in deterministic order.
12. Recheck permissions and mutable business state when required.
13. Validate action preconditions.
14. Execute the handler.
15. Record affected objects and before/after snapshots.
16. Record audit entries.
17. Store the typed result.
18. Mark the action execution succeeded.
19. Commit.
20. Return the result.
```

On failure:

```text
1. Roll back all business changes.
2. Classify the failure.
3. Mark the claimed execution failed in a separate safe transaction.
4. Store a safe error code and message.
5. Record failure evidence without secrets.
6. Return the structured error.
```

The Action Engine must not infer permission or transaction requirements from action names. Read them from the normalized ontology registry, while still applying mandatory system-wide safety rules from this document.

---

## 7. Action request and execution context

### 7.1 Public request envelope

Use the repository's API conventions, but the logical request should contain:

```ts
interface ActionRequest<TParameters> {
  parameters: TParameters;
}
```

The idempotency key should normally come from an HTTP header:

```http
Idempotency-Key: <caller-generated-key>
```

Do not place the idempotency key inside business parameters unless the existing framework requires it.

### 7.2 Runtime context

Every action handler should receive a trusted runtime context equivalent to:

```ts
interface ActionExecutionContext {
  actorId: string;
  actorRoles: string[];
  requestId: string;
  idempotencyKey: string;
  executedAt: Date;
  ontologyVersion: string;
  actionDefinitionVersion: string;
  invocationSource: "user" | "ai_agent" | "system";
  executionId: string;
  parentExecutionId?: string;
  invocationMode: "top_level" | "child_action";
}
```

The API caller must not be allowed to provide or spoof:

```text
actorId
actorRoles
invocationSource
executionId
parentExecutionId
invocationMode
ontologyVersion
actionDefinitionVersion
```

These values come from authentication, the registry, and the Action Engine.

### 7.3 Time

Use `context.executedAt` as the action clock.

Do not call the system clock repeatedly inside handler logic. This keeps timestamps consistent and tests reproducible.

### 7.4 Typed results

Handlers must return explicit DTOs. Do not return raw ORM entities or unrestricted database rows.

A common result envelope may be:

```ts
interface ActionResult<TData> {
  executionId: string;
  actionName: string;
  status: "succeeded";
  executedAt: string;
  data: TData;
  affectedObjects: Array<{
    objectType: string;
    objectId: string;
    operation: "created" | "updated";
  }>;
  warnings: string[];
  replayedFromIdempotency: boolean;
}
```

---

## 8. Metadata-driven authorization

The ontology registry is the source of truth for action roles.

Required Version 1 role behavior:

| Action | Planner | OperationsManager | Admin | AIAgent |
|---|---:|---:|---:|---:|
| `createRiskEvent` | Yes | Yes | Yes | No |
| `acknowledgeRiskEvent` | Yes | Yes | Yes | No |
| `generateMitigationPlan` | Yes | Yes | Yes | Yes |
| `submitMitigationPlan` | Yes | Yes | Yes | No |
| `approveMitigationPlan` | No | Yes | Yes | No |
| `rejectMitigationPlan` | No | Yes | Yes | No |
| `executeMitigationPlan` | No | Yes | Yes | No |
| `reallocateInventory` | No | Yes | Yes | No |
| `completeInventoryTransfer` | No | Yes | Yes | No |
| `expeditePurchaseOrder` | No | Yes | Yes | No |
| `prioritizeShipment` | No | Yes | Yes | No |
| `resolveRiskEvent` | No | Yes | Yes | No |

`Viewer` may not execute write actions.

Authorization order:

```text
authenticate
→ resolve action metadata
→ check role permission
→ validate object-level/business restrictions
→ execute
```

A role check alone is not enough. For example, an `OperationsManager` still cannot approve a plan they submitted.

Do not trust UI visibility as authorization. Every request must be authorized server-side.

---

## 9. Input validation

Every action must validate:

- required fields;
- declared scalar types;
- enum values;
- numeric bounds;
- date formats;
- string length limits;
- IDs and object existence;
- state transitions;
- business preconditions;
- unknown parameters;
- reason requirement;
- matching mitigation step when applicable.

Use the action parameter schema loaded from `ontology.yaml` as the public schema.

Recommended validation sequence:

```text
request envelope
→ schema validation
→ unknown-field rejection
→ authorization
→ object existence
→ state transition
→ business preconditions
→ transactional revalidation under locks
```

Important mutable preconditions must be checked again after locks are acquired. A validation performed before the transaction may become stale.

---

## 10. Reason requirements

A reason is required for:

```text
createRiskEvent
acknowledgeRiskEvent
submitMitigationPlan
approveMitigationPlan
rejectMitigationPlan
executeMitigationPlan
reallocateInventory
completeInventoryTransfer
expeditePurchaseOrder
prioritizeShipment
resolveRiskEvent
```

`generateMitigationPlan` may accept optional notes but does not require a critical-action reason because it only creates a draft.

Validation rules:

- trim leading and trailing whitespace;
- reject an empty string after trimming;
- apply a reasonable maximum length from configuration or the database schema;
- persist the exact accepted reason in the action audit record;
- do not overwrite the domain object's original reason unless that is an explicit effect of the action.

---

## 11. Idempotency

### 11.1 Goal

The same logical action may be retried, but its operational effect must happen once.

Example:

```text
Transfer 40 units from Warehouse B to Warehouse A.
Backend succeeds.
Network response is lost.
Client retries.
```

Correct result:

```text
one InventoryTransfer
40 units reserved once
original result returned on retry
```

### 11.2 Idempotency identity

Recommended unique identity:

```text
actorId + actionName + idempotencyKey
```

Enforce it with a database unique constraint on the existing action-execution table or equivalent.

The exact column names should follow the database context, but the record must support:

```text
executionId
actionName
actorId
idempotencyKey
parameterHash
status
requestId
invocationSource
parentExecutionId
startedAt
completedAt
resultPayload
errorCode
errorMessage
ontologyVersion
actionDefinitionVersion
```

### 11.3 Parameter hash

Normalize the declared action parameters and calculate a stable hash.

Normalization must:

- sort object keys recursively;
- preserve array order unless the schema explicitly defines a set;
- use one stable date representation;
- use stable decimal serialization;
- exclude transport-only fields such as request IDs;
- exclude authentication and runtime context;
- include every declared business parameter.

Store:

```text
SHA-256(canonical action name + normalized parameters)
```

Do not hash secrets into logs. These actions should not accept secrets.

### 11.4 Recommended claim strategy

Use a short idempotency-claim transaction:

```text
BEGIN
INSERT action execution with status = in_progress
COMMIT
```

The insert is protected by the unique identity.

If the insert succeeds, this request owns the execution.

If it conflicts, load the existing record and compare the parameter hash.

This claim transaction is separate from the business transaction so concurrent retries can observe that an execution is already running.

### 11.5 Retry behavior

| Existing status | Same key and same parameter hash |
|---|---|
| `succeeded` | Return the original stored result. Do not execute again. |
| `in_progress` | Return `ACTION_ALREADY_IN_PROGRESS`, or wait only when the existing API convention explicitly supports bounded waiting. |
| `failed` | Return the stored failure. A corrected new attempt must use a new idempotency key. |
| stale `in_progress` | Mark failed using the stale-execution policy, then require a new key or explicitly supported recovery flow. |

If the same key is reused with a different parameter hash, return:

```text
IDEMPOTENCY_KEY_PARAMETER_MISMATCH
```

Never execute the second parameter set.

### 11.6 Business transaction and success record

After the claim succeeds, start the business transaction.

The following must commit together:

```text
operational writes
affected-object records
audit records
stored action result
execution status = succeeded
completedAt
```

This prevents:

```text
business state changed but execution says failed
```

and:

```text
execution says succeeded but business state did not change
```

### 11.7 Failure handling

On a handler failure:

```text
ROLL BACK business transaction
```

Then, in a separate small transaction:

```text
set execution status = failed
store safe errorCode
store safe errorMessage
store failedAt/completedAt
```

No partial operational effects may remain.

### 11.8 Stale in-progress execution

A server may crash after claiming a key and before recording success or failure.

Use configuration such as:

```text
actionInProgressTimeoutMinutes
```

An old `in_progress` record may be transitioned to failed with:

```text
STALE_ACTION_EXECUTION
```

Do not automatically repeat a potentially external side effect. Version 1 actions are database-local, so recovery is simpler, but the implementation must still inspect current domain state before any manual recovery.

### 11.9 Parent and child idempotency

`executeMitigationPlan` is the top-level idempotent action.

For internal child actions, use a stable operation identity derived from:

```text
mitigationPlanId + mitigationStepId + childActionName + actionVersion
```

Also record `parentExecutionId` for traceability.

Child execution records created inside the parent business transaction must roll back when the parent transaction rolls back.

The client must not be able to provide or forge internal child keys.

### 11.10 Idempotency is not concurrency control

Idempotency prevents duplicate retries of the same logical request.

It does not prevent two different requests from competing for the same inventory or plan.

The implementation still requires row locks, conditional updates, state checks, and transactions.

---

## 12. Transactions

### 12.1 General rule

Every action that writes operational state must run inside a database transaction.

This is mandatory for all Version 1 actions and especially important for:

```text
executeMitigationPlan
reallocateInventory
completeInventoryTransfer
```

### 12.2 Transaction contents

A business transaction should include:

- current-state revalidation;
- business writes;
- state transitions;
- affected-object records;
- before/after snapshots;
- audit records;
- successful result persistence;
- successful execution-state update.

### 12.3 Isolation

Use the repository's safe PostgreSQL transaction conventions.

At minimum:

- lock mutable target rows with `SELECT ... FOR UPDATE` when appropriate;
- use atomic conditional updates for inventory quantities;
- recheck mutable state under the lock;
- avoid reading a plan, inventory, or purchase order outside the transaction and trusting it inside the transaction.

`READ COMMITTED` with explicit row locking and atomic conditions is sufficient for Version 1 when correctly implemented. A stricter isolation level may be used if the existing repository already standardizes it.

### 12.4 External systems

Version 1 actions must not call real carrier, supplier, payment, or ERP APIs inside the database transaction.

The Version 1 implementation updates local operational records only.

A future external-integration design would require an outbox, retries, reconciliation, and compensation. Do not approximate that with an HTTP call inside a long transaction.

---

## 13. Concurrency and locking

### 13.1 Why locks are required

Example:

```text
Transferable inventory = 60
Manager A requests 50
Manager B requests 50
```

Both requests may have different idempotency keys. Idempotency does not stop the conflict.

Only one request may succeed.

### 13.2 Inventory protection

For `reallocateInventory`, enforce atomically:

```text
onHandQuantity
- reservedQuantity
- safetyStockQuantity
>= requestedQuantity
```

Use either:

- `SELECT ... FOR UPDATE` followed by a checked update; or
- one atomic conditional `UPDATE` whose affected-row count must equal one.

If the condition fails, return:

```text
INSUFFICIENT_TRANSFERABLE_INVENTORY
```

### 13.3 Plan protection

Lock the `MitigationPlan` row before submit, approve, reject, or execute.

This prevents:

```text
two approvals
a simultaneous approval and rejection
two executions
an execution racing with another state transition
```

### 13.4 Risk-event protection

Lock the `RiskEvent` when:

- acknowledging it;
- generating an active plan when active-plan uniqueness is checked;
- resolving it;
- marking it mitigated during plan execution.

### 13.5 Purchase-order and shipment protection

Lock the target `PurchaseOrder` or `Shipment` before changing it.

Recheck status, date, priority, and plan relevance under the lock.

### 13.6 Deterministic lock order

To reduce deadlocks, acquire locks in a stable order.

For plan execution:

```text
1. RiskEvent by ID
2. MitigationPlan by ID
3. MitigationStep rows by sequenceNumber then ID
4. InventoryPosition rows sorted by inventoryPositionId
5. PurchaseOrder rows sorted by purchaseOrderId
6. Shipment rows sorted by shipmentId
7. InventoryTransfer rows sorted by inventoryTransferId
```

Adapt this order to repository needs, but keep one documented order across handlers.

On a PostgreSQL deadlock or serialization failure, roll back and return a retryable structured error. Do not partially retry only one child step.

---

## 14. State machines

### 14.1 RiskEvent

Allowed transitions:

```text
open → acknowledged
open → resolved
acknowledged → mitigated
acknowledged → resolved
mitigated → resolved
```

Invalid examples:

```text
resolved → open
resolved → acknowledged
mitigated → open
```

`executeMitigationPlan` may perform:

```text
acknowledged → mitigated
```

`resolveRiskEvent` may perform the documented transitions to `resolved` only after its own business validation passes.

### 14.2 MitigationPlan

Allowed transitions:

```text
draft → pending_approval
pending_approval → approved
pending_approval → rejected
approved → executing
executing → completed
executing → failed
```

Terminal states in Version 1:

```text
rejected
completed
failed
```

Invalid examples:

```text
draft → approved
rejected → pending_approval
completed → executing
failed → approved
```

### 14.3 MitigationStep

Version 1 execution path:

```text
pending → validated → executing → completed
pending → validated → executing → failed
```

The existing enum may contain `skipped`, but Version 1 generated steps are required and should not be silently skipped.

If a step is stale or unnecessary, plan validation should fail and require a new plan rather than quietly changing the approved plan.

### 14.4 InventoryTransfer

Relevant Version 1 transitions:

```text
approved → completed
in_transit → completed
```

`reallocateInventory` creates the transfer directly in `approved` state because it runs only as part of an approved mitigation workflow.

The broader ontology may also describe:

```text
requested → approved
approved → in_transit
requested → cancelled
approved → cancelled
in_transit → failed
```

Do not add new public handlers for those transitions in this task.

### 14.5 Shipment and PurchaseOrder

`prioritizeShipment` changes priority, not shipment status.

`expeditePurchaseOrder` changes delivery information and expedite metadata, not the normal purchase-order status.

---

## 15. Active-plan uniqueness

Multiple draft plans may exist for one risk event so planners can compare strategies.

Only one plan for the same risk may be in any of these active governance states at a time:

```text
pending_approval
approved
executing
```

Enforce this under a lock on the `RiskEvent` and, when practical, with a partial unique database constraint.

Do not rely only on an application query without locking.

Rejected, completed, and failed plans do not block a new plan.

Draft plans do not block another draft.

---

## 16. Audit and action-execution history

### 16.1 Required execution record

Every attempted action must record enough information to answer:

```text
What action ran?
Who requested it?
Which ontology/action version governed it?
What parameters were supplied?
What happened?
Which objects changed?
What failed?
Was this a replayed idempotent request?
Was it initiated by a user, AI agent, or system workflow?
```

### 16.2 Required successful audit data

Record:

```text
executionId
actionName
actionDefinitionVersion
ontologyVersion
actorId
actorRoles
invocationSource
requestId
idempotencyKey
parameterHash
reason
startedAt
completedAt
status
target object
all affected objects
before values
after values
changed fields
parentExecutionId
validation snapshot references
result payload or result reference
```

### 16.3 Failed execution data

Record:

```text
errorCode
safe errorMessage
failed validation or failed step
rollback status
retryable flag
parentExecutionId
```

Do not store:

- passwords;
- access tokens;
- authorization headers;
- database credentials;
- unrestricted stack traces;
- secrets in request payloads;
- hidden AI reasoning.

### 16.4 Before and after snapshots

Store only the fields relevant to the action and audit requirement.

Examples:

```text
Shipment priority:
normal → critical
```

```text
InventoryPosition:
reservedQuantity 20 → 60
```

```text
PurchaseOrder:
expectedDeliveryDate July 20 → July 16
expedited false → true
expediteCost 0 → 500
```

Do not store uncontrolled full-row dumps when they include irrelevant or sensitive data.

### 16.5 Parent-child trace

For plan execution:

```text
executeMitigationPlan parent execution
    ├── reallocateInventory child execution
    ├── expeditePurchaseOrder child execution
    └── prioritizeShipment child execution
```

Every child record must reference the parent execution.

---

## 17. Common errors

Use structured errors with stable codes.

Recommended common codes:

```text
ACTION_NOT_FOUND
ACTION_HANDLER_NOT_FOUND
ACTION_NOT_ALLOWED
INVALID_ACTION_INPUT
UNKNOWN_ACTION_PARAMETER
ACTION_REASON_REQUIRED

IDEMPOTENCY_KEY_REQUIRED
IDEMPOTENCY_KEY_PARAMETER_MISMATCH
ACTION_ALREADY_IN_PROGRESS
STALE_ACTION_EXECUTION

OBJECT_NOT_FOUND
INVALID_STATE_TRANSITION
ACTION_PRECONDITION_FAILED
ACTION_VALIDATION_FAILED
CONCURRENT_MODIFICATION
DEADLOCK_RETRY_REQUIRED

RISK_EVENT_NOT_FOUND
DUPLICATE_ACTIVE_RISK_EVENT
MITIGATION_PLAN_NOT_FOUND
MITIGATION_STEP_NOT_FOUND
NO_FEASIBLE_MITIGATION
ANOTHER_ACTIVE_PLAN_EXISTS
APPROVER_IS_SUBMITTER
PLAN_VALIDATION_FAILED
PLAN_COST_CHANGED
PLAN_EXECUTION_FAILED
PLAN_HAS_UNFINISHED_OPERATIONS

INVENTORY_POSITION_NOT_FOUND
INSUFFICIENT_TRANSFERABLE_INVENTORY
SAFETY_STOCK_VIOLATION
INVENTORY_TRANSFER_NOT_FOUND
INVENTORY_TRANSFER_ALREADY_COMPLETED

PURCHASE_ORDER_NOT_FOUND
PURCHASE_ORDER_NOT_EXPEDITABLE
PURCHASE_ORDER_ALREADY_EXPEDITED

SHIPMENT_NOT_FOUND
SHIPMENT_NOT_PRIORITIZABLE
PRIORITY_NOT_INCREASED

ACTION_TRANSACTION_FAILED
ACTION_EXECUTION_FAILED
```

A structured error may be:

```ts
interface ActionErrorResponse {
  executionId?: string;
  actionName: string;
  code: string;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown>;
}
```

Do not expose SQL text, internal stack traces, or unrestricted record contents.

---

## 18. Shared configuration

Do not bury policy values inside handlers.

Use validated configuration equivalent to:

```ts
interface ActionEngineConfig {
  actionInProgressTimeoutMinutes: number;
  riskDuplicateWindowHours: number;
  planCostTolerancePercent: number;
  validationStaleAfterMinutes: number;
  maxReasonLength: number;
  maxActionResultPayloadBytes: number;
  retryableDatabaseErrorCodes: string[];
}
```

Recommended Version 1 defaults:

```text
actionInProgressTimeoutMinutes = 10
riskDuplicateWindowHours = 24
planCostTolerancePercent = use the same value as function validation configuration
validationStaleAfterMinutes = use the same value as function validation configuration
```

The function and action layers must share cost-tolerance and validation-staleness configuration. Do not define contradictory values in two modules.

---

# 19. Action specification: `createRiskEvent`

## 19.1 Purpose

Create a supplier-delay disruption record for an active supplier.

## 19.2 Public input

```text
supplierId: string
delayDays: integer greater than 0
severity: low | medium | high | critical
detectedAt: datetime
expectedResolutionDate: optional date
reason: string
source: manual | integration | ai_detected | simulation
```

## 19.3 Allowed roles

```text
Planner
OperationsManager
Admin
```

The `AIAgent` role may not create a risk event in Version 1.

## 19.4 Preconditions

Validate:

- Supplier exists.
- Supplier status is `active`.
- `delayDays > 0`.
- `detectedAt` is valid and not unreasonably in the future according to repository policy.
- `expectedResolutionDate`, when provided, is after `detectedAt`.
- `reason` is present.
- `source` is a declared enum value.
- An identical active risk event does not already exist inside the duplicate window.

Default duplicate definition:

```text
same supplierId
same riskType = supplier_delay
same delayDays
same source
status in open or acknowledged
created/detected inside riskDuplicateWindowHours
```

Idempotency still remains the primary protection against exact request retries. The duplicate rule prevents separate keys from creating accidental business duplicates.

## 19.5 Locks

Lock the Supplier row while validating its current status and creating the event.

When checking business duplicates, use a safe locking or uniqueness strategy consistent with the database model.

## 19.6 Effects

Create `RiskEvent` with:

```text
riskType = supplier_delay
status = open
supplierId = input supplierId
delayDays = input delayDays
severity = input severity
detectedAt = input detectedAt
expectedResolutionDate = input value or null
reason = input reason
source = input source
createdBy = actorId
createdAt = executedAt
updatedAt = executedAt
resolvedAt = null
```

Also:

- record the Supplier as an affected object;
- record the created RiskEvent as an affected object;
- create the audit entry.

Do not directly change Supplier status or persist derived supplier risk values.

## 19.7 Output

```ts
interface CreateRiskEventResult {
  riskEventId: string;
  supplierId: string;
  riskType: "supplier_delay";
  status: "open";
  delayDays: number;
  severity: "low" | "medium" | "high" | "critical";
  detectedAt: string;
  createdBy: string;
  createdAt: string;
}
```

## 19.8 Minimum tests

- creates an open supplier-delay risk;
- rejects inactive supplier;
- rejects zero or negative delay;
- rejects invalid expected-resolution date;
- rejects duplicate active risk created with a different idempotency key;
- same idempotency key returns the original event;
- different parameters with the same key are rejected;
- audit contains Supplier and RiskEvent.

---

# 20. Action specification: `acknowledgeRiskEvent`

## 20.1 Purpose

Record that an authorized human reviewed the disruption.

## 20.2 Public input

```text
riskEventId: string
reason: string
```

## 20.3 Allowed roles

```text
Planner
OperationsManager
Admin
```

## 20.4 State transition

```text
open → acknowledged
```

## 20.5 Preconditions

- RiskEvent exists.
- Current status is `open`.
- Reason is present.

## 20.6 Locks

Lock the RiskEvent row before checking status.

## 20.7 Effects

- set `status = acknowledged`;
- set `updatedAt = executedAt`;
- record before and after status;
- record actor, time, and reason in action history.

Version 1 does not require new `acknowledgedBy` or `acknowledgedAt` columns because the immutable action history records them.

## 20.8 Output

```ts
interface AcknowledgeRiskEventResult {
  riskEventId: string;
  previousStatus: "open";
  newStatus: "acknowledged";
  acknowledgedBy: string;
  acknowledgedAt: string;
}
```

## 20.9 Minimum tests

- open risk becomes acknowledged;
- already acknowledged risk is rejected;
- resolved risk is rejected;
- concurrent acknowledgements produce one success;
- idempotent retry returns the original result;
- audit records the transition and reason.

---

# 21. Action specification: `generateMitigationPlan`

## 21.1 Purpose

Persist a draft mitigation plan and steps from the read-only `recommendMitigationPlan` function.

## 21.2 Public input

```text
riskEventId: string
strategyPreference: optional string
notes: optional string
```

Do not add a required reason parameter. This action creates a draft only.

## 21.3 Allowed roles

```text
Planner
OperationsManager
Admin
AIAgent
```

## 21.4 Preconditions

- RiskEvent exists.
- RiskEvent status is `open` or `acknowledged`.
- RiskEvent is not resolved.
- `strategyPreference`, when provided, is a supported recommendation preference.
- Input contains no unknown fields.

Multiple draft plans for the same risk are allowed.

## 21.5 Read-only function call

Inside a consistent read snapshot, run:

```text
recommendMitigationPlan(riskEventId)
```

The action may pass a supported strategy preference through a typed internal function option when the function contract allows it. Do not let free-form notes alter numeric calculations.

If the recommendation returns:

```text
recommendedStrategy = no_feasible_mitigation
mitigationSteps = []
```

return:

```text
NO_FEASIBLE_MITIGATION
```

Do not create an empty executable plan merely to avoid an error.

## 21.6 Validation before persistence

Validate every recommended step against the corresponding action schema:

```text
reallocate_inventory → reallocateInventory parameters
expedite_purchase_order → expeditePurchaseOrder parameters
prioritize_shipment → prioritizeShipment parameters
```

Reject unsupported step types, missing target objects, unknown parameters, negative quantities, or malformed costs.

## 21.7 Effects

Create `MitigationPlan`:

```text
status = draft
riskEventId
strategy
summary
confidenceScore
estimatedCost
generatedBy = user | ai_agent | system
createdAt = executedAt
```

Create ordered `MitigationStep` records:

```text
sequenceNumber
stepType
targetObjectType
targetObjectId
parameters
status = pending
estimatedCost
expectedBenefit
createdAt = executedAt
```

Persist a recommendation snapshot or reference containing:

```text
function inputs
function executedAt
impacted object IDs
ranked order IDs
assumptions
warnings
cost estimate
confidence components
recommended and alternative strategies
```

Do not store hidden model reasoning.

## 21.8 AI-generated plans

When invoked by `AIAgent`:

```text
generatedBy = ai_agent
invocationSource = ai_agent
```

Record the approved tool/function evidence and workflow run ID when available.

AI may create the draft but cannot submit it.

## 21.9 Output

```ts
interface GenerateMitigationPlanResult {
  mitigationPlanId: string;
  riskEventId: string;
  status: "draft";
  strategy: string;
  summary: string;
  confidenceScore: number;
  estimatedCost: string;
  generatedBy: "user" | "ai_agent" | "system";
  stepIds: string[];
  stepCount: number;
  createdAt: string;
  warnings: string[];
}
```

## 21.10 Minimum tests

- human generates a valid draft;
- AI agent generates a draft;
- AI agent cannot proceed beyond draft generation;
- no-feasible-mitigation result creates no plan;
- malformed recommendation step is rejected;
- step sequence is deterministic;
- multiple drafts for one risk are allowed;
- idempotent retry returns the same plan and steps;
- recommendation evidence is persisted.

---

# 22. Action specification: `submitMitigationPlan`

## 22.1 Purpose

Freeze a valid draft and send it for human approval.

## 22.2 Public input

```text
mitigationPlanId: string
reason: string
```

## 22.3 Allowed roles

```text
Planner
OperationsManager
Admin
```

## 22.4 State transition

```text
draft → pending_approval
```

## 22.5 Preconditions

- Plan exists.
- Plan status is `draft`.
- Plan has at least one MitigationStep.
- Summary is present.
- Estimated cost is present and non-negative.
- Linked RiskEvent exists.
- Linked RiskEvent status is `acknowledged`.
- No other plan for the same risk is `pending_approval`, `approved`, or `executing`.
- `validateMitigationPlan` returns `valid = true` for submission-stage policy.
- Reason is present.

Requiring acknowledgement gives the risk-review action a meaningful governance role:

```text
drafts may be explored while a risk is open
submission requires the risk to be acknowledged
```

## 22.6 Locks

Lock in order:

```text
RiskEvent
MitigationPlan
MitigationStep rows
```

Then check active-plan uniqueness and run fresh validation against the transaction's operational snapshot.

## 22.7 Effects

- set plan status to `pending_approval`;
- set `submittedBy = actorId`;
- set `submittedAt = executedAt`;
- persist the submission validation snapshot;
- persist or checksum the exact submitted step definitions;
- set step status to `validated` when that matches the existing data model;
- audit the state transition.

After submission, plan strategy and step parameters are frozen.

Do not allow generic edits to a submitted plan. Generate a new plan if changes are required.

## 22.8 Output

```ts
interface SubmitMitigationPlanResult {
  mitigationPlanId: string;
  previousStatus: "draft";
  newStatus: "pending_approval";
  submittedBy: string;
  submittedAt: string;
  validationSnapshotId?: string;
  submittedStepChecksum: string;
}
```

## 22.9 Minimum tests

- valid acknowledged-risk draft is submitted;
- open, unacknowledged risk is rejected;
- empty plan is rejected;
- invalid plan is rejected;
- another active plan blocks submission;
- submitted plan cannot be submitted again;
- submitted step checksum is stable;
- concurrent submissions for two drafts result in one active plan;
- idempotent retry returns original result.

---

# 23. Action specification: `approveMitigationPlan`

## 23.1 Purpose

Approve a submitted plan after fresh feasibility validation and separation-of-duties checks.

## 23.2 Public input

```text
mitigationPlanId: string
reason: string
```

## 23.3 Allowed roles

```text
OperationsManager
Admin
```

## 23.4 State transition

```text
pending_approval → approved
```

## 23.5 Preconditions

- Plan exists.
- Plan status is `pending_approval`.
- `submittedBy` exists.
- Approver actor ID is different from `submittedBy`.
- Submitted steps still match the frozen submitted checksum.
- No other plan for the same risk is `approved` or `executing`.
- `validateMitigationPlan` returns valid under approval-stage policy.
- Recalculated cost is within the configured approval tolerance.
- Current inventory and purchase-order snapshots are available.
- Reason is present.

Return:

```text
APPROVER_IS_SUBMITTER
```

when separation of duties fails.

## 23.6 Locks

Lock:

```text
RiskEvent
MitigationPlan
MitigationStep rows
```

Lock or consistently read the operational rows needed by validation.

## 23.7 Effects

- set plan status to `approved`;
- set `approvedBy = actorId`;
- set `approvedAt = executedAt`;
- persist the approval-time validation snapshot;
- audit the transition and reason.

Approval must not:

- reserve inventory;
- create a transfer;
- change a purchase order;
- change shipment priority;
- mark the risk mitigated.

Operational resources may change after approval. The plan is validated again immediately before execution.

## 23.8 Output

```ts
interface ApproveMitigationPlanResult {
  mitigationPlanId: string;
  previousStatus: "pending_approval";
  newStatus: "approved";
  approvedBy: string;
  approvedAt: string;
  validationSnapshotId?: string;
  approvedEstimatedCost: string;
}
```

## 23.9 Minimum tests

- operations manager approves a valid submitted plan;
- admin approves a valid submitted plan;
- submitter cannot approve own plan;
- Planner and AIAgent are denied;
- stale or infeasible plan is rejected;
- material cost change is rejected;
- approval performs no operational resource writes;
- simultaneous approval and rejection produce one winner;
- idempotent retry returns original approval.

---

# 24. Action specification: `rejectMitigationPlan`

## 24.1 Purpose

Reject a submitted plan and preserve the reason for governance history.

## 24.2 Public input

```text
mitigationPlanId: string
reason: string
```

## 24.3 Allowed roles

```text
OperationsManager
Admin
```

## 24.4 State transition

```text
pending_approval → rejected
```

## 24.5 Preconditions

- Plan exists.
- Plan status is `pending_approval`.
- Reason is present.

The rejector may be the submitter only when ontology permission and organization policy permit it. Version 1 does not require a separate rejector rule; the approval separation rule applies specifically to approval.

## 24.6 Locks

Lock the MitigationPlan row before checking status.

## 24.7 Effects

- set status to `rejected`;
- set `rejectedBy = actorId`;
- set `rejectedAt = executedAt`;
- audit the rejection reason and transition.

Do not modify or delete steps. They remain historical evidence of what was rejected.

A rejected plan cannot be reopened in Version 1.

## 24.8 Output

```ts
interface RejectMitigationPlanResult {
  mitigationPlanId: string;
  previousStatus: "pending_approval";
  newStatus: "rejected";
  rejectedBy: string;
  rejectedAt: string;
}
```

## 24.9 Minimum tests

- valid pending plan is rejected;
- draft, approved, completed, and already rejected plans are rejected by the handler;
- steps remain unchanged as historical records;
- concurrent approval and rejection produce one success;
- idempotent retry returns original rejection.

---

# 25. Action specification: `executeMitigationPlan`

## 25.1 Purpose

Apply all required operations in an approved mitigation plan and mark the risk mitigated when every command succeeds.

## 25.2 Public input

```text
mitigationPlanId: string
reason: string
```

## 25.3 Allowed roles

```text
OperationsManager
Admin
```

## 25.4 State transitions

Success:

```text
approved → executing → completed
```

Failure:

```text
approved → executing → failed
```

Linked risk transition on success:

```text
acknowledged → mitigated
```

## 25.5 Preconditions

- Plan exists.
- Plan status is `approved`.
- Linked RiskEvent exists and status is `acknowledged`.
- Plan contains at least one step.
- All steps use supported types.
- All step parameters match current action schemas.
- Frozen step checksum still matches.
- `validateMitigationPlan` returns valid immediately before execution.
- Cost remains within execution-stage tolerance.
- Reason is present.

## 25.6 Lock preparation

Before writes:

1. Load the plan and steps.
2. Build the full set of mutable target rows.
3. Sort IDs using the shared lock order.
4. Start the business transaction.
5. Lock RiskEvent, MitigationPlan, steps, inventory positions, purchase orders, shipments, and existing transfers as applicable.
6. Re-run mutable precondition checks and validation under the locks.

Do not discover and lock objects in random step order.

## 25.7 Child dispatch

Dispatch by step type:

```text
reallocate_inventory
→ reallocateInventory

expedite_purchase_order
→ expeditePurchaseOrder

prioritize_shipment
→ prioritizeShipment
```

Child actions receive:

```text
parentExecutionId
invocationMode = child_action
same actorId
same executedAt
same database transaction
stable child operation identity
```

The child handler must still validate its specific business rules.

The public client cannot forge child invocation mode.

## 25.8 Atomic execution strategy

Version 1 plan execution is atomic because all supported effects are local PostgreSQL changes.

Required behavior:

```text
Either every required operational step succeeds,
or no operational step effect remains.
```

Recommended transaction structure:

```text
BEGIN business transaction

lock all affected rows
revalidate plan
set plan = executing
set current step = executing
execute child step 1
set step 1 = completed
execute child step 2
set step 2 = completed
...
set plan = completed
set completedAt
set risk = mitigated
record parent and child audit data
set parent execution = succeeded

COMMIT
```

If any required child step fails:

```text
ROLL BACK business transaction
```

Then use a separate failure-recording transaction to:

- set plan status to `failed` only when it is still safe and still `approved` after rollback;
- record the failed step ID, action type, error code, and failure reason;
- keep operational child effects rolled back;
- mark parent execution failed.

The implementation may use a savepoint to preserve failure-state writes, but it must not leave successful child business effects committed after another required step fails.

## 25.9 Already completed steps

Under the normal Version 1 flow, operational steps are executed only through this parent action, so an approved plan should not contain already completed steps.

Reject unexpected completed or failed step states before execution rather than silently skipping them.

## 25.10 Meaning of completion

A plan is `completed` when all governed commands were applied successfully:

- transfer records were created and source inventory reserved;
- purchase orders were marked expedited with updated dates and cost;
- shipment priorities were increased.

The plan does not wait for physical transfer arrival.

Example after plan completion:

```text
MitigationPlan = completed
RiskEvent = mitigated
InventoryTransfer = approved
```

Later:

```text
completeInventoryTransfer
```

moves physical inventory and sets the transfer to `completed`.

## 25.11 Output

```ts
interface ExecuteMitigationPlanResult {
  mitigationPlanId: string;
  riskEventId: string;
  previousPlanStatus: "approved";
  newPlanStatus: "completed";
  newRiskStatus: "mitigated";
  executedBy: string;
  executedAt: string;
  completedAt: string;
  stepResults: Array<{
    mitigationStepId: string;
    stepType: string;
    childExecutionId: string;
    status: "completed";
    affectedObjectIds: string[];
  }>;
}
```

## 25.12 Minimum tests

- valid approved plan executes all steps;
- risk becomes mitigated only after all steps succeed;
- a failing later step rolls back earlier operational effects;
- parent and child audits are linked;
- plan is revalidated under locks;
- two concurrent executions produce one success;
- AI, Planner, and submitter without execution role are denied according to roles;
- stale inventory causes execution failure without partial writes;
- idempotent retry returns the original completed result;
- plan completion does not complete physical transfers.

---

# 26. Action specification: `reallocateInventory`

## 26.1 Purpose

Reserve safe source inventory and create an approved warehouse-to-warehouse transfer for a mitigation step.

## 26.2 Public action parameters

```text
partId: string
sourceWarehouseId: string
destinationWarehouseId: string
quantity: number greater than 0
mitigationPlanId: string
reason: string
```

## 26.3 Allowed roles

```text
OperationsManager
Admin
```

## 26.4 Invocation rule

In Version 1, this handler is normally invoked as a governed child action of `executeMitigationPlan`.

Do not expose it to the AI agent.

If the generic action endpoint permits top-level invocation, the runtime must reject it unless the repository explicitly supports a trusted manual-step execution workflow. The default safe policy is:

```text
invocationMode must equal child_action
parent execution must be executeMitigationPlan
```

This preserves the atomic all-steps plan guarantee.

## 26.5 Preconditions

- MitigationPlan exists.
- Plan status is `executing` inside the parent transaction.
- Matching MitigationStep exists.
- Step type is `reallocate_inventory`.
- Step belongs to the plan.
- Step parameters and target match the action input.
- Step status is `validated` or the parent-supported pre-execution state.
- Part exists and is active.
- Source warehouse exists and is active.
- Destination warehouse exists and is active.
- Source and destination differ.
- Source InventoryPosition exists.
- Destination InventoryPosition exists.
- Quantity is greater than zero.
- Source has enough transferable inventory.
- Source remains at or above safety stock.
- The same step has not already created a transfer.
- Reason is present.

Transferable quantity:

```text
onHandQuantity
- reservedQuantity
- part safetyStockQuantity
- any additional committed quantity not already included in reservedQuantity
```

Use the repository's single source of truth for commitments. Do not subtract the same reservation twice.

## 26.6 Locks

Lock:

```text
matching MitigationStep
source InventoryPosition
destination InventoryPosition
```

The source check and reservation update must be atomic.

## 26.7 Effects

Atomically increase source `reservedQuantity` by the transfer quantity.

Create `InventoryTransfer`:

```text
mitigationPlanId
partId
sourceWarehouseId
destinationWarehouseId
quantity
status = approved
reason
requestedBy = actorId
approvedBy = actorId
requestedAt = executedAt
approvedAt = executedAt
```

Generate a unique transfer number using repository conventions.

Update MitigationStep:

```text
status = completed
executedAt = executedAt
failureReason = null
```

Do not:

- decrease source on-hand quantity yet;
- increase destination on-hand quantity yet;
- mark the transfer completed;
- change unrelated inventory rows.

## 26.8 Inventory example

Before:

```text
source onHand = 100
source reserved = 20
safety stock = 30
transferable = 50
```

Transfer quantity:

```text
40
```

After action:

```text
source onHand = 100
source reserved = 60
destination onHand = unchanged
transfer status = approved
```

## 26.9 Output

```ts
interface ReallocateInventoryResult {
  inventoryTransferId: string;
  transferNumber: string;
  mitigationPlanId: string;
  mitigationStepId: string;
  partId: string;
  sourceWarehouseId: string;
  destinationWarehouseId: string;
  quantity: number;
  transferStatus: "approved";
  sourceInventoryBefore: {
    onHandQuantity: number;
    reservedQuantity: number;
    transferableQuantity: number;
  };
  sourceInventoryAfter: {
    onHandQuantity: number;
    reservedQuantity: number;
    transferableQuantity: number;
  };
}
```

## 26.10 Minimum tests

- safe surplus is reserved and transfer created;
- destination on-hand does not change;
- source safety stock is preserved;
- insufficient stock is rejected;
- concurrent requests cannot over-reserve;
- source and destination equality is rejected;
- missing matching step is rejected;
- duplicate child execution does not create another transfer;
- parent rollback removes reservation and transfer;
- audit records inventory before/after and transfer creation.

---

# 27. Action specification: `completeInventoryTransfer`

## 27.1 Purpose

Record physical arrival of previously approved or in-transit inventory.

## 27.2 Public input

```text
inventoryTransferId: string
completedAt: datetime
reason: string
```

## 27.3 Allowed roles

```text
OperationsManager
Admin
```

This is a top-level action and may occur after the mitigation plan is completed.

## 27.4 Preconditions

- InventoryTransfer exists.
- Transfer status is `approved` or `in_transit`.
- Transfer quantity is positive.
- Source InventoryPosition exists.
- Destination InventoryPosition exists.
- Source on-hand quantity is at least the transfer quantity.
- Source reserved quantity includes at least the transfer quantity.
- `completedAt` is not before `requestedAt`.
- `completedAt` is not unreasonably in the future.
- Reason is present.

If transfer status is already `completed`, a new idempotency key must not silently complete it again. Return `INVENTORY_TRANSFER_ALREADY_COMPLETED`, unless the request is a replay with the original successful idempotency key, in which case return the stored original result.

## 27.5 Locks

Lock in deterministic order:

```text
InventoryTransfer
source InventoryPosition
destination InventoryPosition
```

## 27.6 Transactional effects

For transfer quantity `q`:

```text
source.onHandQuantity -= q
source.reservedQuantity -= q
destination.onHandQuantity += q
transfer.status = completed
transfer.completedAt = input completedAt
```

Set inventory update timestamps according to the database model.

Do not let any resulting quantity become negative.

If the data model tracks destination `inTransitQuantity` for this transfer, decrement it exactly once. If approved transfers are tracked only through the transfer table in Version 1, do not invent an in-transit inventory mutation.

The related MitigationStep should already be completed because its command was successfully initiated. Do not change the plan back to executing.

## 27.7 Example

Before:

```text
transfer quantity = 40

source:
  onHand = 100
  reserved = 60

destination:
  onHand = 20
```

After:

```text
source:
  onHand = 60
  reserved = 20

destination:
  onHand = 60

transfer = completed
```

## 27.8 Output

```ts
interface CompleteInventoryTransferResult {
  inventoryTransferId: string;
  previousStatus: "approved" | "in_transit";
  newStatus: "completed";
  completedAt: string;
  sourceInventoryBefore: {
    onHandQuantity: number;
    reservedQuantity: number;
  };
  sourceInventoryAfter: {
    onHandQuantity: number;
    reservedQuantity: number;
  };
  destinationInventoryBefore: {
    onHandQuantity: number;
  };
  destinationInventoryAfter: {
    onHandQuantity: number;
  };
}
```

## 27.9 Minimum tests

- approved transfer completes atomically;
- in-transit transfer completes atomically;
- source on-hand and reserved both decrease;
- destination on-hand increases;
- negative quantities are impossible;
- already completed transfer is rejected under a new key;
- original idempotent retry returns original result;
- concurrent completion requests produce one success;
- rollback leaves all three records unchanged.

---

# 28. Action specification: `expeditePurchaseOrder`

## 28.1 Purpose

Apply an approved mitigation step that moves an open purchase order's expected delivery date earlier and records the additional cost.

## 28.2 Public action parameters

```text
purchaseOrderId: string
newExpectedDeliveryDate: date
additionalCost: currency greater than or equal to 0
mitigationPlanId: string
reason: string
```

## 28.3 Allowed roles

```text
OperationsManager
Admin
```

## 28.4 Invocation rule

Default Version 1 policy:

```text
invocationMode = child_action
parent action = executeMitigationPlan
```

Do not expose this action to AI or bypass the approved-plan workflow.

## 28.5 Expeditable statuses

```text
submitted
confirmed
partially_received
delayed
```

Reject:

```text
draft
received
cancelled
```

## 28.6 Preconditions

- PurchaseOrder exists.
- Status is expeditable.
- PurchaseOrder has positive open quantity.
- `expedited = false` in Version 1.
- `newExpectedDeliveryDate` is earlier than the current `expectedDeliveryDate`.
- `newExpectedDeliveryDate` is not before the action date.
- `additionalCost >= 0`.
- Plan exists and is executing under the parent transaction.
- Matching MitigationStep exists and has type `expedite_purchase_order`.
- Step target and parameters match the input.
- The PurchaseOrder contains a part relevant to the mitigation plan.
- Recalculated expedite cost remains within tolerance.
- Reason is present.

Version 1 does not support expediting the same PO multiple times. Return:

```text
PURCHASE_ORDER_ALREADY_EXPEDITED
```

## 28.7 Locks

Lock:

```text
MitigationStep
PurchaseOrder
relevant PurchaseOrderLine rows when needed for open-quantity validation
```

## 28.8 Effects

Update PurchaseOrder:

```text
expedited = true
expectedDeliveryDate = newExpectedDeliveryDate
expediteCost = additionalCost
updatedAt = executedAt
```

Update MitigationStep:

```text
status = completed
executedAt = executedAt
failureReason = null
```

Do not change the normal purchase-order status.

## 28.9 Output

```ts
interface ExpeditePurchaseOrderResult {
  purchaseOrderId: string;
  mitigationPlanId: string;
  mitigationStepId: string;
  previousExpectedDeliveryDate: string;
  newExpectedDeliveryDate: string;
  additionalCost: string;
  expedited: true;
}
```

## 28.10 Minimum tests

- confirmed PO is expedited;
- partially received PO with open quantity is expedited;
- received or cancelled PO is rejected;
- already expedited PO is rejected;
- later or equal delivery date is rejected;
- date in the past is rejected;
- irrelevant PO is rejected;
- child rollback restores original date and cost;
- audit contains old/new date and cost.

---

# 29. Action specification: `prioritizeShipment`

## 29.1 Purpose

Increase the priority of an eligible shipment linked to an impacted order.

## 29.2 Public action parameters

```text
shipmentId: string
newPriority: low | normal | high | critical
mitigationPlanId: string
reason: string
```

## 29.3 Allowed roles

```text
OperationsManager
Admin
```

## 29.4 Invocation rule

Default Version 1 policy:

```text
invocationMode = child_action
parent action = executeMitigationPlan
```

## 29.5 Priority order

```text
low < normal < high < critical
```

The requested priority must be strictly higher than the current priority.

## 29.6 Eligible shipment statuses

```text
planned
ready
```

Reject shipped, in-transit, delivered, delayed, or cancelled shipments for this Version 1 prioritization action. A future workflow may support carrier intervention after shipment, but it is not part of this action.

## 29.7 Preconditions

- Shipment exists.
- Status is `planned` or `ready`.
- New priority is a declared enum value.
- New priority is strictly greater than current priority.
- Linked CustomerOrder is impacted by the plan's RiskEvent.
- Inventory or allocation exists for the shipment/order.
- Plan exists and is executing under the parent transaction.
- Matching MitigationStep exists and has type `prioritize_shipment`.
- Step target and parameters match the action input.
- Reason is present.

Shipment priority cannot create missing inventory. Reject a step that attempts to use prioritization as a substitute for unavailable supply.

The current schema does not contain shipment-line quantities. Use existing order allocation and warehouse inventory records as the Version 1 evidence. Do not invent shipment quantities.

## 29.8 Locks

Lock:

```text
MitigationStep
Shipment
linked CustomerOrder and relevant allocation rows when required
```

## 29.9 Effects

Update Shipment:

```text
priority = newPriority
updatedAt = executedAt
```

Update MitigationStep:

```text
status = completed
executedAt = executedAt
failureReason = null
```

Do not change shipment status or dates unless a future explicit action is added.

## 29.10 Output

```ts
interface PrioritizeShipmentResult {
  shipmentId: string;
  mitigationPlanId: string;
  mitigationStepId: string;
  previousPriority: "low" | "normal" | "high" | "critical";
  newPriority: "low" | "normal" | "high" | "critical";
  orderId: string;
}
```

## 29.11 Minimum tests

- planned shipment priority increases;
- ready shipment priority increases;
- same or lower priority is rejected;
- shipped/delivered/cancelled shipment is rejected;
- non-impacted order shipment is rejected;
- missing allocation/inventory is rejected;
- child rollback restores original priority;
- audit contains old and new priority.

---

# 30. Action specification: `resolveRiskEvent`

## 30.1 Purpose

Close a disruption only after it no longer causes current operational impact and no unfinished mitigation work remains.

## 30.2 Public input

```text
riskEventId: string
resolvedAt: datetime
reason: string
```

## 30.3 Allowed roles

```text
OperationsManager
Admin
```

## 30.4 State transitions

```text
open → resolved
acknowledged → resolved
mitigated → resolved
```

## 30.5 Preconditions

- RiskEvent exists.
- Current status is `open`, `acknowledged`, or `mitigated`.
- RiskEvent is not already resolved.
- `resolvedAt` is valid and not before `detectedAt`.
- No related MitigationPlan is `pending_approval`, `approved`, or `executing`.
- No related InventoryTransfer is `requested`, `approved`, or `in_transit`.
- `findImpactedOrders(riskEventId)` returns no current risk-event-caused impacted orders.
- Reason is present.

A completed or failed historical plan does not by itself block resolution. Unfinished operational work and current impact block resolution.

## 30.6 Locks and validation

Lock:

```text
RiskEvent
related active MitigationPlan rows
related active InventoryTransfer rows
```

Run the final impact function against a consistent operational snapshot.

Do not mark the event resolved based only on a plan's completed status.

## 30.7 Effects

- set `status = resolved`;
- set `resolvedAt = input resolvedAt`;
- set `updatedAt = executedAt`;
- persist or reference the final impact snapshot;
- audit the previous state, final state, actor, time, and reason.

## 30.8 Output

```ts
interface ResolveRiskEventResult {
  riskEventId: string;
  previousStatus: "open" | "acknowledged" | "mitigated";
  newStatus: "resolved";
  resolvedBy: string;
  resolvedAt: string;
  finalImpactedOrderCount: 0;
  activePlanCount: 0;
  unfinishedTransferCount: 0;
}
```

## 30.9 Minimum tests

- mitigated risk with no impact or unfinished work resolves;
- open risk with no impact may resolve;
- active impacted orders block resolution;
- pending/approved/executing plan blocks resolution;
- approved or in-transit transfer blocks resolution;
- completed transfer does not block resolution;
- already resolved risk is rejected under a new key;
- idempotent retry returns original result;
- final impact snapshot is audited.

---

## 31. Action handler interface

Use repository conventions, but a useful abstraction is:

```ts
interface ActionHandler<TInput, TOutput> {
  execute(args: {
    input: TInput;
    context: ActionExecutionContext;
    transaction: DatabaseTransaction;
    metadata: NormalizedActionDefinition;
  }): Promise<{
    data: TOutput;
    affectedObjects: AffectedObjectRecord[];
    auditChanges: AuditChange[];
    warnings: string[];
  }>;
}
```

Handlers should not:

- open an independent transaction when one is supplied;
- authenticate users;
- parse HTTP requests;
- decide public error status codes;
- read raw YAML directly;
- commit or roll back the transaction directly;
- write execution success outside the Action Engine.

Handlers should:

- enforce action-specific business rules;
- lock and mutate through the supplied transaction;
- return typed effects and evidence;
- throw or return typed domain errors.

---

## 32. Handler registry

The action handler registry must map stable ontology handler names to implementations:

```text
createRiskEvent
acknowledgeRiskEvent
generateMitigationPlan
submitMitigationPlan
approveMitigationPlan
rejectMitigationPlan
executeMitigationPlan
reallocateInventory
completeInventoryTransfer
expeditePurchaseOrder
prioritizeShipment
resolveRiskEvent
```

Application startup must fail when:

- ontology metadata references an unknown action handler;
- a duplicate handler key is registered;
- a critical action lacks required transaction, audit, or idempotency metadata;
- `AIAgent` is granted a prohibited critical action;
- an action state transition references an unknown state.

Do not dynamically evaluate handler names from YAML.

---

## 33. API behavior

Recommended endpoint shape:

```http
POST /actions/:actionName
Idempotency-Key: <key>
Content-Type: application/json
```

Request body:

```json
{
  "parameters": {}
}
```

The API layer must:

- validate `actionName` as a safe registry key;
- reject missing idempotency key;
- authenticate the caller;
- call the shared Action Engine;
- map typed domain errors to the project's structured error format;
- never accept actor roles or internal execution fields from the body;
- never expose raw database errors.

For idempotent replay, return the same business result and indicate replay through a response field or header according to repository conventions.

Internal child actions should use an internal Action Engine method, not an HTTP call back into the application.

---

## 34. MCP and AI restrictions

The MCP layer may expose:

```text
generateMitigationPlan
```

only when the authenticated AI identity has the `AIAgent` role and the tool is configured as draft-only.

Do not expose these as AI-executable tools:

```text
createRiskEvent
acknowledgeRiskEvent
submitMitigationPlan
approveMitigationPlan
rejectMitigationPlan
executeMitigationPlan
reallocateInventory
completeInventoryTransfer
expeditePurchaseOrder
prioritizeShipment
resolveRiskEvent
```

The AI may:

- call read-only functions;
- explain impact evidence;
- recommend mitigation;
- create a draft plan through the governed action;
- show the user which human approval is required.

The AI may not impersonate a human role or provide `parentExecutionId`/child invocation context.

Record AI tool inputs, outputs, object IDs, function evidence, model identifier, workflow run ID, and timestamps when available. Do not store hidden chain-of-thought.

---

## 35. Suggested backend structure

Adapt to the existing repository.

```text
src/
└── ontology/
    ├── actions/
    │   ├── createRiskEvent.ts
    │   ├── acknowledgeRiskEvent.ts
    │   ├── generateMitigationPlan.ts
    │   ├── submitMitigationPlan.ts
    │   ├── approveMitigationPlan.ts
    │   ├── rejectMitigationPlan.ts
    │   ├── executeMitigationPlan.ts
    │   ├── reallocateInventory.ts
    │   ├── completeInventoryTransfer.ts
    │   ├── expeditePurchaseOrder.ts
    │   ├── prioritizeShipment.ts
    │   └── resolveRiskEvent.ts
    │
    ├── runtime/
    │   ├── action-engine.ts
    │   ├── action-context.ts
    │   ├── action-registry.ts
    │   ├── action-errors.ts
    │   ├── action-result.ts
    │   └── action-config.ts
    │
    ├── idempotency/
    │   ├── idempotency-service.ts
    │   ├── parameter-normalizer.ts
    │   └── parameter-hash.ts
    │
    ├── audit/
    │   ├── action-audit-service.ts
    │   ├── affected-object-recorder.ts
    │   └── snapshot-sanitizer.ts
    │
    ├── permissions/
    │   └── ontology-authorization-service.ts
    │
    └── functions/
        └── existing read-only handlers
```

Use the repository's selected language and naming conventions. Do not create parallel database or authentication layers.

---

## 36. Database requirements to verify

Before implementation, inspect existing migrations and models for support equivalent to:

```text
action execution records
action affected-object records
audit records
idempotency key and parameter hash
execution status
stored success result
stored safe failure result
parent execution reference
ontology/action version
created/started/completed timestamps
```

Also verify constraints for:

```text
non-negative inventory quantities
reservedQuantity <= onHandQuantity when that is the chosen invariant
unique inventory position per warehouse + part
unique transfer number
valid plan/risk/transfer statuses
foreign keys for plans, steps, transfers, POs, shipments, and inventory
```

Do not redesign the database inside this task without first reconciling with `supplygraph_database_context.md`.

When a required execution field is absent, add the smallest migration needed and document why it is required by this action specification.

---

## 37. Testing strategy

### 37.1 Unit tests

Test pure or isolated components:

- parameter normalization;
- stable parameter hashing;
- reason validation;
- state-transition validation;
- priority comparison;
- transferable-inventory calculation;
- duplicate-risk matching;
- error mapping;
- permission checks;
- lock-order builder.

### 37.2 Handler integration tests

Run handlers against a real test PostgreSQL database or the repository's established integration-test environment.

Cover:

- successful writes;
- rollback behavior;
- row locking;
- affected-object records;
- audit snapshots;
- state transitions;
- foreign-key behavior;
- timestamp consistency.

Do not rely only on mocked repositories for transaction and concurrency behavior.

### 37.3 Idempotency tests

For every action:

- first request executes;
- exact replay returns stored result;
- replay creates no second business effect;
- same key with different input is rejected;
- concurrent same-key requests produce one execution;
- failed execution returns stored failure;
- stale in-progress policy works.

### 37.4 Concurrency tests

At minimum:

- two inventory transfers compete for the same stock;
- two drafts attempt submission for the same risk;
- approval and rejection race;
- two plan executions race;
- two transfer completions race.

Assert one valid winner and no broken quantities or invalid states.

### 37.5 Parent transaction tests

Create a plan with at least two different step types.

Force the second step to fail after the first handler has mutated state.

Assert:

```text
first step effect rolled back
no successful child business record remains
plan failure is recorded
parent action is failed
inventory/PO/shipment state is unchanged
```

### 37.6 Permission tests

Verify every role/action pair, especially:

- Viewer denied all actions;
- AIAgent allowed only `generateMitigationPlan`;
- Planner cannot approve or execute;
- submitter cannot approve own plan;
- OperationsManager and Admin can execute critical actions when all preconditions pass.

### 37.7 Audit tests

Assert:

- action name and version recorded;
- actor and invocation source recorded;
- reason recorded where required;
- before/after values are accurate;
- parent-child links are present;
- failed actions record safe errors;
- secrets and raw stack traces are absent.

---

## 38. Deterministic demo scenario

Create an integration fixture equivalent to:

```text
Supplier S-102 is delayed by 5 days.
A Planner creates RiskEvent R-102.
The Planner acknowledges the risk.
The recommendation identifies impacted orders and proposes:
  1. transfer 40 units of Part B from Warehouse B to Warehouse A;
  2. expedite PurchaseOrder PO-200;
  3. prioritize Shipment SHIP-881.
A draft MitigationPlan is generated.
The Planner submits it.
A different OperationsManager approves it.
The OperationsManager executes it.
All three operational commands succeed atomically.
The plan becomes completed.
The risk becomes mitigated.
The transfer remains approved until inventory physically arrives.
The transfer is later completed, moving inventory atomically.
After impact analysis returns no affected orders and no unfinished work remains,
the OperationsManager resolves the risk.
```

Also create failure variants:

```text
insufficient transfer inventory at execution time
purchase order cancelled before execution
shipment already shipped before execution
approver equals submitter
same idempotency key with different quantity
network retry after successful transfer completion
```

Store expected DTOs and audit records as fixtures when that matches repository conventions.

---

## 39. Implementation order for Codex

Implement in this order unless the repository already contains some pieces.

### Phase 1: Inspect and align

- read ontology metadata and database context;
- inspect existing action-execution and audit tables;
- inspect authentication and role middleware;
- inspect transaction and error conventions;
- identify existing function handlers to reuse.

### Phase 2: Shared contracts

- runtime context;
- action request/result DTOs;
- typed domain errors;
- validated action configuration;
- handler interface;
- stable handler registry.

### Phase 3: Idempotency

- canonical parameter normalization;
- parameter hashing;
- database unique claim;
- replay behavior;
- stale in-progress policy;
- tests.

### Phase 4: Action Engine

- metadata resolution;
- authentication and authorization integration;
- schema validation;
- reason enforcement;
- business transaction wrapper;
- affected-object collection;
- audit recording;
- success/failure persistence;
- API adapter.

### Phase 5: Risk actions

```text
createRiskEvent
acknowledgeRiskEvent
```

### Phase 6: Plan lifecycle before execution

```text
generateMitigationPlan
submitMitigationPlan
approveMitigationPlan
rejectMitigationPlan
```

### Phase 7: Operational child actions

```text
reallocateInventory
expeditePurchaseOrder
prioritizeShipment
```

### Phase 8: Parent execution

```text
executeMitigationPlan
```

Add atomic rollback and child audit tests before continuing.

### Phase 9: Transfer and risk completion

```text
completeInventoryTransfer
resolveRiskEvent
```

### Phase 10: Final validation

Run:

```text
formatter
lint
type checking
unit tests
integration tests
concurrency tests
production build or backend startup check
```

Do not disable checks to make the implementation pass.

---

## 40. Version 1 exclusions

Do not add these to complete this task:

```text
generic PATCH object endpoint
generic action builder
ontology editing or publishing
new ontology object types
plan editing after submission
plan reopen workflow
plan cancellation workflow
manual step skipping
partial-success plan execution
compensation workflow for external systems
real supplier/carrier/ERP API calls
background orchestration platform
message broker unless already required by the repository
real-time logistics tracking
inventory-transfer shipping action
purchase-order renegotiation action
multiple expedite operations on one PO
automatic AI approval
automatic AI execution
LLM-generated numeric writes
hidden writes inside functions
```

Version 1 should demonstrate a narrow, complete, governed workflow rather than a generic enterprise workflow engine.

---

## 41. Acceptance criteria

The action implementation is complete only when all conditions below are satisfied.

### Shared Action Engine

- all 12 stable handlers exist and are registered;
- unknown handler references fail startup;
- action metadata comes from the ontology registry;
- authentication and role authorization are enforced server-side;
- declared schemas validate inputs;
- unknown parameters are rejected;
- required reasons are enforced;
- every action requires an idempotency key;
- parameter hashes are stable;
- exact retries do not duplicate effects;
- different parameters with the same key are rejected;
- operational writes run transactionally;
- success result and business changes commit together;
- failures roll back business changes;
- execution and audit history are recorded;
- errors are typed and safe.

### Concurrency

- inventory cannot be over-reserved;
- the same plan cannot be approved/rejected/executed twice;
- only one active governed plan exists per risk;
- transfer completion cannot run twice;
- deterministic lock ordering is used;
- database retryable errors are surfaced safely.

### Risk lifecycle

- supplier-delay risk creation is governed and deduplicated;
- acknowledgement enforces `open → acknowledged`;
- risk resolves only with no current impact or unfinished work;
- invalid state transitions are rejected.

### Plan lifecycle

- recommendation function remains read-only;
- plan generation creates a draft and typed steps;
- no-feasible recommendation creates no plan;
- submission requires acknowledgement and current validation;
- submitted steps are frozen;
- approver differs from submitter;
- approval performs no operational writes;
- rejection is terminal;
- execution revalidates under locks;
- all required steps execute atomically;
- parent and child action records are linked;
- successful execution completes the plan and mitigates the risk;
- physical transfer completion remains separate.

### Operational actions

- transfer reservation preserves safety stock;
- destination on-hand does not increase before completion;
- transfer completion updates both inventories atomically;
- only eligible open POs can be expedited;
- expedite date must move earlier and remain valid;
- only eligible shipments can be prioritized;
- priority must strictly increase;
- operational child actions cannot be invoked by AI;
- all before/after values are audited.

### Testing and quality

- focused unit tests pass;
- integration tests pass against PostgreSQL;
- concurrency tests pass;
- rollback tests prove no partial effects;
- lint and type checks pass;
- production build or backend startup succeeds;
- existing tests remain green;
- no unrelated features or dependency upgrades are introduced.

---

## 42. Expected final output from Codex

After implementation, Codex should report:

```text
1. Files created.
2. Files modified.
3. Database migrations added, if any.
4. Stable action handlers registered.
5. Idempotency strategy implemented.
6. Transaction and locking strategy implemented.
7. Audit and affected-object recording implemented.
8. API routes or adapters added.
9. Tests added.
10. Commands run.
11. Test, lint, type-check, and build results.
12. Any documented limitation or deviation from this specification.
```

Do not claim completion when concurrency, rollback, idempotency replay, or audit behavior has not been tested.
