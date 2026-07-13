# Frontend Application Design Context

## File Purpose

This file defines the frontend architecture and implementation plan for **Operational Ontology**, a Palantir Foundry Ontology-inspired supply-chain disruption response system.

It is implementation context for a coding agent. It covers the complete operational frontend, including the Ontology Studio, Object Explorer, relationship graph, function execution, governed actions, mitigation workflow, action history, audit history, and later AI workflow.

This file does not redefine backend business logic or API contracts. Use these existing files as the source of truth:

```text
ontology_api_design_context.md
operational-ontology_backend_implementation_context.md
SupplyGraph_Ontology_Implementation_Context.md
SupplyGraph_Lightweight_Ontology_Manager_Implementation_Context.md
```

---

## 1. Frontend Goal

The frontend must demonstrate that operational data is represented as:

```text
Objects
+ Properties
+ Links
+ Read-only Functions
+ Governed Actions
+ Permissions
+ Execution History
+ Auditability
```

The application must not feel like a normal CRUD admin dashboard.

The main user workflow is:

```text
Open delayed Supplier
→ inspect linked Parts and Products
→ run impact-analysis Functions
→ inspect impacted CustomerOrders
→ create or open RiskEvent
→ generate MitigationPlan
→ review recommended mitigation steps
→ submit plan
→ authorized user approves or rejects
→ execute approved plan
→ inspect action execution and audit history
```

---

## 2. Selected Frontend Stack

Use:

```text
Framework: Next.js App Router
Language: TypeScript
UI: React
Styling: Tailwind CSS
Component foundation: existing project components or shadcn/ui
Server-state management: TanStack Query
Forms: React Hook Form
Client validation: Zod
Graph visualization: React Flow
API type generation: OpenAPI-generated TypeScript types
Testing: Vitest, React Testing Library, MSW, Playwright
```

Do not introduce Redux for Version 1.

Use:

```text
URL state       → searches, filters, sorting, pagination, selected tabs
TanStack Query  → backend/server state
React state     → temporary component interactions
React Hook Form → function and action parameter forms
```

Add Zustand only later if a real cross-page client-state requirement appears.

---

## 3. Frontend Architecture

```text
Browser
    ↓
Next.js Application
    ├── Server Components for initial reads
    ├── Client Components for interaction
    ├── Central API client
    ├── TanStack Query cache
    └── Secure authentication/session layer
    ↓
FastAPI Backend
    ↓
Ontology Runtime
    ├── Object Runtime
    ├── Link Runtime
    ├── Function Engine
    └── Action Engine
```

The frontend must never:

- connect directly to PostgreSQL
- parse `ontology.yaml` in the browser
- contain a duplicated ontology registry
- decide authorization independently
- modify operational records through generic PATCH forms
- treat a hidden button as a security boundary

The backend remains authoritative for permissions, validation, functions, actions, idempotency, transactions, and audit recording.

---

## 4. Authentication and API Access

Backend APIs use Bearer authentication.

Preferred frontend pattern:

```text
Browser
→ secure Next.js session
→ Next.js server-side API layer/BFF
→ Bearer token attached server-side
→ FastAPI
```

Requirements:

- Do not store access tokens in `localStorage`.
- Protect application routes through the existing authentication system.
- The frontend may use returned roles for display, but it must render actions from backend-provided capabilities or permission-filtered metadata.
- The backend must still reject every unauthorized request.
- Preserve the backend `requestId` and expose it in error details for debugging.

If the repository already has a secure authentication pattern, reuse it instead of creating a second system.

---

## 5. Main Application Navigation

Use a desktop-first application shell with a collapsible left sidebar and top header.

Recommended navigation:

```text
Command Center
Ontology Studio
Object Explorer
Risk Events
Mitigation Plans
Action Executions
Audit Log
AI Assistant              later phase
```

The Ontology Studio has its own sub-navigation:

```text
Overview
Object Types
Link Types
Functions
Actions
Roles & Permissions
Relationship Graph
Validation
```

Do not call the product Palantir or copy Palantir branding.

---

## 6. Route Structure

