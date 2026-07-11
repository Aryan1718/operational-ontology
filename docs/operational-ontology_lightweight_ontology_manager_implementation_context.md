# operational-ontology Lightweight Ontology Manager — Implementation Context

## 1. Purpose of this document

This document is the implementation context for building the first version of the **operational-ontology Lightweight Ontology Manager**.

The agent implementing this feature should use this document to understand:

- what the Ontology Manager is responsible for
- what it must not do
- how it relates to `ontology/ontology.yaml`
- how ontology metadata should be loaded and normalized
- which backend services and APIs are required
- which frontend pages and components are required
- how search, dependency inspection, graph visualization, permissions, and validation should work
- how the implementation should be tested
- the required delivery order and acceptance criteria

This document does **not** replace the existing ontology definition. The existing ontology specification and generated `ontology/ontology.yaml` remain the source of truth for object types, properties, links, functions, actions, roles, permissions, and settings.

The purpose of this task is to build a read-only application that makes that ontology understandable and navigable.

---

# 2. Project context

## 2.1 Product

operational-ontology is a Palantir Foundry Ontology-inspired supply-chain disruption response platform.

The project is intended to demonstrate how raw operational data can be represented as:

```text
business objects
+ typed properties
+ relationships
+ derived logic
+ governed actions
+ permissions
+ auditability
+ safe AI tools
```

The selected use case is supply-chain disruption response.

The main workflow is:

```text
Supplier delay detected
→ RiskEvent created
→ impacted Parts discovered
→ impacted Products discovered
→ impacted CustomerOrders discovered
→ available Inventory checked
→ mitigation options generated
→ MitigationPlan created
→ plan submitted
→ Operations Manager approves
→ approved steps execute
→ operational records change
→ every action is audited
→ AI explains the decision
```

This project is not a Palantir clone and must not claim official Palantir integration. It may be described as:

> A lightweight, open-source operational data platform inspired by Palantir Foundry Ontology concepts.

## 2.2 Important system distinction

operational-ontology is not a normal CRUD application.

Avoid treating the product as only:

```text
GET /suppliers
GET /orders
PATCH /inventory/:id
```

The system should expose connected business meaning and governed behavior through APIs such as:

```text
GET /ontology/object-types
GET /objects/:objectType/:objectId
GET /objects/:objectType/:objectId/links
POST /functions/findImpactedOrders
POST /actions/generateMitigationPlan
POST /actions/approveMitigationPlan
```

The Ontology Manager exists to make the metadata behind those capabilities visible.

---

# 3. Existing ontology source of truth

The ontology definition already exists at:

```text
ontology/ontology.yaml
```

It contains the metadata definitions for:

- ontology identity and version
- object types
- stored properties
- derived properties
- link types
- derived or flattened links
- functions
- governed actions
- action parameters
- validation rules
- state transitions
- roles
- permissions
- audit settings
- transaction settings
- idempotency settings
- AI execution restrictions
- UI labels, categories, icons, and ordering
- PostgreSQL table and column mappings
- stable backend handler names

The manager must consume this file. It must not create a second hardcoded ontology definition in frontend code.

## 3.1 Final Version 1 object types

The existing ontology contains these 16 object types:

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

## 3.2 Final Version 1 functions

The existing ontology contains these 10 read-only functions:

```text
findImpactedParts
findImpactedProducts
findImpactedOrders
calculateStockoutRisk
getInventoryAvailability
findAlternativeWarehouses
findExpeditablePurchaseOrders
rankImpactedOrders
recommendMitigationPlan
validateMitigationPlan
```

## 3.3 Final Version 1 actions

The existing ontology contains these 12 governed actions:

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

## 3.4 Final Version 1 roles

The ontology defines five roles:

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

Do not hardcode what each role can do in the manager. Render the permission rules from `ontology.yaml`.

## 3.5 Source separation

Preserve this separation:

```text
PostgreSQL
= operational records and execution history

ontology/ontology.yaml
= ontology metadata definitions

backend handlers
= executable function and action logic

ontology runtime
= loading, querying, authorization, dispatch, and auditing

Ontology Manager
= read-only visualization and inspection of ontology metadata

Object Explorer
= inspection of actual operational object instances

MCP layer
= safe AI access to approved ontology capabilities
```

---

# 4. What the Ontology Manager is

The Ontology Manager is the **control-plane user interface for understanding the ontology definition**.

It should let a user answer questions such as:

- Which object types exist?
- What does each object type represent?
- Which PostgreSQL table backs an object type?
- Which properties are stored and which are derived?
- Which property is the title property?
- Which links connect two object types?
- Is a link stored, flattened, or derived?
- Which function resolves a derived property or derived link?
- Which functions are available for an object type?
- Which actions can target an object type?
- Which roles may execute an action?
- Which actions require a reason, transaction, audit entry, or idempotency key?
- What state transitions does an action allow?
- What depends on a specific object type, link, function, action, or role?
- Is the loaded ontology valid?
- What ontology version and source hash is currently loaded?

The manager should feel like a compact developer and operations studio, not a generic dashboard.

---

# 5. Version 1 scope

## 5.1 Required capabilities

Version 1 must support:

1. Loading the ontology through the existing ontology loader.
2. Reading a normalized ontology registry.
3. Displaying ontology identity, version, description, and settings.
4. Listing all object types.
5. Inspecting one object type in detail.
6. Listing and inspecting all link types.
7. Listing and inspecting all functions.
8. Listing and inspecting all actions.
9. Listing and inspecting all roles and permissions.
10. Searching across ontology resources.
11. Filtering resources by kind and metadata.
12. Displaying ontology relationships in a graph.
13. Displaying resource dependencies.
14. Displaying ontology validation status and warnings.
15. Showing backing tables, source columns, handlers, and resolver metadata.
16. Handling missing resources, invalid routes, and unavailable ontology state cleanly.
17. Rendering entirely from ontology metadata instead of duplicated frontend constants.

## 5.2 Explicit non-goals

Do not implement these features in Version 1:

