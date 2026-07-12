# Ontology Permissions and Authorization Implementation Context

## What this file is about

This file defines how permissions and authorization must be implemented in the **Operational Ontology** project. It is an implementation context for a Codex agent or developer building the shared authorization runtime used by ontology object APIs, link traversal, functions, governed actions, audit history, the Ontology Manager, Object Explorer, and MCP/AI tools.

This document does **not** redesign authentication, database tables, ontology objects, functions, or actions. Those areas are defined in their existing context files. This document defines the security boundary that decides whether an authenticated actor may attempt an ontology operation and what information may be returned.

The implementation must preserve the central project goal: operational data should be exposed as governed ontology objects, links, functions, and actions rather than as unrestricted CRUD endpoints. AI may investigate and recommend, but critical operational changes require authorized human control.

---

## 1. Scope

Implement a central permission system that protects:

- ontology metadata inspection;
- object listing, search, and reading;
- property visibility;
- stored and derived link traversal;
- ontology function execution;
- ontology action execution;
- audit history access;
- MCP and AI tools;
- trusted internal child-action dispatch;
- future ontology publishing operations.

Every public ontology entry point must use the same authorization runtime.

### Version 1 non-goals

Do not implement the following in Version 1:

- tenant-level authorization;
- warehouse-, region-, supplier-, or row-level access scopes;
- custom user-created roles;
- a visual role editor;
- dynamic permission changes without ontology reload or publication;
- emergency Admin override behavior;
- service-account operational permissions;
- a standalone policy database or external policy engine;
- field-level encryption;
- security-event database storage.

The interfaces may leave room for future scope support, but unused complexity must not be added now.

---

## 2. Core security principle

Permissions and business rules are separate concerns.

```text
Authentication
    answers: Who is calling?

Authorization
    answers: Is this actor generally allowed to attempt this operation?

Business validation
    answers: Is the operation valid for this object in its current state?
```

Example:

```text
OperationsManager may generally approve mitigation plans.

Authorization check:
OperationsManager -> approveMitigationPlan is allowed.

Business checks:
- the plan exists;
- the plan is PENDING_APPROVAL;
- the current actor did not submit the same plan.
```

The authorization layer must not check plan state, inventory availability, quantities, workflow transitions, or other domain facts. Those checks remain in the Function Engine or Action Engine.

The required execution order is:

```text
Authenticate
-> Build trusted ActorContext
-> Authorize
-> Validate input
-> Validate business rules
-> Execute
-> Apply response projection
-> Record execution and audit data when appropriate
```

---

## 3. Confirmed Version 1 roles

Use only these five ontology roles:

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

Do not add a sixth public or internal ontology role in Version 1.

### 3.1 Viewer

Viewer can inspect operations but cannot change operational state.

Viewer may:

- inspect approved ontology metadata;
- list, search, and read operational objects;
- traverse allowed links;
- run safe read-only analytical functions;
- view limited object activity summaries.

Viewer may not:

- generate formal mitigation recommendations;
- validate mitigation plans;
- execute any governed write action;
- inspect detailed or global audit history;
- publish ontology metadata.

### 3.2 Planner

Planner can investigate disruptions and prepare governed responses.

Planner may:

- do everything a Viewer can do;
- run operational analysis and recommendation functions;
- create and acknowledge risk events;
- generate draft mitigation plans;
- submit mitigation plans for approval;
- inspect object-specific operational history.

Planner may not:

- approve or reject plans;
- execute approved plans;
- directly reallocate inventory;
- directly expedite purchase orders;
- directly prioritize shipments;
- resolve risk events through manager-only actions.

### 3.3 OperationsManager

OperationsManager can review and execute governed operational decisions.

OperationsManager may:

- do everything a Planner can do;
- approve and reject mitigation plans;
- execute approved mitigation plans;
- perform declared operational actions;
- complete inventory transfers;
- resolve risk events;
- inspect global operational audit history.

### 3.4 Admin

Admin can manage the platform and inspect all operational and technical governance information.

Admin may:

- perform all currently declared operational actions;
- inspect complete audit and execution details;
- inspect role and permission metadata;
- receive future ontology publication capabilities;
- manage role assignments outside this authorization runtime.

Admin must still obey action business rules. Admin does not bypass required approval states, transaction rules, separation-of-duties rules, or idempotency rules.

Admin also does not automatically receive access to unknown future resources. New resources require explicit policies.

### 3.5 AIAgent

AIAgent can investigate and recommend but cannot make final operational decisions.

AIAgent may:

- list, search, and read approved ontology objects through an AI-safe projection;
- traverse approved links;
- execute approved read-only functions;
- recommend mitigation approaches;
- generate a draft mitigation plan;
- explain evidence and recommendations.

AIAgent may not:

- create or acknowledge risk events;
- submit a mitigation plan;
- approve or reject a mitigation plan;
- execute a mitigation plan;
- reallocate inventory;
- complete inventory transfers;
- expedite purchase orders;
- prioritize shipments;
- resolve risk events;
- publish ontology metadata;
- browse raw audit logs or technical execution records.

---

## 4. Actor model

Authorization must evaluate more than role names. It must also evaluate the identity type and the trusted source through which the operation was invoked.

```ts
export type ActorType =
  | "human"
  | "ai_agent"
  | "service";

export type InvocationSource =
  | "web_app"
  | "api"
  | "mcp"
  | "ai_workflow"
  | "background_job"
  | "internal";

export type OntologyRole =
  | "Viewer"
  | "Planner"
  | "OperationsManager"
  | "Admin"
  | "AIAgent";

export interface ActorContext {
  actorId: string;
  actorType: ActorType;
  roles: OntologyRole[];
  invocationSource: InvocationSource;
}
```