```text
frontend/src/app/
├── (auth)/
│   └── login/
│       └── page.tsx
│
├── (app)/
│   ├── layout.tsx
│   ├── page.tsx                         # Command Center
│   │
│   ├── ontology/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── object-types/
│   │   │   ├── page.tsx
│   │   │   └── [key]/page.tsx
│   │   ├── link-types/
│   │   │   ├── page.tsx
│   │   │   └── [key]/page.tsx
│   │   ├── functions/
│   │   │   ├── page.tsx
│   │   │   └── [key]/page.tsx
│   │   ├── actions/
│   │   │   ├── page.tsx
│   │   │   └── [key]/page.tsx
│   │   ├── roles/
│   │   │   ├── page.tsx
│   │   │   └── [key]/page.tsx
│   │   ├── graph/page.tsx
│   │   └── validation/page.tsx
│   │
│   ├── explorer/
│   │   └── page.tsx
│   │
│   ├── objects/
│   │   └── [objectType]/
│   │       └── [objectId]/page.tsx
│   │
│   ├── risk-events/
│   │   ├── page.tsx
│   │   └── [riskEventId]/page.tsx
│   │
│   ├── mitigation-plans/
│   │   ├── page.tsx
│   │   └── [planId]/page.tsx
│   │
│   ├── action-executions/
│   │   ├── page.tsx
│   │   └── [executionId]/page.tsx
│   │
│   ├── audit/
│   │   └── page.tsx
│   │
│   └── assistant/
│       └── page.tsx                    # Later phase
│
├── loading.tsx
├── error.tsx
└── not-found.tsx
```

The dynamic object route is the primary detail route for all ontology object types. Do not create separate CRUD detail implementations for Supplier, Part, Product, Warehouse, and CustomerOrder.

RiskEvent and MitigationPlan may have dedicated workflow pages because they need specialized operational presentation, but they should reuse the generic object components.

---

## 7. Frontend Folder Structure

Use a feature-first structure:

```text
frontend/
├── src/
│   ├── app/
│   ├── components/
│   │   ├── ui/
│   │   ├── layout/
│   │   └── shared/
│   │
│   ├── features/
│   │   ├── ontology/
│   │   │   ├── components/
│   │   │   ├── queries.ts
│   │   │   ├── types.ts
│   │   │   └── mappers.ts
│   │   ├── objects/
│   │   │   ├── components/
│   │   │   ├── queries.ts
│   │   │   └── filters.ts
│   │   ├── graph/
│   │   ├── functions/
│   │   ├── actions/
│   │   │   ├── components/
│   │   │   ├── form-schema.ts
│   │   │   ├── idempotency.ts
│   │   │   └── mutations.ts
│   │   ├── risk-events/
│   │   ├── mitigation-plans/
│   │   ├── executions/
│   │   ├── audit/
│   │   └── assistant/
│   │
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── errors.ts
│   │   │   ├── envelope.ts
│   │   │   └── generated.ts
│   │   ├── auth/
│   │   ├── query/
│   │   ├── formatters/
│   │   └── utils/
│   │
│   ├── hooks/
│   └── test/
│       ├── mocks/
│       └── fixtures/
│
├── public/
├── e2e/
├── package.json
├── next.config.ts
├── tsconfig.json
└── .env.example
```

Rules:

- Keep reusable primitive components in `components/ui`.
- Keep domain behavior inside `features`.
- Do not place API calls directly inside presentation components.
- Do not create one-off versions of tables, badges, or empty states when shared components can be reused.

---

## 8. Central API Client

All backend access must pass through one typed client.

Responsibilities:

- apply the `/api/v1` base path
- attach authentication through the selected secure pattern
- send `X-Request-Id` when useful
- add `Idempotency-Key` for action requests
- parse the common success envelope
- parse backend error envelopes
- expose typed errors to UI components
- support request cancellation
- never silently swallow an API error

Generate TypeScript request and response types from the FastAPI OpenAPI document when practical. Do not manually duplicate every backend DTO.

Suggested error type:

```ts
interface ApiError {
  status: number;
  code: string;
  message: string;
  details?: unknown;
  requestId?: string;
}
```

UI behavior:

```text
401 → redirect to authentication
403 → permission-denied state
404 → resource not found
409 → conflict or idempotency explanation
422 → show field/business validation errors
500 → generic failure with request ID
```

---

## 9. Data-Fetching Rules

Use Server Components for:

- initial ontology metadata pages
- initial object detail load when possible
- read-only page headers and summaries

Use Client Components and TanStack Query for:

- search
- filters
- cursor pagination
- graph interaction
- function execution
- action execution
- execution-status polling
- tabs that lazily load data

Suggested query-key groups:

```text
ontology.summary
ontology.objectTypes
ontology.resource(kind, key)
objects.search(request)
objects.detail(objectType, objectId)
objects.links(objectType, objectId, linkType)
executions.list(filters)
executions.detail(executionId)
audit.list(filters)
```