```text
editing ontology.yaml through the UI
creating object types through the UI
editing properties, links, functions, actions, or roles
publishing ontology changes
draft ontology states
ontology branching
ontology version history
rollback or restore
concurrent metadata editing
database-backed ontology metadata
dragging graph nodes to modify relationships
executing ontology functions
executing ontology actions
displaying actual Supplier, Order, Inventory, or RiskEvent records
generic database administration
MCP tool execution
AI chat
audit-log browsing for operational actions
```

Some of these belong to later phases of operational-ontology, but not to this task.

## 5.3 Read-only means read-only

The manager must not expose any endpoint that mutates ontology metadata.

Do not create:

```text
POST /ontology/object-types
PATCH /ontology/object-types/:key
DELETE /ontology/object-types/:key
POST /ontology/publish
```

The only source of ontology changes in Version 1 is a developer changing `ontology/ontology.yaml` in source control.

---

# 6. Implementation assumptions

## 6.1 Reuse the existing project

Before writing code, inspect the repository and reuse:

- the existing frontend framework
- the existing backend framework
- the existing ontology schema
- the existing loader
- the existing registry
- the existing API conventions
- the existing authentication middleware
- the existing UI component library
- the existing test setup
- the existing lint and formatting configuration

Do not create a parallel application or duplicate infrastructure when the repository already provides the required layer.

## 6.2 Preferred technical direction

When the repository does not already make the choice, prefer:

```text
Language: TypeScript
Frontend: Next.js App Router + React
Styling: existing Tailwind or project design system
Validation: Zod
YAML parsing: existing safe YAML parser
Graph: React Flow or the graph library already installed
Backend API: existing Node.js service or Next.js route handlers
Tests: existing unit test framework + Playwright for end-to-end tests
```

Do not upgrade unrelated dependencies while implementing this feature.

## 6.3 Server-side metadata access

The browser must not read `ontology/ontology.yaml` directly from the file system.

Correct flow:

```text
ontology.yaml
→ server-side loader
→ schema and semantic validation
→ normalized registry
→ query service
→ read-only API
→ frontend
```

Incorrect flow:

```text
browser
→ fetch raw YAML
→ parse and interpret ontology independently
```

The server must remain the single interpretation layer.

---

# 7. High-level architecture

```text
┌─────────────────────────────────────────────┐
│ ontology/ontology.yaml                      │
│ Canonical ontology metadata                 │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ Ontology Loader                             │
│ - reads one configured file                 │
│ - safe YAML parsing                         │
│ - schema validation                         │
│ - semantic reference validation             │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ Ontology Registry                           │
│ - normalized immutable metadata             │
│ - indexes by key and resource kind          │
│ - reverse dependency indexes                │
│ - search document index                     │
│ - graph projection                          │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ Ontology Manager Query Service              │
│ - summary                                   │
│ - lists and filters                         │
│ - detail lookup                             │
│ - dependency lookup                         │
│ - graph projection                          │
│ - validation report                         │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ Read-only Ontology Manager API              │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ Ontology Manager UI                         │
│ - overview                                  │
│ - resource lists                            │
│ - resource details                          │
│ - relationship graph                        │
│ - permission views                          │
│ - validation status                         │
└─────────────────────────────────────────────┘
```

---

# 8. Ontology loading and registry behavior

## 8.1 Startup behavior

At application startup:

1. Resolve the ontology file from a fixed trusted configuration.
2. Read `ontology/ontology.yaml`.
3. Parse YAML using a safe parser.
4. Validate the raw structure using the existing strict schema.
5. Perform semantic validation across references.
6. Resolve known handler names where required by the existing runtime.
7. Normalize all resource definitions.
8. Build lookup indexes.
9. Build reverse dependency indexes.
10. Build the graph projection.
11. Compute a deterministic source checksum.
12. Freeze or otherwise protect the registry from mutation.
13. Make the registry available through dependency injection or a singleton service.

Normal application startup must fail when fatal ontology errors exist.

## 8.2 Required validation checks

The loader or registry must reject fatal issues such as:

```text
duplicate resource keys
unknown object types
unknown properties
unknown title properties
unknown link endpoints
invalid link cardinalities
unknown function references
unknown action targets
unknown role references
unknown handler names
derived properties without resolvers
derived links without resolvers
invalid action state transitions
invalid property types
enum properties without enum values
write actions granted to AIAgent when prohibited
missing required ontology metadata
```

Warnings may include non-fatal quality issues such as:

```text
missing descriptions
missing UI icon
missing UI category
resource not referenced by any other resource
searchable object without searchable properties
object with no links
action with no visible object association
```

Fatal errors prevent normal startup. Warnings appear on the Validation page.

## 8.3 Production and development loading

Production behavior:

```text
load once at startup
registry remains immutable
changes require application restart or redeployment
```

Development behavior may optionally support file watching and registry reload, but this is not required for Version 1.

Do not introduce hot reload if it complicates correctness.

## 8.4 Ontology checksum

Compute a stable checksum from the exact ontology source contents.

Expose:

```text
ontologyVersion
ontologyKey
sourceChecksum
loadedAt
sourcePathLabel
validationStatus
warningCount
```

Do not expose an arbitrary server file path. A safe label such as `ontology/ontology.yaml` is enough.

---

# 9. Normalized registry requirements

The manager should query a normalized registry rather than repeatedly traversing raw YAML objects.

The registry should provide operations equivalent to:

```ts
getOntologySummary()
getObjectTypes()
getObjectType(key)
getLinkTypes()
getLinkType(key)
getFunctions()
getFunction(key)
getActions()
getAction(key)
getRoles()
getRole(key)
getSettings()
searchResources(query, filters)
getDependencies(kind, key)
getGraph(options)
getValidationReport()
```

## 9.1 Resource kinds

Use a shared resource-kind union:

```text
ontology
objectType
property
derivedProperty
linkType
function
action
role
setting
dataSource
```

Properties may be represented as nested resources in detail views. They do not need top-level routes in Version 1.

## 9.2 Resource identity

Every top-level resource should have a stable manager identity:

```text
objectType:Supplier
linkType:supplierParts
function:findImpactedOrders
action:approveMitigationPlan
role:OperationsManager
```