### Trusted actor context requirements

The client must never be allowed to provide or override:

- `actorId`;
- `actorType`;
- `roles`;
- `invocationSource`;
- trusted internal-dispatch fields.

These values must come from a trusted authentication or runtime adapter, such as:

- an authenticated web session;
- a verified API token;
- an authenticated MCP connection;
- a trusted AI workflow identity;
- an internal Action Engine call.

Reject or ignore role and actor information sent inside normal request bodies.

`service` remains part of the type model for future compatibility, but Version 1 grants service identities no operational capability. A service identity is denied unless a later policy explicitly permits it.

---

## 5. Capability model

Do not scatter checks such as `if role === "Planner"` across routes or handlers. The runtime must evaluate capabilities against ontology resources.

Use these Version 1 capabilities:

```ts
export type AuthorizationCapability =
  | "ontology.metadata.read"
  | "ontology.metadata.publish"
  | "permission.metadata.read"
  | "object.list"
  | "object.search"
  | "object.read"
  | "property.read"
  | "link.traverse"
  | "function.execute"
  | "action.execute"
  | "audit.read"
  | "audit.read.full";
```

Capabilities must be resource-specific.

Examples:

```text
object.read -> CustomerOrder
function.execute -> findImpactedOrders
action.execute -> approveMitigationPlan
link.traverse -> riskEventImpactedOrders
audit.read -> object_history
```

There must be no generic `object.update` or unrestricted table-write capability. Operational writes happen only through declared ontology actions.

---

## 6. Authorization resources

```ts
export type AuthorizationResourceType =
  | "ontology"
  | "objectType"
  | "object"
  | "property"
  | "linkType"
  | "function"
  | "action"
  | "auditLog";

export interface AuthorizationResource {
  resourceType: AuthorizationResourceType;

  /**
   * Ontology key such as CustomerOrder,
   * findImpactedOrders, or approveMitigationPlan.
   */
  resourceKey: string;

  /** Concrete object identifier when relevant. */
  objectId?: string;

  /** Required for property-specific requests. */
  propertyKey?: string;
}

export interface TrustedAuthorizationContext {
  internalDispatch?: boolean;
  parentActionKey?: string;
  parentExecutionId?: string;
}

export interface AuthorizationRequest {
  actor: ActorContext;
  capability: AuthorizationCapability;
  resource: AuthorizationResource;

  /**
   * This context may only be created by trusted runtime code.
   * It must never be accepted from HTTP, MCP, or AI input.
   */
  trustedContext?: TrustedAuthorizationContext;
}
```

---

## 7. Central AuthorizationService

Create one shared service.

```ts
export interface AuthorizationService {
  authorize(
    request: AuthorizationRequest
  ): AuthorizationDecision;

  authorizeOrThrow(
    request: AuthorizationRequest
  ): AuthorizationDecision;
}
```

Every ontology entry point must call this service:

- ontology metadata APIs;
- object list, search, and read APIs;
- property projection;
- link traversal;
- Function Engine;
- Action Engine;
- audit APIs;
- Ontology Manager;
- Object Explorer;
- MCP tools;
- AI workflows.

Repositories must not perform public authorization by themselves, and public routes must not call repositories directly.

Correct boundary:

```text
Public adapter
-> Ontology runtime service
-> AuthorizationService
-> Repository or engine
```

Incorrect boundary:

```text
Public route or MCP tool
-> Repository
```

---

## 8. Authorization decision

```ts
export type AuthorizationReasonCode =
  | "ALLOWED"
  | "NOT_AUTHENTICATED"
  | "ACTOR_INACTIVE"
  | "POLICY_NOT_FOUND"
  | "ROLE_NOT_ALLOWED"
  | "ACTOR_TYPE_NOT_ALLOWED"
  | "INVOCATION_SOURCE_NOT_ALLOWED"
  | "RESOURCE_NOT_ALLOWED"
  | "PROPERTY_NOT_ALLOWED"
  | "INTERNAL_DISPATCH_REQUIRED"
  | "INVALID_INTERNAL_DISPATCH"
  | "EXPLICITLY_DENIED";

export interface AuthorizationObligations {
  projectionKey?: string;
  auditView?:
    | "summary"
    | "object_history"
    | "operational"
    | "full";
}

export interface AuthorizationDecision {
  allowed: boolean;
  reasonCode: AuthorizationReasonCode;
  policyVersion: string;
  matchedRole?: OntologyRole;
  obligations?: AuthorizationObligations;
}
```

An allowed AI object read should return an obligation such as:

```json
{
  "allowed": true,
  "reasonCode": "ALLOWED",
  "policyVersion": "1.0.0",
  "matchedRole": "AIAgent",
  "obligations": {
    "projectionKey": "ai_safe"
  }
}
```

The calling runtime must enforce obligations before returning data.

---

## 9. Deny-by-default model

The permission model must use:

```yaml
permissionModel:
  version: "1.0.0"
  defaultEffect: deny
```

Rules:

1. No matching permission means deny.
2. Unknown capability means deny.
3. Unknown resource means deny.
4. Admin does not automatically receive unknown permissions.
5. A new object, link, function, or action must declare permissions before the ontology can load.
6. Runtime lookups for unknown keys must still return a denied decision.

Example:

```text
A developer adds cancelCustomerOrder without a policy.

Startup behavior:
Ontology validation fails.

Runtime defense:
Any unknown cancelCustomerOrder authorization request is denied.
```

---

## 10. Version 1 object access

Use the 16 already-defined ontology object types:

```text
Supplier
Part
Product
Warehouse
SupplierPart
ProductPartRequirement
InventoryPosition
CustomerOrder
OrderLine
Shipment
PurchaseOrder
PurchaseOrderLine
RiskEvent
MitigationPlan
MitigationStep
InventoryTransfer
```

All five roles may list, search, and read these object types.

Human roles receive the normal business projection. AIAgent receives an AI-safe projection.

### Object capability rules

For each object type, define:

```text
object.list
object.search
object.read
```

Normal properties inherit object-read permission unless a property explicitly overrides it.

### No row-level scope in Version 1

Do not filter objects by warehouse, region, supplier, or tenant based on role.

The interface may reserve future scope support:

```ts
export interface AuthorizationScope {
  tenantId?: string;
  regionIds?: string[];
  warehouseIds?: string[];
}
```

Do not use or populate this structure in Version 1.

---

## 11. Property visibility and projections

Authorization decides whether the object may be read. Projection decides which properties may be returned.

Default rule:

```text
Readable object
-> normal business properties inherit read access.

Restricted property
-> explicit property policy overrides inheritance.
```

### AI-safe projection

AIAgent may receive business facts required for analysis, including:

- ontology object identifiers;
- business statuses;
- quantities;
- dates;
- priority;
- cost and lead-time facts;
- supplier, part, product, warehouse, order, shipment, and risk references;
- plan strategy and status;
- step and transfer status;
- safe timestamps and provenance.

AIAgent must not receive unrestricted versions of:

- idempotency keys;
- request or parameter hashes;
- raw stack traces or failure diagnostics;
- authentication identifiers;
- secrets or tokens;
- technical database metadata;
- unrestricted before-and-after snapshots;
- hidden technical JSON;
- internal notes;
- human-written confidential reasons;
- `submittedBy`, `approvedBy`, or `rejectedBy` identifiers;
- complete action execution records.

Prefer safe provenance such as:

```json
{
  "generatedByType": "human",
  "approved": true,
  "approvedAt": "2026-07-11T20:10:00Z"
}
```

Do not return hidden fields with `null`. Omit them completely so the projection does not reveal their presence.

Example projection metadata:

```yaml
projections:
  CustomerOrder:
    full:
      include: "*"

    ai_safe:
      include:
        - orderId
        - status
        - priority
        - orderDate
        - requiredDeliveryDate
        - customerRegion
        - remainingQuantity
```

### Property override example

```yaml
objectTypes:
  MitigationPlan:
    properties:
      approvedBy:
        type: string
        readOnly: true
        permissions:
          read:
            capability: property.read
            allowedRoles:
              - Planner
              - OperationsManager
              - Admin
            allowedActorTypes:
              - human
```

---

## 12. Link traversal permissions

All roles may traverse declared links when all required checks succeed.

For a stored link:

```text
1. Actor may read the source object type.
2. Actor may traverse the link type.
3. Actor may read the target object type.
4. Target projection is applied.
```

For a derived link:

```text
1. Actor may read the source object type.
2. Actor may traverse the derived link type.
3. Actor may execute the resolver function.
4. Actor may read the target object type.
5. Target projection is applied.
```

Example:

```text
RiskEvent
-> impactedOrders
-> CustomerOrder

Required checks:
object.read:RiskEvent
link.traverse:riskEventImpactedOrders
function.execute:findImpactedOrders
object.read:CustomerOrder
```

A link resolver must never bypass Function Engine authorization.

---

## 13. Function permission matrix

Use the existing 10 ontology functions and this exact matrix:

| Function | Viewer | Planner | OperationsManager | Admin | AIAgent |
|---|---:|---:|---:|---:|---:|
| `findImpactedParts` | Yes | Yes | Yes | Yes | Yes |
| `findImpactedProducts` | Yes | Yes | Yes | Yes | Yes |
| `findImpactedOrders` | Yes | Yes | Yes | Yes | Yes |
| `calculateStockoutRisk` | Yes | Yes | Yes | Yes | Yes |
| `getInventoryAvailability` | Yes | Yes | Yes | Yes | Yes |
| `findAlternativeWarehouses` | Yes | Yes | Yes | Yes | Yes |
| `findExpeditablePurchaseOrders` | Yes | Yes | Yes | Yes | Yes |
| `rankImpactedOrders` | Yes | Yes | Yes | Yes | Yes |
| `recommendMitigationPlan` | No | Yes | Yes | Yes | Yes |
| `validateMitigationPlan` | No | Yes | Yes | Yes | No |

`validateMitigationPlan` may still be invoked internally by governed human action flows after the relevant action has been authorized. It must not be directly exposed as an AI capability.

---

## 14. Action permission matrix

Use the existing 12 ontology actions and this exact matrix:

| Action | Viewer | Planner | OperationsManager | Admin | AIAgent |
|---|---:|---:|---:|---:|---:|
| `createRiskEvent` | No | Yes | Yes | Yes | No |
| `acknowledgeRiskEvent` | No | Yes | Yes | Yes | No |
| `generateMitigationPlan` | No | Yes | Yes | Yes | Yes |
| `submitMitigationPlan` | No | Yes | Yes | Yes | No |
| `approveMitigationPlan` | No | No | Yes | Yes | No |
| `rejectMitigationPlan` | No | No | Yes | Yes | No |
| `executeMitigationPlan` | No | No | Yes | Yes | No |
| `reallocateInventory` | No | No | Yes | Yes | No |
| `completeInventoryTransfer` | No | No | Yes | Yes | No |
| `expeditePurchaseOrder` | No | No | Yes | Yes | No |
| `prioritizeShipment` | No | No | Yes | Yes | No |
| `resolveRiskEvent` | No | No | Yes | Yes | No |