After a successful governed action, invalidate only the affected query groups returned by the action result, including:

- affected object details
- related object links
- mitigation plan
- action execution
- audit history
- command-center summaries

Do not optimistically change critical operational state. Wait for the authoritative backend result.

---

## 10. Command Center

The Command Center is the operational starting page.

Display:

```text
active risk events
orders currently at risk
mitigation plans awaiting approval
running or failed action executions
recent critical actions
supplier-delay demo entry point
```

Recommended layout:

```text
summary cards
→ active risk table
→ plans requiring attention
→ recent execution and audit activity
```

For the MVP, compose this page from existing object-search, execution, and audit APIs.

Add a dedicated read-only dashboard summary endpoint only if repeated frontend aggregation becomes inefficient. Do not make the frontend calculate business risk metrics.

---

## 11. Ontology Studio

The Ontology Studio is the read-only control-plane interface for ontology metadata.

Its detailed behavior is defined in:

```text
SupplyGraph_Lightweight_Ontology_Manager_Implementation_Context.md
```

The Studio must render metadata from backend ontology endpoints and must not parse or hardcode ontology definitions.

Key views:

```text
ontology overview
object type details
properties and derived properties
link types
functions
registered actions
roles and permissions
metadata relationship graph
validation report
resource dependencies
```

The Ontology Studio does not execute functions or actions and does not display operational object records.

---

## 12. Object Explorer

The Object Explorer displays actual operational object instances.

### Explorer search page

Allow users to:

- select one or more object types
- enter a text query
- add property filters
- sort by declared sortable properties
- browse cursor-paginated results
- open an object detail page

Search controls must be generated from searchable and filterable ontology metadata where possible.

Never expose raw table names, SQL, or unrestricted operators.

### Object detail page

Recommended layout:

```text
Object header
├── display title
├── object type
├── object ID
├── status badges
└── permitted action menu

Tabs
├── Overview
├── Relationships
├── Functions / Insights
├── Action History
└── Audit History
```

Overview displays:

- stored properties
- derived properties
- descriptions and types from ontology metadata
- timestamps and status fields

Relationships displays:

- declared link groups
- linked object counts
- linked object tables
- bounded object-instance graph

The frontend must follow declared links. It must not request arbitrary unrestricted graph traversal.

---

## 13. Relationship Graph

Use React Flow for two different graph surfaces.

### Ontology metadata graph

Displays:

```text
Object Type → Link Type → Object Type
```

Optional overlays may display functions, actions, roles, or backing sources.

### Object-instance graph

Starts from one operational object and displays linked objects.

Behavior:

- load the selected object as the root
- show only returned/declared relationships
- expand one link group at a time
- enforce backend traversal limits
- open a side panel when a node is selected
- navigate to the full object page from the side panel
- visually distinguish object types and risk/workflow statuses

Do not build an unrestricted client-side graph crawler.

---

## 14. Function Runner

Functions are read-only calculations, searches, rankings, explanations, or recommendations.

The generic Function Runner should:

1. load function metadata
2. render parameter fields from the declared input schema
3. validate basic client-side shape
4. call the correct global or object-scoped function endpoint
5. display structured results
6. preserve the backend execution metadata and request ID

Supported field controls should include:

```text
string
multiline string
integer
number
boolean
enum
date
datetime
object reference
simple array
```

Object-reference parameters should use an ontology-aware object search combobox.

Do not let functions modify local or backend operational state.

Common result presentations:

```text
object list
ranked order list
risk summary
inventory availability table
alternative warehouse table
recommendation explanation
validation issue list
raw JSON fallback for unknown structured outputs
```

---

## 15. Governed Action Panel

Actions are the only frontend mechanism allowed to change operational business state.

The generic Action Panel should:

1. receive the permitted action list from the backend or permission-filtered metadata
2. load the selected action definition
3. render parameters from metadata
4. require a reason when declared
5. generate and retain an idempotency key
6. validate the request shape
7. show a critical-action confirmation when required
8. submit to the action endpoint
9. display the returned execution status
10. refresh affected objects, executions, and audit history

Action forms must not directly call generic update endpoints.

### Idempotency behavior

- Generate one key for one logical submission.
- Retain the same key when retrying after a network timeout.
- Generate a new key only when the user intentionally starts a new execution.
- Never reuse one key with changed parameters.

### Action confirmation