Use this identity for graph nodes, search results, dependency edges, and UI keys.

## 9.3 Immutability

The manager must not mutate registry values.

Use one of these approaches:

- immutable data structures
- deep freezing after normalization
- returning copies or read-only DTOs
- TypeScript `Readonly` types plus runtime discipline

Do not return direct mutable references to internal registry maps.

---

# 10. Reverse dependency index

The registry must build reverse dependencies so the UI can answer “what uses this resource?”

Examples:

```text
Supplier
← targeted by createRiskEvent
← referenced by supplierParts
← referenced by purchaseOrders
← used in findImpactedParts traversal
← backed by suppliers table
```

```text
recommendMitigationPlan
← attached to RiskEvent
← referenced by generateMitigationPlan
← exposed as an approved read tool for AIAgent
```

```text
OperationsManager
← allowed by specific functions
← allowed by specific actions
← permitted to approve and execute plans
```

## 10.1 Dependency edge types

Support dependency relationships such as:

```text
HAS_PROPERTY
HAS_DERIVED_PROPERTY
HAS_LINK
LINKS_FROM
LINKS_TO
USES_FUNCTION
RESOLVED_BY_FUNCTION
TARGETED_BY_ACTION
ACTION_USES_FUNCTION
ALLOWS_ROLE
BACKED_BY_TABLE
BACKED_BY_COLUMN
REFERENCES_OBJECT_TYPE
TRANSITIONS_STATE
```

The exact internal names may follow existing repository conventions, but the semantics must remain clear.

## 10.2 Dependency response

A dependency result should distinguish:

```text
incoming dependencies
outgoing dependencies
direct dependencies
resource kind
resource key
relationship type
human-readable explanation
```

---

# 11. Search behavior

## 11.1 Search scope

Global search should match:

- resource key
- display name
- description
- object type property names
- derived property names
- link names
- PostgreSQL table names
- PostgreSQL column names
- function names
- action names
- handler names
- role names
- enum values
- UI category
- state transition values

## 11.2 Search implementation

The ontology is small. Do not add Elasticsearch, PostgreSQL full-text search, or an external search service.

Build a simple in-memory normalized search index from registry metadata.

Recommended matching behavior:

1. exact key match
2. case-insensitive display-name match
3. prefix match
4. token/substring match
5. description and nested metadata match

A fuzzy-search library is optional. Prefer a deterministic dependency-free implementation when practical.

## 11.3 Search filters

Support filters such as:

```text
kind
category
objectType
role
readOnly
critical
sourceTable
```

Only display filters that are meaningful for the current result set.

## 11.4 Search result contract

Each result should contain enough information to navigate without loading the full resource:

```json
{
  "id": "action:approveMitigationPlan",
  "kind": "action",
  "key": "approveMitigationPlan",
  "displayName": "Approve Mitigation Plan",
  "description": "Approves a submitted mitigation plan.",
  "category": "Workflow",
  "matchedFields": ["key", "description", "allowedRoles"],
  "href": "/ontology/actions/approveMitigationPlan"
}
```

---

# 12. Read-only API design

Adapt the route prefix to the existing project. The following contracts describe required behavior.

## 12.1 Summary

```http
GET /api/ontology
```

Returns:

```json
{
  "key": "supplyGraph",
  "displayName": "operational-ontology",
  "version": "1.0.0",
  "description": "...",
  "sourceChecksum": "...",
  "loadedAt": "...",
  "validation": {
    "status": "valid",
    "warningCount": 0
  },
  "counts": {
    "objectTypes": 16,
    "linkTypes": 0,
    "functions": 10,
    "actions": 12,
    "roles": 5,
    "storedProperties": 0,
    "derivedProperties": 0
  },
  "settings": {}
}
```

Counts must be calculated from the loaded registry. Do not hardcode them.

## 12.2 Resource collection endpoints

```http
GET /api/ontology/object-types
GET /api/ontology/link-types
GET /api/ontology/functions
GET /api/ontology/actions
GET /api/ontology/roles
```

Optional query parameters:

```text
q
category
role
objectType
readOnly
critical
sort
```

For Version 1, pagination is optional because the ontology is small. Follow existing API conventions if all collection endpoints are paginated.

## 12.3 Resource detail endpoints

```http
GET /api/ontology/object-types/:objectTypeKey
GET /api/ontology/link-types/:linkTypeKey
GET /api/ontology/functions/:functionKey
GET /api/ontology/actions/:actionKey
GET /api/ontology/roles/:roleKey
```

The detail response must be manager-friendly and normalized. The frontend should not need to understand raw YAML shape variations.

## 12.4 Search

```http
GET /api/ontology/search?q=impact&kind=function
```

Reject an empty or excessively long query according to existing validation conventions.

## 12.5 Graph

```http
GET /api/ontology/graph
```

Optional filters:

```text
includeDerivedLinks
includeFlattenedLinks
includeFunctions
includeActions
includeDataSources
objectTypes
```

The default global graph should prioritize readability:

```text
object type nodes
+ stored link edges
+ derived link edges with a distinct edge type
```

Functions, actions, roles, and data sources should be optional overlays or separate dependency views.

## 12.6 Dependencies

```http
GET /api/ontology/dependencies/:kind/:key
```

Valid top-level kinds:

```text
object-types
link-types
functions
actions
roles
```

Return 404 for a valid kind with an unknown key.

## 12.7 Validation

```http
GET /api/ontology/validation
```

Returns:

```json
{
  "status": "valid",
  "checkedAt": "...",
  "sourceChecksum": "...",
  "errors": [],
  "warnings": [],
  "statistics": {}
}
```

A normally running production application should have zero fatal errors because fatal errors prevent startup.

## 12.8 Standard error shape

Use the repository’s existing error format. When no standard exists, use:

```json
{
  "error": {
    "code": "ONTOLOGY_RESOURCE_NOT_FOUND",
    "message": "Object type 'UnknownType' was not found.",
    "details": {
      "kind": "objectType",
      "key": "UnknownType"
    }
  }
}
```

Expected status codes:

```text
200 successful read
400 invalid query or resource kind
401 unauthenticated, when authentication exists
403 unauthorized, when manager access is restricted
404 ontology resource not found
500 ontology unavailable or unexpected server failure
```

---

# 13. API DTO requirements

Create shared DTOs or schemas so backend and frontend agree on response structure.

## 13.1 Resource summary DTO

```ts
type OntologyResourceKind =
  | "objectType"
  | "linkType"
  | "function"
  | "action"
  | "role";

interface OntologyResourceSummary {
  id: string;
  kind: OntologyResourceKind;
  key: string;
  displayName: string;
  description?: string;
  category?: string;
  icon?: string;
  badges: string[];
  href: string;
}
```

## 13.2 Object type detail DTO

Include:

```text
key
displayName
description
category
icon
order
source table
source primary key
title property
stored properties
derived properties
links
functions
actions
permissions
incoming dependencies
outgoing dependencies
```

Stored property rows should include:

```text
key
displayName
description
type
sourceColumn
required
readOnly
unique
indexed
searchable
sortable
filterable
enumValues
constraints
```

Derived property rows should include:

```text
key
displayName
description
type
resolver type
resolver function or expression
readOnly
dependencies
```

## 13.3 Link detail DTO

Include:

```text
key
displayName
description
from object type
to object type
cardinality
link classification
foreign-key backing
resolver
inverse link when defined
permissions
dependencies
```

Link classification values should reflect the YAML vocabulary, for example:

```text
stored
derived
flattened
```

Do not infer a classification silently when the YAML defines it explicitly.

## 13.4 Function detail DTO

Include:

```text
key
displayName
description
handler
readOnly
input schema
output schema
allowed roles
associated object types
resolver usage
AI/MCP exposure metadata when present
dependencies
```

## 13.5 Action detail DTO

Include:

```text
key
displayName
description
target object type
handler
parameters
validation rules
allowed roles
critical flag
reason requirement
audit settings
transaction settings
idempotency settings
state transitions
preconditions
effects metadata when present
AI execution restrictions
dependencies
```

## 13.6 Role detail DTO

Include:

```text
key
displayName
description
human or agent classification when defined
read permissions
allowed functions
allowed actions
prohibited critical actions
ontology management permissions
dependency references
```

Render what exists in the YAML. Do not invent missing permissions.

---

# 14. Frontend information architecture

Use the following main routes unless the existing application has a stronger route convention:

```text
/ontology
/ontology/object-types
/ontology/object-types/[key]
/ontology/link-types
/ontology/link-types/[key]
/ontology/functions
/ontology/functions/[key]
/ontology/actions
/ontology/actions/[key]
/ontology/roles
/ontology/roles/[key]
/ontology/graph
/ontology/validation
```

Search may be:

```text
/ontology/search?q=...
```

or a global command/search interface that navigates directly to resource pages.

---

# 15. Shared manager layout

The Ontology Manager should have a consistent layout containing:

## 15.1 Header

Display:

```text
operational-ontology Ontology
version
validation status
source checksum shortened for display
global search
```

## 15.2 Sidebar navigation

Recommended navigation:

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

Show resource counts next to collection labels when useful.

## 15.3 Breadcrumbs

Examples:

```text
Ontology / Object Types / RiskEvent
Ontology / Actions / approveMitigationPlan
```

## 15.4 Resource header

Every detail page should show:

```text
icon
display name
stable key
resource kind
description
category
important badges
copy-key control
```

Useful badges include:

```text
Stored
Derived
Read-only
Critical
Audited
Transactional
Idempotent
AI Restricted
```

Only render badges supported by metadata.

---

# 16. Overview page

Route:

```text
/ontology
```

The overview page should provide a compact model summary.

## 16.1 Required content

Display:

- ontology name
- ontology description
- ontology version
- validation status
- loaded source
- source checksum
- counts for object types, links, functions, actions, roles, stored properties, and derived properties
- object types grouped by their YAML UI categories
- important global settings
- a small relationship preview
- recently navigated resources only if the application already supports local history

Do not display fabricated operational metrics such as “orders at risk” or “inventory health.” Those belong to the operational application, not the Ontology Manager.

## 16.2 Global settings panel

Render settings such as:

```text
defaultPropertyReadOnly
writesThroughActionsOnly
auditAllActions
requireIdempotencyKeyForActions
requireReasonForCriticalActions
aiCanExecuteCriticalActions
```

Use labels and explanations rather than exposing only raw booleans.

Example:

```text
Writes through actions only: Enabled
Operational records cannot be changed through generic update endpoints.
```

---

# 17. Object Types collection page

Route:

```text
/ontology/object-types
```

## 17.1 Required behavior

- list all object types
- search by key, display name, description, property, or table
- filter by UI category
- sort by configured UI order, display name, or key
- switch between table and compact card view only if easy; table view is sufficient
- navigate to detail page
- show useful counts

## 17.2 Recommended columns

```text
Object Type
Category
Backing Table
Stored Properties
Derived Properties
Links
Functions
Actions
```

Do not hardcode category names. Read them from YAML.

---

# 18. Object Type detail page

Route:

```text
/ontology/object-types/[key]
```

## 18.1 Required tabs

```text
Overview
Properties
Links
Functions
Actions
Permissions
Dependencies
```

Tabs may collapse into sections on smaller screens.

## 18.2 Overview tab

Show:

- business description
- backing PostgreSQL table
- primary key column
- ontology title property
- category
- icon
- searchable/display metadata
- counts
- direct incoming and outgoing object relationships
- a small object-specific graph

## 18.3 Properties tab

Separate:

```text
Stored Properties
Derived Properties
```

Stored properties table:

```text
Property
Type
Source Column
Required
Read-only
Indexed
Searchable
Sortable
Filterable
Constraints
```

Derived properties table:

```text
Property
Type
Resolver
Dependencies
Read-only
```

Enum values should be visible through an expandable row, drawer, or popover.

Do not display a derived property as a normal database column.

## 18.4 Links tab

Group links into:

```text
Outgoing
Incoming
Derived
Flattened
```

Each link row should show:

```text
link name
target object type
direction
cardinality
backing type
resolver or foreign key
```

Clicking a link opens its detail page.

## 18.5 Functions tab

Show functions associated with the object type.

Columns:

```text
Function
Read-only
Handler
Allowed Roles
Used As Resolver
```

## 18.6 Actions tab

Show actions associated with or targeting the object type.

Columns:

```text
Action
Target
State Transition
Allowed Roles
Critical
Audit
Transaction
Idempotency
```

## 18.7 Permissions tab

Show a matrix based on actual YAML metadata.

Possible columns:

```text
Role
Can Read Object
Allowed Functions
Allowed Actions
Restrictions
```

Do not derive action permissions from role names alone.

## 18.8 Dependencies tab

Show:

- resources this object type depends on
- resources that depend on this object type
- relation type
- navigation links
- a localized dependency graph

---

# 19. Link Types pages

## 19.1 Collection route

```text
/ontology/link-types
```

Recommended columns:

```text
Link
From
To
Cardinality
Classification
Backing or Resolver
```

Filters:

```text
from object type
to object type
cardinality
stored/derived/flattened
```

## 19.2 Detail route

```text
/ontology/link-types/[key]
```

Show:

- definition and description
- source object type
- target object type
- cardinality
- direction
- inverse metadata when available
- foreign-key mapping
- derived resolver
- flattened traversal path
- permissions
- dependencies
- local graph visualization

Do not execute the link or load operational records.

---

# 20. Functions pages

## 20.1 Collection route

```text
/ontology/functions
```

Recommended columns:

```text
Function
Description
Handler
Associated Objects
Input Count
Output Shape
Allowed Roles
Read-only
```

All 10 Version 1 functions are read-only, but the UI must render the value from metadata rather than assuming it.

## 20.2 Detail route

```text
/ontology/functions/[key]
```

Show:

- description
- stable key
- handler name
- read-only status
- input schema
- output schema
- allowed roles
- object types that expose the function
- derived properties or links resolved by the function
- actions that depend on the function
- MCP or AI exposure metadata when present
- dependencies

Input and output schemas should be rendered as readable field tables, not only raw JSON.

Provide a collapsible raw JSON view only when useful.

Do not add a “Run Function” button in Version 1.

---

# 21. Actions pages

## 21.1 Collection route

```text
/ontology/actions
```

Recommended columns:

```text
Action
Target Object
Handler
Allowed Roles
State Transition
Critical
Audit
Transaction
Idempotency
```

Filters:

```text
target object type
role
critical
requires reason
transactional
AI allowed or restricted
```

## 21.2 Detail route

```text
/ontology/actions/[key]
```

Show:

- business description
- target object type
- handler
- parameter schema
- validation rules
- preconditions
- state transition
- allowed roles
- critical classification
- reason requirement
- audit behavior
- transaction requirement
- idempotency requirement
- effects metadata when defined
- AI execution restrictions
- related object types and functions
- dependencies

Validation rules must be shown in a human-readable ordered list.

Parameter schemas should show:

```text
name
type
required
enum values
constraints
description
object reference when applicable
```

Do not add an “Execute Action” button in Version 1.

---

# 22. Roles and Permissions pages

## 22.1 Collection route

```text
/ontology/roles
```

Display the five defined roles and their metadata.

Recommended columns:

```text
Role
Description
Object Read Scope
Functions
Actions
Critical Actions
Ontology Management
```

## 22.2 Detail route

```text
/ontology/roles/[key]
```

Show:

- description
- human or agent classification when available
- object type access
- function access
- action access
- explicit denials or restrictions
- critical action restrictions
- ontology publishing or management permissions
- all resources referencing the role

## 22.3 Permission matrix

Provide a matrix view that can switch between:

```text
roles × functions
roles × actions
roles × object types
```

Cells should display:

```text
Allowed
Denied
Not specified
```

“Not specified” must not be silently rendered as “Allowed.”

The permission matrix must be generated from YAML.

---

# 23. Relationship Graph page

Route:

```text
/ontology/graph
```

## 23.1 Purpose

The graph visualizes the ontology schema, not operational object instances.

Correct:

```text
Supplier → SupplierPart → Part → ProductPartRequirement → Product
```

Incorrect:

```text
Supplier S-102 → Part P-44 → Order ORD-881
```

The second graph belongs to the Object Explorer or workflow demo.

## 23.2 Default graph

Default nodes:

```text
all object types
```

Default edges:

```text
stored links
derived links
flattened links when they do not make the graph unreadable
```

Use distinct edge labels or styles for:

```text
stored
derived
flattened
```

Do not rely on color alone. Also use labels, line patterns, or a legend.

## 23.3 Graph controls

Support:

```text
search/highlight object type
filter by category
toggle stored links
toggle derived links
toggle flattened links
show link labels
fit view
reset view
```

Optional overlays:

```text
functions
actions
data sources
```

Keep overlays disabled by default if they make the graph too dense.

## 23.4 Node interaction

Clicking an object node should:

- open a detail drawer or side panel
- show summary metadata
- allow navigation to the full object type page
- highlight direct neighbors

Clicking an edge should:

- show link metadata
- allow navigation to the link detail page

## 23.5 Layout

Use a deterministic automatic layout.

Prefer:

- existing graph layout dependency
- a simple layered/DAG layout
- category grouping when useful

Do not persist manually dragged node positions in Version 1.

---

# 24. Validation page

Route:

```text
/ontology/validation
```

## 24.1 Required content

Show:

```text
overall status
ontology key
ontology version
source checksum
loaded timestamp
schema validation status
semantic validation status
handler validation status
resource statistics
warnings
```

## 24.2 Warning display

Each warning should contain:

```text
code
message
resource kind
resource key
metadata path when available
severity
```

Example:

```text
ONTOLOGY_DESCRIPTION_MISSING
Object type 'Warehouse' does not define a description.
Path: objectTypes.Warehouse.description
```

## 24.3 No fake invalid mode

Do not invent validation errors for demonstration.

When the ontology is valid, display a valid status and real warnings only.

A separate CLI validator may be used to test invalid fixtures.