`generateMitigationPlan` is the only Version 1 action callable by AIAgent. It must only create a draft and must not submit, approve, reserve, or execute operational changes.

---

## 15. Actor-type restrictions

Critical actions must explicitly permit only human actors.

The following actions require:

```yaml
allowedActorTypes:
  - human
```

Actions:

- `createRiskEvent`;
- `acknowledgeRiskEvent`;
- `submitMitigationPlan`;
- `approveMitigationPlan`;
- `rejectMitigationPlan`;
- `executeMitigationPlan`;
- `reallocateInventory`;
- `completeInventoryTransfer`;
- `expeditePurchaseOrder`;
- `prioritizeShipment`;
- `resolveRiskEvent`.

`generateMitigationPlan` permits:

```yaml
allowedActorTypes:
  - human
  - ai_agent
```

Actor-type restrictions override role grants.

Example:

```text
actorType = ai_agent
roles = [AIAgent, OperationsManager]
action = approveMitigationPlan

Result: denied
```

---

## 16. Invocation-source restrictions

Use this Version 1 policy:

| Operation | `web_app` | `api` | `mcp` | `ai_workflow` | trusted internal dispatch |
|---|---:|---:|---:|---:|---:|
| Read objects | Yes | Yes | Yes | Yes | Yes |
| Run approved functions | Yes | Yes | Yes | Yes | Yes |
| Generate draft plan | Yes | Yes | Yes | Yes | Yes |
| Submit plan | Yes | Yes | No | No | No |
| Approve or reject plan | Yes | Yes | No | No | No |
| Execute plan | Yes | Yes | No | No | No |
| Direct operational actions | Yes | Yes | No | No | Restricted |

`invocationSource` must be assigned by trusted infrastructure. Never trust a normal caller-provided header claiming that a request is internal.

---

## 17. Internal child-action dispatch

`executeMitigationPlan` may internally dispatch declared child actions such as:

- `reallocateInventory`;
- `expeditePurchaseOrder`;
- `prioritizeShipment`.

Internal dispatch is allowed only when:

1. the parent action is `executeMitigationPlan`;
2. the parent actor is an authorized human;
3. the parent plan is approved;
4. the child action is declared by a frozen `MitigationStep`;
5. the child action runs through the Action Engine;
6. the child action uses the parent transaction or approved transaction strategy;
7. the parent execution ID is recorded;
8. the accountable actor remains the authorized parent human.

Use a private runtime method such as:

```ts
actionEngine.executeChildAction({
  parentActor,
  parentExecution,
  actionKey,
  input,
});
```

The method creates trusted context internally:

```ts
const trustedContext: TrustedAuthorizationContext = {
  internalDispatch: true,
  parentActionKey: parentExecution.actionKey,
  parentExecutionId: parentExecution.executionId,
};
```

HTTP, MCP, and AI schemas must reject fields such as:

- `internalDispatch`;
- `parentActionKey`;
- `parentExecutionId`;
- `invocationSource: internal`.

Hiding these fields is not enough. The trusted context must be created in process by code that external callers cannot invoke directly.

---

## 18. Ontology permission metadata

Permissions should be authored in ontology YAML next to the relevant resources.

### Object example

```yaml
objectTypes:
  CustomerOrder:
    table: customer_orders

    permissions:
      list:
        capability: object.list
        allowedRoles:
          - Viewer
          - Planner
          - OperationsManager
          - Admin
          - AIAgent
        allowedActorTypes:
          - human
          - ai_agent

      search:
        capability: object.search
        allowedRoles:
          - Viewer
          - Planner
          - OperationsManager
          - Admin
          - AIAgent
        allowedActorTypes:
          - human
          - ai_agent

      read:
        capability: object.read
        allowedRoles:
          - Viewer
          - Planner
          - OperationsManager
          - Admin
          - AIAgent
        allowedActorTypes:
          - human
          - ai_agent
        projections:
          human: full
          ai_agent: ai_safe
```

### Function example

```yaml
functions:
  recommendMitigationPlan:
    permissions:
      execute:
        capability: function.execute
        allowedRoles:
          - Planner
          - OperationsManager
          - Admin
          - AIAgent
        allowedActorTypes:
          - human
          - ai_agent
        allowedInvocationSources:
          - web_app
          - api
          - mcp
          - ai_workflow
```

### Critical action example

```yaml
actions:
  approveMitigationPlan:
    permissions:
      execute:
        capability: action.execute
        allowedRoles:
          - OperationsManager
          - Admin
        allowedActorTypes:
          - human
        allowedInvocationSources:
          - web_app
          - api
```

### AI-safe action example

```yaml
actions:
  generateMitigationPlan:
    permissions:
      execute:
        capability: action.execute
        allowedRoles:
          - Planner
          - OperationsManager
          - Admin
          - AIAgent
        allowedActorTypes:
          - human
          - ai_agent
        allowedInvocationSources:
          - web_app
          - api
          - mcp
          - ai_workflow
```

---

## 19. Normalized PermissionRegistry

Raw YAML must not be interpreted repeatedly on every request.

At application startup:

```text
Load ontology YAML
-> validate ontology and permission metadata
-> normalize policies
-> build indexed PermissionRegistry
-> freeze registry
-> start application
```

Suggested structures:

```ts
export interface ResourcePolicy {
  capability: AuthorizationCapability;
  resourceType: AuthorizationResourceType;
  resourceKey: string;

  allowedRoles: OntologyRole[];
  deniedRoles?: OntologyRole[];

  allowedActorTypes: ActorType[];
  deniedActorTypes?: ActorType[];

  allowedInvocationSources: InvocationSource[];
  deniedInvocationSources?: InvocationSource[];

  projectionByActorType?: Partial<Record<ActorType, string>>;

  requiresTrustedInternalDispatch?: boolean;
}

export interface PermissionRegistry {
  version: string;
  defaultEffect: "deny";
  policies: ReadonlyMap<string, ResourcePolicy>;
}
```

Policy key:

```ts
export function buildPolicyKey(
  capability: AuthorizationCapability,
  resourceType: AuthorizationResourceType,
  resourceKey: string
): string {
  return `${capability}:${resourceType}:${resourceKey}`;
}
```

Examples:

```text
object.read:objectType:CustomerOrder
function.execute:function:findImpactedOrders
action.execute:action:approveMitigationPlan
link.traverse:linkType:riskEventImpactedOrders
```

The normalized registry must be immutable after startup.

---

## 20. Startup validation

The application must fail to start when permission metadata is incomplete or invalid.

Validate at least the following:

- every object type declares list, search, and read behavior or a documented inherited default;
- every function declares execution permissions;
- every action declares execution permissions;
- every link declares or safely inherits traversal permissions;
- every referenced role exists;
- every actor type is valid;
- every invocation source is valid;
- every resource key exists;
- every property override references an existing property;
- every derived link resolver references an existing function;
- every projection key exists;
- duplicate normalized permission keys are forbidden;
- the permission model default is `deny`;
- critical actions cannot include `ai_agent` or `service` in allowed actor types;
- AI-exposed actions are limited to `generateMitigationPlan` in Version 1;
- service actors receive no Version 1 operational grants.

Missing permission metadata for a newly declared resource must be treated as an ontology-definition error, not as a warning.

---

## 21. Authorization evaluation algorithm

Evaluate authorization in this order:

```text
1. Confirm ActorContext exists.
2. Confirm the actor identity is active when identity status is available.
3. Resolve the exact resource policy.
4. Apply global safety restrictions.
5. Apply denied actor-type rules.
6. Apply allowed actor-type rules.
7. Apply denied invocation-source rules.
8. Apply allowed invocation-source rules.
9. Apply explicit denied-role rules.
10. Find at least one matching allowed role.
11. Validate trusted internal-dispatch requirements.
12. Resolve obligations such as response projection or audit view.
13. Return allow.
```

Denial precedence:

```text
Global safety denial
-> actor-type denial
-> invocation-source denial
-> explicit role denial
-> missing role grant
-> allow
```

Suggested implementation:

```ts
export function authorize(
  request: AuthorizationRequest,
  registry: PermissionRegistry
): AuthorizationDecision {
  const { actor, capability, resource, trustedContext } = request;

  if (!actor?.actorId) {
    return deny(registry.version, "NOT_AUTHENTICATED");
  }

  const policyKey = buildPolicyKey(
    capability,
    resource.resourceType,
    resource.resourceKey
  );

  const policy = registry.policies.get(policyKey);

  if (!policy) {
    return deny(registry.version, "POLICY_NOT_FOUND");
  }

  if (policy.deniedActorTypes?.includes(actor.actorType)) {
    return deny(registry.version, "ACTOR_TYPE_NOT_ALLOWED");
  }

  if (!policy.allowedActorTypes.includes(actor.actorType)) {
    return deny(registry.version, "ACTOR_TYPE_NOT_ALLOWED");
  }

  if (
    policy.deniedInvocationSources?.includes(
      actor.invocationSource
    )
  ) {
    return deny(
      registry.version,
      "INVOCATION_SOURCE_NOT_ALLOWED"
    );
  }

  if (
    !policy.allowedInvocationSources.includes(
      actor.invocationSource
    )
  ) {
    return deny(
      registry.version,
      "INVOCATION_SOURCE_NOT_ALLOWED"
    );
  }

  const explicitlyDenied = actor.roles.some((role) =>
    policy.deniedRoles?.includes(role)
  );

  if (explicitlyDenied) {
    return deny(registry.version, "EXPLICITLY_DENIED");
  }

  const matchedRole = actor.roles.find((role) =>
    policy.allowedRoles.includes(role)
  );

  if (!matchedRole) {
    return deny(registry.version, "ROLE_NOT_ALLOWED");
  }

  if (policy.requiresTrustedInternalDispatch) {
    if (!trustedContext?.internalDispatch) {
      return deny(
        registry.version,
        "INTERNAL_DISPATCH_REQUIRED"
      );
    }

    if (
      !trustedContext.parentActionKey ||
      !trustedContext.parentExecutionId
    ) {
      return deny(
        registry.version,
        "INVALID_INTERNAL_DISPATCH"
      );
    }
  }

  return {
    allowed: true,
    reasonCode: "ALLOWED",
    policyVersion: registry.version,
    matchedRole,
    obligations: resolveObligations(policy, actor),
  };
}
```

Do not expose detailed internal denial reasons directly to callers.

---

## 22. Multiple-role behavior

Role grants are additive.

Example:

```text
roles = [Viewer, Planner]

Result:
Viewer read grants
+
Planner analysis and draft-workflow grants
```

Safety denials override additive grants.

Example:

```text
actorType = ai_agent
roles = [AIAgent, OperationsManager]
action = approveMitigationPlan

OperationsManager role matches,
but ai_agent actor type is forbidden.

Final result: deny.
```

Use this priority:

```text
1. System safety denial
2. Actor-type denial
3. Invocation-source denial
4. Resource-specific explicit denial
5. Matching role allow
6. No matching allow means deny
```

---

## 23. Object API enforcement

### List

```text
GET /objects/:objectType
```

Before querying, check:

```text
object.list:<objectType>
```

### Search

```text
POST /objects/:objectType/search
```

Before validating filters or returning counts, check:

```text
object.search:<objectType>
```

This avoids leaking hidden schema or record counts through search behavior.

### Read one object

```text
GET /objects/:objectType/:objectId
```

Flow:

```text
Authorize object.read
-> query object
-> apply required projection
-> return object
```

When possible, authorize object-type access before querying the object ID.

Suggested pattern:

```ts
const decision = authorizationService.authorizeOrThrow({
  actor,
  capability: "object.read",
  resource: {
    resourceType: "objectType",
    resourceKey: objectType,
    objectId,
  },
});

const object = await objectRepository.findById(
  objectType,
  objectId
);

return projectionService.apply({
  objectType,
  object,
  projectionKey:
    decision.obligations?.projectionKey ?? "full",
});
```

---

## 24. Function Engine enforcement

Every public ontology function must be invoked through one wrapper.

```ts
export async function executeOntologyFunction(
  actor: ActorContext,
  functionKey: string,
  rawInput: unknown
) {
  authorizationService.authorizeOrThrow({
    actor,
    capability: "function.execute",
    resource: {
      resourceType: "function",
      resourceKey: functionKey,
    },
  });

  const definition =
    ontologyRegistry.functions.getRequired(functionKey);

  const input = definition.inputSchema.parse(rawInput);

  const result = await definition.handler({
    actor,
    input,
  });

  return functionProjectionService.apply({
    actor,
    functionKey,
    result,
  });
}
```

Private implementation helpers do not require ontology-level authorization. Public ontology functions always do.

A derived link calling a function must use this Function Engine path or an equivalent internal path that preserves the original authorization decision.

---

## 25. Action Engine enforcement

Every external action request must follow:

```text
Authentication
-> AuthorizationService
-> parameter validation
-> business validation
-> idempotency handling
-> transaction and locking
-> action handler
-> action execution record
-> operational audit record
```

Suggested wrapper:

```ts
export async function executeOntologyAction(
  actor: ActorContext,
  actionKey: string,
  rawInput: unknown
) {
  authorizationService.authorizeOrThrow({
    actor,
    capability: "action.execute",
    resource: {
      resourceType: "action",
      resourceKey: actionKey,
    },
  });

  return actionEngine.execute({
    actor,
    actionKey,
    rawInput,
  });
}
```

Action handlers must not contain duplicated role checks.

Incorrect:

```ts
if (actor.roles.includes("OperationsManager")) {
  // permit approval
}
```

Correct handler responsibility:

```ts
if (plan.status !== "PENDING_APPROVAL") {
  throw new ActionStateError(
    "PLAN_NOT_PENDING_APPROVAL"
  );
}
```

---

## 26. MCP and AI enforcement

MCP is an adapter over the ontology runtime, not a separate access path.

Correct flow:

```text
MCP tool call
-> authenticated MCP identity
-> ActorContext
-> ontology object/function/action runtime
-> AuthorizationService
-> repository or engine
```

Do not allow MCP tools to query repositories directly.

For AIAgent, expose only tools that resolve to permitted ontology capabilities, such as:

- object search;
- object read;
- linked-object traversal;
- `findImpactedParts`;
- `findImpactedProducts`;
- `findImpactedOrders`;
- `calculateStockoutRisk`;
- `getInventoryAvailability`;
- `findAlternativeWarehouses`;
- `findExpeditablePurchaseOrders`;
- `rankImpactedOrders`;
- `recommendMitigationPlan`;
- `generateMitigationPlan`.

Do not expose AI tools for:

- `submitMitigationPlan`;
- `approveMitigationPlan`;
- `rejectMitigationPlan`;
- `executeMitigationPlan`;
- `reallocateInventory`;
- `completeInventoryTransfer`;
- `expeditePurchaseOrder`;
- `prioritizeShipment`;
- `resolveRiskEvent`.

The backend must still authorize every call. Tool hiding improves usability but is not a security boundary.

The AI should receive its own resolved capability description, not the full role matrix or permissions of other users.

---

## 27. Audit access

Audit access is separate from object access.

Use these effective views:

| Audit access | Viewer | Planner | OperationsManager | Admin | AIAgent |
|---|---:|---:|---:|---:|---:|
| Object activity summary | Yes | Yes | Yes | Yes | No |
| Object-specific detailed history | No | Yes | Yes | Yes | No |
| Global operational audit search | No | No | Yes | Yes | No |
| Before/after business snapshots | No | Limited | Yes | Yes | No |
| Human action reasons | No | Yes | Yes | Yes | No |
| Technical execution metadata | No | No | No | Yes | No |
| Idempotency and parameter hashes | No | No | No | Yes | No |
| Raw failure diagnostics | No | No | No | Yes | No |
| Safe provenance in tool output | No | No | No | No | Yes |

Suggested authorization obligations:

```text
Viewer -> auditView: summary
Planner -> auditView: object_history
OperationsManager -> auditView: operational
Admin -> auditView: full
AIAgent -> no direct audit view
```

AIAgent may receive safe provenance embedded in normal object or function results:

```json
{
  "dataAsOf": "2026-07-11T21:10:00Z",
  "planStatus": "approved",
  "lastOperationalChangeAt": "2026-07-11T20:55:00Z"
}
```

It must not browse raw audit records.

---

## 28. HTTP and public error behavior

Use these mappings:

| Condition | HTTP status |
|---|---:|
| No authenticated identity | `401` |
| Authenticated actor cannot execute known function/action | `403` |
| Object type or object existence must be concealed | `404` |
| Unknown ontology resource | `404` |
| Business-state conflict | `409` |
| Invalid parameters | `422` |
| Idempotency key reused with different input | `409` |