Critical actions should show:

```text
action name
target object
important parameters
reason
expected affected object types
approval warning
```

Do not claim success until the backend returns success.

---

## 16. Risk Event Experience

RiskEvent is an ontology object with a specialized workflow page.

Display:

```text
risk status and severity
source Supplier
reported delay
impacted Parts
impacted Products
impacted CustomerOrders
stockout-risk results
linked MitigationPlan
available governed actions
action and audit timeline
```

Recommended workflow actions may include:

```text
acknowledgeRiskEvent
generateMitigationPlan
resolveRiskEvent
```

Render only actions permitted by the backend for the current actor and object state.

---

## 17. Mitigation Plan Experience

The MitigationPlan page is the main review and approval surface.

Display:

```text
plan status
linked RiskEvent
recommendation explanation
impacted orders and priority
inventory availability
alternative warehouses
expeditable purchase orders
ordered mitigation steps
validation results
approval and execution history
```

Represent plan lifecycle visually:

```text
Draft
→ Submitted
→ Approved or Rejected
→ Executing
→ Completed or Failed
```

Do not hardcode allowed transitions. Render the current state and actions provided by the backend.

Mitigation steps should display:

```text
step order
action type
target object
parameters
status
execution ID
failure reason when present
```

The page must make human approval explicit before critical execution.

---

## 18. Action Executions

The execution list should support filters for:

```text
action type
status
actor
object reference
date range
```

Execution detail should display:

```text
execution ID
action type
status
actor
submitted parameters
reason
idempotency key in masked or shortened form
affected objects
result
error information
timestamps
linked audit records
```

When an execution is `pending` or `running`, poll at a moderate interval and stop polling when it reaches a terminal state.

Terminal states include:

```text
succeeded
failed
rejected
partiallyCompleted
```

Follow the actual backend status vocabulary.

---

## 19. Audit Log

The audit log is read-only.

Display:

```text
timestamp
actor
action
object type and object ID
previous value
new value
reason
execution ID
request ID
```

Support filters for:

```text
object type
object ID
action type
actor
date range
```

Use a side panel or detail page for large before/after payloads.

The frontend must not fabricate audit entries or calculate diffs when the backend already provides authoritative audit data.

---

## 20. AI Assistant — Later Phase

The AI Assistant should be implemented only after its backend/MCP API contract is defined.

The surface should eventually display:

```text
user question
assistant answer
ontology objects referenced
functions/tools used
recommendation rationale
proposed governed actions
approval requirement
```

The assistant may recommend or draft critical actions, but it must not silently approve or execute them.

Human approval remains explicit through the same Action Engine and Action Panel used elsewhere in the application.

Do not create a fake chat endpoint or bypass the ontology runtime for the demo.

---

## 21. Metadata-Driven UI Rules

The frontend should derive the following from ontology metadata or backend responses:

```text
object labels and icons
property display names and descriptions
property formatting and filter controls
links shown for each object type
functions attached to an object type
actions available for an object type
parameter fields
critical-action indicators
reason requirements
role and permission explanations
state-transition information
```

The frontend may contain reusable rendering rules for data types, but it must not contain a second hardcoded list of all objects, links, functions, actions, or role permissions.

Specialized workflow pages may arrange metadata differently, but they must still use the same backend contracts and shared components.

---

## 22. Core Shared Components

```text
AppShell
AppSidebar
AppHeader
Breadcrumbs
GlobalSearch
PageHeader
StatusBadge
ObjectTypeBadge
PropertyGrid
MetadataTable
CursorPagination
FilterBuilder
ObjectSearchCombobox
ObjectResultTable
ObjectHeader
LinkedObjectsPanel
RelationshipGraph
FunctionRunner
FunctionResultRenderer
AvailableActionsMenu
ActionDialog
DynamicParameterForm
CriticalActionConfirmation
ExecutionStatusPanel
ExecutionTimeline
AuditTimeline
BeforeAfterViewer
RiskSummaryPanel
MitigationStepTable
MitigationLifecycle
PermissionDeniedState
EmptyState
ErrorState
LoadingSkeleton
RequestErrorDetails
```

Prefer generic metadata-driven components over separate components for every object type.

---

## 23. Visual and UX Direction

The application should look like a serious operational command center.

Use:

- dense but readable desktop layouts
- clear tables and split panels
- neutral base colors
- consistent status semantics
- visible object types and IDs
- clear workflow states
- restrained graph styling
- obvious critical-action warnings