---

# 25. Global search experience

Provide a search input in the manager header.

Recommended behavior:

1. User types at least two characters.
2. Debounce the request.
3. Display grouped results by resource kind.
4. Highlight the matching field.
5. Keyboard navigation is supported.
6. Enter navigates to the selected resource.
7. Escape closes the search.
8. Empty states explain which metadata is searchable.

Suggested groups:

```text
Object Types
Links
Functions
Actions
Roles
Nested Properties
```

A property search result should navigate to the parent object type with the Properties tab selected or the property highlighted.

---

# 26. UI and design guidance

## 26.1 Visual direction

The manager should look like a structured engineering tool.

Prefer:

- clear hierarchy
- compact tables
- tabs
- badges
- code-style identifiers
- readable descriptions
- strong spacing
- consistent detail panels
- a restrained visual design

Avoid:

- oversized marketing cards
- excessive gradients
- fake analytics
- decorative charts unrelated to ontology metadata
- duplicated information on every page

## 26.2 Identifiers

Display human names and technical keys together.

Example:

```text
Approve Mitigation Plan
approveMitigationPlan
```

Use monospace text for:

```text
resource keys
handler names
table names
column names
enum values
state names
```

## 26.3 Accessibility

At minimum:

- keyboard-accessible navigation
- visible focus states
- semantic table markup
- labels for icon-only controls
- non-color graph legends
- adequate contrast
- screen-reader text for status badges
- usable empty and error states

## 26.4 Responsive behavior

Desktop is the primary target because the manager is an engineering interface.

Still ensure:

- sidebar can collapse
- tables scroll horizontally
- detail tabs remain usable
- graph controls do not overlap
- mobile routes do not crash

---

# 27. Suggested frontend components

Adapt names to the repository.

```text
OntologyShell
OntologyHeader
OntologySidebar
OntologyBreadcrumbs
OntologyStatusBadge
OntologySummaryCards
OntologySettingsPanel
ResourceListTable
ResourceHeader
ResourceKey
ResourceBadge
GlobalOntologySearch
ObjectTypeTable
PropertyTable
DerivedPropertyTable
LinkTable
FunctionTable
ActionTable
RoleTable
PermissionMatrix
SchemaFieldTable
StateTransitionView
DependencyList
DependencyGraph
OntologyRelationshipGraph
ValidationSummary
ValidationIssueList
EmptyState
ErrorState
LoadingSkeleton
```

Do not create a unique one-off component when a generic metadata table can be reused.

---

# 28. Suggested backend modules

Reuse existing ontology modules when present.

A reasonable structure is:

```text
ontology/
├── ontology.yaml
├── schema.ts
├── loader.ts
├── registry.ts
├── types.ts
└── validation.ts

src/
└── ontology/
    ├── manager/
    │   ├── ontology-manager.service.ts
    │   ├── ontology-search.service.ts
    │   ├── ontology-dependency.service.ts
    │   ├── ontology-graph.service.ts
    │   ├── ontology-manager.dto.ts
    │   └── ontology-manager.routes.ts
    └── runtime/
        └── existing runtime modules
```

For a Next.js full-stack project, an equivalent structure may be:

```text
src/
├── lib/
│   └── ontology/
│       ├── loader.ts
│       ├── registry.ts
│       ├── manager-query.ts
│       ├── search.ts
│       ├── dependencies.ts
│       └── graph.ts
├── app/
│   ├── api/
│   │   └── ontology/
│   └── ontology/
└── components/
    └── ontology/
```

Do not move stable existing ontology code only to match this suggested structure.

---

# 29. Suggested frontend route structure

For a Next.js App Router project:

```text
src/app/ontology/
├── layout.tsx
├── page.tsx
├── loading.tsx
├── error.tsx
├── object-types/
│   ├── page.tsx
│   └── [key]/
│       └── page.tsx
├── link-types/
│   ├── page.tsx
│   └── [key]/
│       └── page.tsx
├── functions/
│   ├── page.tsx
│   └── [key]/
│       └── page.tsx
├── actions/
│   ├── page.tsx
│   └── [key]/
│       └── page.tsx
├── roles/
│   ├── page.tsx
│   └── [key]/
│       └── page.tsx
├── graph/
│   └── page.tsx
└── validation/
    └── page.tsx
```

Use server components for initial metadata fetching when consistent with the project. Use client components only for interactive tables, search, tabs, filters, and graph behavior.

---

# 30. Authentication and authorization

Follow the existing application authentication model.

Recommended Version 1 behavior:

```text
authenticated human users
→ may read Ontology Manager metadata

AIAgent
→ does not use the visual manager

Admin
→ may view all metadata, including handlers and backing tables
```

When the project has no authentication yet, do not build a complete identity system only for this manager. Keep the API read-only and document the future authorization boundary.

When the manager exposes internal table names or handler names in a production deployment, consider restricting those fields to Admin. For the project demo, displaying them is part of the ontology-learning goal.

Do not implement metadata write permissions because Version 1 contains no metadata writes.

---

# 31. Security requirements

1. The ontology file path must come from trusted configuration.
2. Do not accept a file path from a request parameter.
3. Use safe YAML parsing.
4. Do not use `eval`, dynamic code execution, or executable YAML tags.
5. Validate all route parameters.
6. Escape or safely render all descriptions and metadata.
7. Do not render ontology descriptions as raw HTML unless sanitized.
8. Do not expose server stack traces through API responses.
9. Keep the registry immutable.
10. Do not create write endpoints.
11. Do not allow the graph component to change metadata.
12. Apply normal API rate limiting if the application already uses it.
13. Do not expose secrets or environment values on the Validation page.
14. The checksum may be exposed; full filesystem paths should not be exposed.
15. Dependency and search queries must operate only on the loaded registry.

---

# 32. Logging and observability

Use existing application logging.

Useful events:

```text
ontology_load_started
ontology_load_succeeded
ontology_load_failed
ontology_validation_warning
ontology_registry_built
ontology_manager_request_failed
```

Log fields may include:

```text
ontologyKey
ontologyVersion
sourceChecksum
objectTypeCount
linkTypeCount
functionCount
actionCount
roleCount
warningCount
durationMs
```

Do not log the entire ontology YAML on every startup.

Do not create database tables only for Ontology Manager request logs.

---

# 33. Performance expectations

The ontology is small enough to remain fully in memory.

Required principles:

- parse and validate once at startup
- do not read the YAML file on every request
- prebuild key indexes
- prebuild or lazily cache the search index
- prebuild reverse dependency indexes
- return compact summary DTOs for list pages
- return full DTOs only for detail routes
- avoid sending the complete ontology to every page
- load graph data only on graph pages
- use client-side filtering only after receiving a reasonably small collection

No distributed cache is required.

No ontology database is required.

---

# 34. Testing strategy

## 34.1 Unit tests

Test:

- YAML loader success
- schema validation failure
- semantic validation failure
- registry lookup by key
- unknown key behavior
- object type normalization
- stored and derived property separation
- link normalization
- function normalization
- action normalization
- role normalization
- source checksum stability
- search exact match
- search nested property match
- search handler match
- search filtering
- reverse dependency generation
- graph node generation
- graph edge generation
- immutable registry behavior

## 34.2 Fixture tests

Create small test fixtures separate from production ontology:

```text
valid-minimal.yaml
invalid-unknown-object.yaml
invalid-title-property.yaml
invalid-link-endpoint.yaml
invalid-handler.yaml
invalid-role.yaml
invalid-derived-resolver.yaml
invalid-state-transition.yaml
```

Do not modify the production ontology to test failure states.

## 34.3 Contract tests against the real ontology

Assert that the loaded production ontology contains:

```text
16 object types
10 functions
12 actions
5 roles
```

Also assert the known keys listed in this document.

Counts for properties and links should be derived from the YAML and asserted only when the ontology specification defines a stable expected count.

## 34.4 API tests

Test:

- summary response
- each collection endpoint
- each known detail endpoint
- unknown resource 404
- invalid kind 400
- search results
- graph response
- dependency response
- validation response
- no write methods exist
- response schema validation

## 34.5 UI tests

Test:

- overview renders ontology summary
- object types list renders all object types
- object detail displays stored and derived properties separately
- action detail displays roles and controls
- function detail does not show an execution button
- action detail does not show an execution button
- search navigates to a resource
- graph node opens resource details
- invalid route displays not-found state
- validation page shows real status
- permission matrix distinguishes denied and unspecified

## 34.6 End-to-end smoke flow

A recommended smoke flow:

```text
Open /ontology
→ confirm operational-ontology and version appear
→ open Object Types
→ open RiskEvent
→ inspect derived links and functions
→ navigate to recommendMitigationPlan
→ inspect input/output and allowed roles
→ navigate to generateMitigationPlan
→ inspect target, parameters, validations, audit, and AI restrictions
→ open OperationsManager role
→ inspect permitted actions
→ open graph
→ highlight RiskEvent relationships
→ open validation page
→ confirm ontology is valid
```

---

# 35. Implementation order for Codex

Implement in small, verifiable stages.

## Phase 0: Repository inspection

Before changing code:

1. Find `ontology/ontology.yaml`.
2. Find the ontology schema, loader, registry, and types.
3. Confirm the frontend and backend structure.
4. Find existing API response and error conventions.
5. Find existing authentication middleware.
6. Find the existing component library.
7. Find test commands.
8. Write down which existing modules will be reused.

Do not begin by scaffolding a separate application.

## Phase 1: Registry query layer

Implement or extend:

```text
summary calculation
resource list lookups
detail lookups
normalized DTO mapping
source checksum
validation report
```

Add unit tests before building UI pages.

## Phase 2: Search and dependencies

Implement:

```text
search document creation
search matching
filters
reverse dependency index
dependency query API
```

Add deterministic tests.

## Phase 3: Graph projection

Implement:

```text
object type nodes
stored link edges
derived link edges
flattened link edges
filter options
localized resource graph support
```

Do not include operational object instances.

## Phase 4: Read-only APIs

Implement all required read endpoints.

Validate all route and query parameters.

Add API tests.

## Phase 5: Manager shell and overview

Implement:

```text
layout
sidebar
header
breadcrumbs
global search shell
overview page
loading and error states
```

## Phase 6: Resource collection and detail pages

Implement in this order:

```text
Object Types
Link Types
Functions
Actions
Roles and Permissions
```

Build reusable tables and resource headers.

## Phase 7: Relationship graph and validation

Implement:

```text
global schema graph
node and edge details
filters
validation page
```

## Phase 8: Final quality pass

Run:

```text
formatter
lint
type checking
unit tests
API tests
component tests
end-to-end smoke test
production build
```

Fix all errors introduced by this feature.

Do not hide failing checks by disabling rules.

---

# 36. Required implementation quality

The implementation must:

- use the real ontology file
- avoid duplicated ontology constants
- preserve strict validation
- preserve read-only scope
- use shared types
- keep backend and frontend responsibilities separate
- follow existing repository conventions
- include loading, empty, error, and not-found states
- include tests
- avoid unrelated refactors
- avoid placeholder data
- avoid TODO-only implementations
- avoid silently swallowing invalid ontology references
- avoid presenting guessed permissions
- avoid executing actions or functions

---

# 37. Acceptance criteria

The Ontology Manager Version 1 is complete only when all criteria below pass.

## 37.1 Source and registry

- `ontology/ontology.yaml` remains the metadata source of truth.
- The server loads the ontology once during startup.
- The raw YAML is validated.
- Cross-resource references are validated.
- The registry is immutable.
- The registry exposes lookup methods for every top-level resource kind.
- A deterministic source checksum is available.
- No second ontology definition exists in frontend code.

## 37.2 Overview

- `/ontology` displays the ontology name, version, description, status, counts, and settings.
- All counts come from the registry.
- No operational business metrics are fabricated.

## 37.3 Object types

- All 16 object types appear.
- Every object type has a detail route.
- Stored and derived properties are separated.
- Backing table and primary key are visible.
- Links, functions, actions, permissions, and dependencies are visible.