For object reads, prefer `404` when returning `403` would reveal resource existence.

Example external action error:

```json
{
  "error": {
    "code": "OPERATION_NOT_PERMITTED",
    "message": "You are not permitted to execute this operation."
  }
}
```

Do not expose internal reason codes such as required role names to normal callers.

Suggested error class:

```ts
export class AuthorizationError extends Error {
  constructor(
    public readonly reasonCode: AuthorizationReasonCode,
    public readonly capability: AuthorizationCapability,
    public readonly resourceType: AuthorizationResourceType,
    public readonly resourceKey: string
  ) {
    super("Authorization denied");
  }
}
```

---

## 29. Denied-attempt telemetry

A denied request must not create an operational audit record because no business operation occurred.

It should create structured security telemetry, for example:

```json
{
  "eventType": "authorization_denied",
  "actorId": "AGENT-101",
  "actorType": "ai_agent",
  "roles": ["AIAgent"],
  "invocationSource": "mcp",
  "capability": "action.execute",
  "resourceType": "action",
  "resourceKey": "approveMitigationPlan",
  "reasonCode": "ACTOR_TYPE_NOT_ALLOWED",
  "policyVersion": "1.0.0",
  "requestId": "REQ-801",
  "occurredAt": "2026-07-11T22:30:00Z"
}
```

Do not log:

- access tokens;
- cookies;
- passwords;
- secrets;
- complete action parameters;
- full private object contents;
- unrestricted before-and-after snapshots.

Structured application logs are sufficient for Version 1. Do not add a security-events table unless another context explicitly requires it.

---

## 30. Policy versioning

The permission registry must have an explicit version.

```yaml
permissionModel:
  version: "1.0.0"
  defaultEffect: deny
```

Record the permission policy version in:

- authorization decisions;
- action execution records when supported by the existing schema;
- security telemetry;
- debug and operational logs.

The purpose is to answer:

> Which permission policy was active when this operation was allowed or denied?

Permissions should change through:

```text
edit ontology metadata
-> validate
-> publish or redeploy
-> load a new immutable registry version
```

Do not mutate the in-memory registry after application startup.

---

## 31. Performance expectations

Version 1 authorization should be an in-memory indexed lookup.

Recommended:

- compile policies at startup;
- use immutable maps;
- avoid database queries for each permission decision;
- keep policy keys deterministic;
- keep authorization synchronous when possible;
- obtain roles from trusted authentication context.

Do not cache operational facts such as:

- plan state;
- object existence;
- inventory availability;
- transfer status;
- business validation results.

Those facts may change and belong to repositories or domain engines, not the permission registry.

---

## 32. Suggested module structure

Adapt names to the selected backend framework, but preserve these responsibilities:

```text
src/ontology/authorization/
  actor-context.ts
  authorization-types.ts
  authorization-error.ts
  authorization-service.ts
  permission-registry.ts
  permission-registry-builder.ts
  permission-validator.ts
  policy-key.ts
  projection-service.ts
  security-telemetry.ts

src/ontology/runtime/
  object-runtime.ts
  link-runtime.ts
  function-engine.ts
  action-engine.ts
  audit-runtime.ts

src/ontology/adapters/
  http/
  mcp/
  ai/
```

The authorization package must not import concrete HTTP route classes. Adapters depend on the authorization/runtime layer, not the other way around.

---

## 33. Testing requirements

### 33.1 Registry validation tests

Verify startup fails when:

- an object type lacks required permissions;
- a function lacks execution permissions;
- an action lacks execution permissions;
- a policy references an unknown role;
- a policy references an unknown resource;
- a derived link references an unknown resolver function;
- a property override references an unknown property;
- a critical action allows `ai_agent`;
- a critical action allows `service`;
- an AI projection does not exist;
- duplicate policies normalize to the same key;
- the default effect is not `deny`.

### 33.2 Function matrix tests

Use table-driven tests for:

```text
5 roles x 10 functions
```

Verify every expected allow and deny result from the confirmed matrix.

### 33.3 Action matrix tests

Use table-driven tests for:

```text
5 roles x 12 actions
```

Verify every expected allow and deny result from the confirmed matrix.

### 33.4 Actor-type override tests

At minimum:

```text
AI actor + OperationsManager role
-> cannot approve a plan.

AI actor + Admin role
-> cannot execute a plan.

Service actor + Admin role
-> denied in Version 1.

Human actor + AIAgent role
-> receives only AIAgent role grants.
```

### 33.5 Invocation-source tests

At minimum:

```text
Planner through web_app
-> may submit a plan.

Planner through api
-> may submit a plan.

Planner through mcp
-> may not submit a plan.

OperationsManager through ai_workflow
-> may not approve a plan.

AIAgent through mcp
-> may generate a draft plan.
```

### 33.6 Object projection tests

Verify AIAgent receives approved business fields and does not receive:

- internal notes;
- human identifiers such as `approvedBy`;
- raw audit snapshots;
- hashes;
- technical metadata;
- raw diagnostics.

Verify hidden fields are omitted, not returned as `null`.

### 33.7 Link traversal tests

At minimum:

```text
Readable source + allowed link + readable target
-> return projected target objects.

Denied link
-> traversal fails.

Derived link allowed but resolver function denied
-> traversal fails.

Target object denied
-> no target data is returned.
```

### 33.8 Bypass tests

Verify callers cannot gain access by:

- providing roles in request input;
- providing actor type in request input;
- sending `invocationSource: internal`;
- sending `internalDispatch: true`;
- sending a fake parent execution ID;
- directly invoking hidden MCP actions;
- using a public route that calls a repository without authorization;
- invoking a child action without an authorized parent execution.