Do not use color alone to communicate status. Include text labels and icons.

Desktop is the primary target. Still ensure:

- sidebar collapses
- tables scroll on narrow screens
- tabs remain usable
- dialogs fit small screens
- graph controls do not overlap
- routes do not crash on mobile

---

## 24. Loading, Empty, and Error States

Every data surface must provide:

```text
loading state
empty state
permission-denied state
not-found state
recoverable error state
```

Error messages should be understandable to users and retain technical details behind an expandable section.

For backend errors, display:

```text
message
error code
request ID
retry action when safe
```

For action errors:

- keep the user-entered form values
- display field and business validation errors
- explain conflicts
- reuse the same idempotency key only for a true retry of the same request

---

## 25. Accessibility

Requirements:

- keyboard-accessible navigation and dialogs
- visible focus states
- semantic headings and tables
- form labels and error messages linked to inputs
- screen-reader labels for icon-only controls
- graph information available through an accessible list or detail panel
- status represented by text, not only color
- confirmation dialogs must trap and restore focus correctly

---

## 26. Testing Strategy

### Unit tests

Test:

- API envelope parsing
- API error mapping
- property formatting
- dynamic field selection
- action parameter schema creation
- idempotency-key lifecycle
- query-key generation

### Component tests

Test:

- object property rendering
- linked-object tables
- function form submission
- action validation and confirmation
- execution status rendering
- audit before/after viewer

Use MSW for backend contract mocks.

### End-to-end tests

The primary Playwright scenario should cover:

```text
search Supplier S-102
→ open object detail
→ inspect supplied Parts
→ create RiskEvent
→ run impact functions
→ generate MitigationPlan
→ submit plan
→ approve plan as authorized actor
→ execute plan
→ verify execution result
→ verify audit history
```

Also test:

- Viewer cannot execute a write action
- validation errors remain visible
- duplicate action retry returns the original idempotent result
- unknown object route shows not-found state
- backend failure includes request ID

Do not make end-to-end tests depend on unstable random seed data. Use deterministic project seed records.

---

## 27. Implementation Order

### Phase 1 — Foundation

1. Create Next.js application structure.
2. Add authentication integration.
3. Add the central typed API client.
4. Add TanStack Query provider and error handling.
5. Build the application shell and shared UI components.

### Phase 2 — Ontology and Exploration

1. Implement the read-only Ontology Studio.
2. Implement object search.
3. Implement generic object detail pages.
4. Implement linked-object views.
5. Implement ontology and object-instance graphs.

### Phase 3 — Functions and Actions

1. Implement metadata-driven Function Runner.
2. Implement metadata-driven Action Panel.
3. Implement idempotency handling.
4. Implement action execution pages.
5. Implement audit history.

### Phase 4 — Supply-Chain Workflow

1. Implement RiskEvent workflow page.
2. Implement MitigationPlan review page.
3. Implement approval/rejection/execution experience.
4. Implement Command Center summaries.
5. Complete the deterministic supplier-delay demo.

### Phase 5 — AI Workflow

1. Define the assistant/MCP API contract.
2. Implement tool trace and referenced-object display.
3. Allow AI recommendations and action drafts.
4. Route every approved action through the normal Action Engine.

---

## 28. Explicit Non-Goals for Version 1

Do not implement:

```text
ontology editing or publishing
generic table administration
direct database updates
arbitrary graph-depth traversal
frontend-only authorization
offline mode
real-time collaboration
custom dashboard builder
user-defined workflows
mobile-first graph editing
AI execution that bypasses approval
```

Do not add WebSockets unless an actual backend requirement appears. Polling is sufficient for the initial action-execution workflow.

---

## 29. Acceptance Criteria

The frontend design is correctly implemented when:

- users can understand the ontology through the Ontology Studio
- users can search and inspect actual ontology objects
- object pages display declared properties, links, functions, and permitted actions
- functions run through the Function Engine and remain read-only
- all business writes run through governed actions
- action forms honor parameter metadata, reasons, critical flags, and idempotency
- mitigation plans require explicit authorized approval
- executions and audit records are visible and linked
- permissions are enforced by the backend and represented accurately in the UI
- no ontology definition is duplicated in frontend constants
- the complete Supplier S-102 disruption workflow can be demonstrated end to end

---

## 30. Final Frontend Principle

```text
The frontend does not decide what the operational world contains.
The ontology describes it.
The backend enforces it.
The frontend makes it understandable and safely actionable.
```