## 37.4 Links

- All defined link types appear.
- From object, to object, cardinality, and classification are visible.
- Stored backing and derived resolver metadata are visible.
- Link dependencies are navigable.

## 37.5 Functions

- All 10 functions appear.
- Input and output schemas are readable.
- Handler and allowed roles are visible.
- Resolver usage is visible.
- No execution control exists.

## 37.6 Actions

- All 12 actions appear.
- Target object, parameters, validations, state transitions, and roles are visible.
- Audit, transaction, reason, idempotency, and AI restrictions are visible.
- No execution control exists.

## 37.7 Roles and permissions

- All five roles appear.
- The permission matrix is generated from YAML.
- Allowed, denied, and unspecified states are distinct.
- AIAgent restrictions are visible.
- No permissions are guessed from role names.

## 37.8 Search

- Search finds top-level resources.
- Search finds nested property names.
- Search finds table, column, handler, enum, and state-transition metadata.
- Results navigate to the correct resource.

## 37.9 Graph

- The graph displays ontology object types and relationships.
- Stored, derived, and flattened links are distinguishable.
- Nodes and edges navigate to metadata details.
- The graph does not show operational object records.
- The graph cannot modify metadata.

## 37.10 Validation

- The validation page displays real status.
- Fatal errors prevent normal startup.
- Warnings include resource and path context.
- No fake validation problems are shown.

## 37.11 API and security

- Only read-only manager endpoints exist.
- Route parameters are validated.
- Unknown resources return structured 404 responses.
- The file path cannot be controlled by a request.
- The UI does not parse YAML.
- No executable YAML or dynamic evaluation is used.
- Full server filesystem paths are not exposed.

## 37.12 Testing

- Unit tests cover loader, registry, search, dependencies, and graph projection.
- API tests cover all endpoint groups.
- UI tests cover main resource pages.
- A production build succeeds.
- Existing tests continue to pass.

---

# 38. Version 1 exclusions checklist

Before finishing, verify that none of the following were accidentally added:

```text
ontology editor
save button
publish button
rollback
version-history database
metadata mutation endpoint
function runner
action executor
actual object record browser
operational action audit log
AI chat
MCP execution
database schema editor
generic YAML editor
```

---

# 39. Future phases

These are future possibilities and must not be implemented now.

## Phase 2: Object Explorer

```text
list actual objects
inspect one object instance
show linked object instances
show derived values
show available governed actions
show object audit history
```

## Phase 3: Action Console

```text
render action forms from action metadata
validate parameters
authorize actor
preview effects
execute governed actions
record audit history
```

## Phase 4: Ontology authoring

```text
draft metadata changes
edit object types and links
validate working state
review diff
publish
restore versions
resolve conflicts
```

This phase would require a real metadata versioning and authoring model. Do not approximate it with direct YAML writes from the browser.

## Phase 5: AI and MCP integration

```text
derive safe MCP tools
let AI inspect objects and links
run read-only functions
draft mitigation plans
require human approval for critical actions
record AI evidence and tool history
```

---

# 40. Codex execution rules

The implementation agent must follow these rules:

1. Read this document fully before making changes.
2. Inspect the repository before choosing file paths.
3. Reuse the existing ontology schema, loader, and registry.
4. Treat `ontology/ontology.yaml` as canonical.
5. Do not retype ontology definitions into React components.
6. Do not broaden the task into the Object Explorer or action runtime.
7. Implement one phase at a time.
8. Run focused tests after each phase.
9. Keep changes limited to the Ontology Manager and required shared registry support.
10. Document any unavoidable deviation from this specification.
11. Do not remove existing validation to make the UI work.
12. Do not invent missing metadata.
13. Render unknown or unspecified metadata honestly.
14. Preserve stable ontology keys in URLs and API contracts.
15. Finish with a list of created files, modified files, commands run, test results, and remaining limitations.

---

# 41. Expected final output from Codex

At completion, Codex should provide:

```text
1. A working read-only Ontology Manager.
2. All required manager pages.
3. Read-only ontology metadata APIs.
4. Registry query, search, dependency, and graph services.
5. Shared DTOs and validation schemas.
6. Unit, API, UI, and smoke tests appropriate to the repository.
7. A short developer document explaining how to run the manager.
8. A summary of files changed.
9. Exact verification commands and their results.
10. Any remaining limitations without overstating completion.
```

---

# 42. Reference documents

Use these existing project artifacts as the primary source of truth:

```text
ontology/ontology.yaml
operational-ontology_ontology_implementation_context.md
Context.txt
```

Official Palantir documentation may be used only for conceptual inspiration:

- Ontology overview: https://www.palantir.com/docs/foundry/ontology/overview/
- Ontology core concepts: https://www.palantir.com/docs/foundry/ontology/core-concepts/
- Ontology system architecture: https://www.palantir.com/docs/foundry/architecture-center/ontology-system/
- Ontology Manager overview: https://www.palantir.com/docs/foundry/ontology-manager/overview/
- Ontology Manager navigation: https://www.palantir.com/docs/foundry/ontology-manager/navigation/
- Ontology best practices: https://www.palantir.com/docs/foundry/ontology/ontology-best-practices/
- Derived properties: https://www.palantir.com/docs/foundry/ontology/derived-properties/
- Action types overview: https://www.palantir.com/docs/foundry/action-types/overview/
- Ontology SDK overview: https://www.palantir.com/docs/foundry/ontology-sdk/overview/
- Ontology MCP overview: https://www.palantir.com/docs/foundry/ontology-mcp/overview/

Do not copy Palantir branding, proprietary UI, or implementation details. Build an original lightweight system based on the general architectural concepts.

---

# 43. Final implementation principle

The Ontology Manager should make the ontology easy to understand without becoming the ontology runtime itself.

```text
It reads definitions.
It validates definitions.
It indexes definitions.
It explains definitions.
It visualizes definitions.
It does not mutate definitions.
It does not execute operational logic.
```

The success of Version 1 is not measured by how many features it contains. It is measured by whether a developer, operator, or reviewer can open the manager and clearly understand how operational-ontology models its operational world.