### 33.9 Denied-action integration tests

When authorization denies an action:

- the handler is never called;
- no action-execution row is created;
- no operational audit row is created;
- no business record changes;
- security telemetry is emitted;
- the public response does not disclose internal policy details.

### 33.10 Deny-by-default tests

- ontology validation fails for a newly declared resource without permissions;
- an unknown runtime policy key returns `POLICY_NOT_FOUND` and denies access;
- Admin is also denied unknown resources.

---

## 34. Example end-to-end flows

### Planner submits a mitigation plan

```text
Authenticated human Planner
-> action.execute:submitMitigationPlan
-> role allowed
-> actor type allowed
-> web_app or api source allowed
-> authorization succeeds
-> Action Engine validates plan state and separation rules
-> plan is submitted
-> action execution is recorded
-> operational audit is recorded
```

### AI attempts to submit a mitigation plan

```text
Authenticated AIAgent through MCP
-> action.execute:submitMitigationPlan
-> role not allowed
-> actor type not allowed
-> authorization denied
-> action handler is never called
-> no database changes occur
-> no operational audit is created
-> security telemetry is emitted
```

### AI generates a draft plan

```text
Authenticated AIAgent through MCP
-> action.execute:generateMitigationPlan
-> role allowed
-> actor type allowed
-> MCP source allowed
-> draft plan is generated
-> status remains DRAFT
-> generatedByType is recorded as ai_agent
-> human review is required
```

### Operations Manager executes an approved plan

```text
Authenticated human OperationsManager
-> action.execute:executeMitigationPlan
-> authorization succeeds
-> Action Engine validates APPROVED state
-> execution context and steps are frozen
-> trusted child actions are dispatched
-> child actions remain accountable to the human parent actor
-> operational records change transactionally
-> action and audit records are created
```

### AI with an incorrectly attached manager role attempts approval

```text
actorType = ai_agent
roles = [AIAgent, OperationsManager]
source = mcp
action = approveMitigationPlan

Role grant exists for OperationsManager,
but actor type and invocation source are forbidden.

Result:
403-style denial for the public caller,
no handler execution,
no data changes,
security telemetry recorded.
```

---

## 35. Implementation order

Implement in this order:

1. Create authorization types and error types.
2. Extend ontology metadata schemas with permission definitions.
3. Add permission and projection validation to ontology loading.
4. Build immutable `PermissionRegistry` normalization.
5. Implement `AuthorizationService.authorize()`.
6. Implement `authorizeOrThrow()` and public error mapping.
7. Build projection handling for human and AI object responses.
8. Integrate authorization into object list, search, and read paths.
9. Integrate authorization into link traversal.
10. Integrate authorization into Function Engine.
11. Integrate authorization into Action Engine.
12. Add trusted internal child-action dispatch.
13. Integrate authorization into audit APIs.
14. Route MCP and AI tools through normal ontology runtimes.
15. Add security telemetry for denied attempts.
16. Add matrix, validation, bypass, and integration tests.

Do not implement UI role management or dynamic policy editing as part of this task.

---

## 36. Completion criteria

The permissions implementation is complete when all of the following are true:

- one shared `AuthorizationService` protects all public ontology operations;
- actor identity, role, type, and source come from trusted context;
- permissions are loaded from ontology metadata into an immutable registry;
- every object, link, function, and action has an explicit effective policy;
- unknown resources are denied;
- incomplete permission metadata prevents startup;
- all five roles match the confirmed function and action matrices;
- AI only receives safe projections;
- AI can generate a draft plan but cannot submit, approve, or execute it;
- critical actions require a human actor and approved invocation source;
- multiple roles are additive, but safety denials override grants;
- MCP and AI adapters cannot bypass the ontology runtime;
- derived links enforce resolver-function permissions;
- external callers cannot forge internal child-action context;
- denied actions cause no operational database or audit changes;
- denied attempts emit safe security telemetry;
- permission policy versions are visible in decisions and execution records where supported;
- the complete authorization test suite passes.

---

## 37. Final implementation rules

Treat these as fixed Version 1 decisions:

1. Use one central `AuthorizationService`.
2. Keep the existing five roles only.
3. Use capabilities and ontology resources, not scattered role checks.
4. Keep authentication, authorization, and business validation separate.
5. Use `actorType`, roles, and invocation source together.
6. Deny unspecified access by default.
7. Require explicit policies for every new ontology resource.
8. Allow all five roles to read the 16 operational object types.
9. Apply AI-safe projections to AIAgent reads.
10. Enforce source, link, target, and resolver permissions for link traversal.
11. Preserve the confirmed 10-function permission matrix.
12. Preserve the confirmed 12-action permission matrix.
13. Permit AIAgent to execute only `generateMitigationPlan` among actions.
14. Restrict critical actions to human actors.
15. Restrict approval, execution, and direct operational actions to web or trusted API sources.
16. Permit child actions only through trusted Action Engine dispatch.
17. Give Viewer summary audit access only.
18. Give Planner object-specific operational history.
19. Give OperationsManager global operational history.
20. Give Admin full operational and technical audit access.
21. Give AIAgent safe provenance, not raw audit access.
22. Do not implement row-level authorization in Version 1.
23. Do not create a separate permission path for MCP or AI.
24. Do not treat hidden UI buttons or hidden MCP tools as security controls.
25. Do not let Admin or any role access an unknown future resource automatically.

The result should be a lightweight but strict authorization layer that makes ontology objects, functions, and actions safe for both human users and AI agents while preserving governed human control over operational changes.
