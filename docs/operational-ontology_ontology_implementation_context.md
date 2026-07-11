# operational-ontology Ontology Implementation Context

## 1. Purpose of this document

This document is the complete implementation context for creating the first version of the `ontology.yaml` file for **operational-ontology**, a Palantir Foundry Ontology-inspired supply-chain disruption response system.

The agent consuming this document should use it as the source of truth for:

- object type definitions
- stored and derived properties
- link type definitions
- ontology functions
- governed actions
- action parameters and validation rules
- roles and permissions
- audit requirements
- backing PostgreSQL table mappings
- ontology runtime expectations
- YAML structure
- implementation boundaries
- acceptance criteria

The goal is not to copy Palantir or claim official Palantir integration. The goal is to implement a lightweight, open-source ontology and operational layer inspired by Palantir Foundry concepts.

---

# 2. Project goal

operational-ontology is a supply-chain disruption response platform.

The system must convert operational supply-chain data into business objects, relationships, functions, governed actions, permissions, and audit history.

The primary workflow is:

```text
Supplier delay detected
→ RiskEvent created
→ impacted Parts discovered
→ impacted Products discovered
→ impacted CustomerOrders discovered
→ available Inventory checked
→ mitigation options generated
→ MitigationPlan created
→ Planner submits the plan
→ Operations Manager approves the plan
→ approved steps are executed
→ every action is audited
→ AI explains the recommendation
```

This should not behave like a normal CRUD application.

Avoid exposing generic write operations such as:

```text
PATCH /inventory/:id
PATCH /purchase-orders/:id
```

Prefer governed ontology actions such as:

```text
POST /actions/reallocateInventory
POST /actions/expeditePurchaseOrder
POST /actions/approveMitigationPlan
```

---

# 3. Architecture decisions

## 3.1 Source of truth

The ontology definition must live in:

```text
ontology/ontology.yaml
```

The YAML file is the source of truth for ontology metadata.

It must be:

- human-readable
- version-controlled
- validated during application startup
- deterministic
- independent of runtime business data
- usable by the lightweight Ontology Manager UI
- usable by the ontology runtime and MCP layer

## 3.2 What lives in PostgreSQL

PostgreSQL stores:

- actual supply-chain business data
- workflow data
- risk events
- mitigation plans
- mitigation steps
- inventory transfers
- action execution history
- audit records
- AI tool-call history when enabled

## 3.3 What lives in backend code

Backend code stores:

- function handler implementations
- action handler implementations
- validation logic
- permission enforcement
- transactional write logic
- audit recording logic
- ontology registry loader
- MCP tool implementations

The YAML file must reference handlers by stable names. It must not contain executable code.

## 3.4 Ontology Manager scope

Version 1 of the Ontology Manager is read-only.

It should display:

- object types
- properties
- derived properties
- links
- functions
- actions
- required roles
- backing tables
- descriptions
- UI labels and categories

Do not implement ontology editing, publishing, rollback, or ontology version management in Version 1.

---

# 4. Required top-level YAML structure

The generated `ontology.yaml` should follow this structure:

```yaml
ontology:
  key: supplyGraph
  displayName: operational-ontology
  version: 1.0.0
  description: >
    Supply-chain disruption response ontology for connected business objects,
    governed actions, reusable functions, permissions, and auditability.

objectTypes: {}

linkTypes: {}

functions: {}

actions: {}

roles: {}

permissions: {}

settings: {}
```

Recommended additional settings:

```yaml
settings:
  defaultPropertyReadOnly: true
  writesThroughActionsOnly: true
  auditAllActions: true
  requireIdempotencyKeyForActions: true
  requireReasonForCriticalActions: true
  aiCanExecuteCriticalActions: false
```

---

# 5. Common ontology conventions

## 5.1 Naming

Use PascalCase for:

- object type keys

Examples:

```text
Supplier
RiskEvent
MitigationPlan
InventoryTransfer
```

Use camelCase for:

- property keys
- link keys
- function keys
- action keys
- handler names

Examples:

```text
supplierId
requiredDeliveryDate
findImpactedOrders
approveMitigationPlan
```

Use snake_case only for PostgreSQL table and column names.

## 5.2 Object type metadata

Every object type should support:

```yaml
key: Supplier
displayName: Supplier
description: Company that supplies one or more parts.

source:
  table: suppliers
  primaryKey: supplier_id

titleProperty: name

properties: {}
derivedProperties: {}
links: []
functions: []
actions: []
permissions: {}

ui:
  category: Master Data
  icon: building
  order: 1
```

## 5.3 Property metadata

Each stored property should support:

```yaml
status:
  displayName: Status
  sourceColumn: status
  type: enum
  required: true
  readOnly: true
  indexed: true
  sortable: true
  filterable: true
  description: Current operational status.
  enumValues:
    - active
    - delayed
    - inactive
```

Valid property types may include:

```text
string
integer
number
boolean
date
datetime
enum
json
currency
```

## 5.4 Derived property metadata

Derived properties must reference a function or deterministic expression.

Example:

```yaml
availableQuantity:
  displayName: Available Quantity
  type: number
  derived: true
  resolver:
    type: expression
    expression: onHandQuantity - reservedQuantity
```

Or:

```yaml
riskScore:
  displayName: Risk Score
  type: number
  derived: true
  resolver:
    type: function
    function: calculateOrderRisk
```

Derived properties must never be directly writable.

## 5.5 Writes

All properties are read-only by default.

Operational changes must happen through actions.

Do not define generic update actions for every object.

Only define meaningful business actions.

---

# 6. Final object types

There are 16 object types in Version 1.

---

## 6.1 Supplier

### Business meaning

A company that supplies one or more parts.

### Backing source

```text
table: suppliers
primary key: supplier_id
title property: name
```

### Stored properties

```text
supplierId
name
country
region
status
reliabilityScore
defaultLeadTimeDays
createdAt
updatedAt
```

### Property expectations

```text
supplierId: string, required, read-only, indexed
name: string, required, searchable
country: string, optional
region: string, optional
status: enum(active, delayed, inactive), required
reliabilityScore: number from 0 to 100
defaultLeadTimeDays: integer greater than or equal to 0
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Derived properties

```text
openRiskCount
currentRiskLevel
activePurchaseOrderCount
suppliedPartCount
```

### Links

```text
supplierParts
riskEvents
purchaseOrders
```

### Functions

```text
findImpactedParts
findImpactedProducts
findImpactedOrders
```

### Actions

```text
createRiskEvent
```

---

## 6.2 Part

### Business meaning

A component used to manufacture one or more products.

### Backing source

```text
table: parts
primary key: part_id
title property: name
```

### Stored properties

```text
partId
sku
name
category
unitOfMeasure
safetyStockQuantity
status
createdAt
updatedAt
```

### Property expectations

```text
partId: string, required, read-only, indexed
sku: string, required, unique, searchable
name: string, required, searchable
category: string, optional
unitOfMeasure: string, required
safetyStockQuantity: number greater than or equal to 0
status: enum(active, inactive, discontinued)
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Derived properties

```text
totalOnHandQuantity
totalAvailableQuantity
affectedProductCount
shortageRisk
```

### Links

```text
supplierParts
productRequirements
inventoryPositions
purchaseOrderLines
```

### Functions

```text
calculateStockoutRisk
getInventoryAvailability
findAlternativeWarehouses
findExpeditablePurchaseOrders
```

### Actions

No direct write actions in Version 1.

---

## 6.3 Product

### Business meaning

A finished product sold through customer orders.

### Backing source

```text
table: products
primary key: product_id
title property: name
```

### Stored properties

```text
productId
sku
name
category
status
createdAt
updatedAt
```

### Property expectations

```text
productId: string, required, read-only, indexed
sku: string, required, unique, searchable
name: string, required, searchable
category: string, optional
status: enum(active, inactive, discontinued)
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Derived properties

```text
maximumBuildableQuantity
requiredPartCount
openOrderQuantity
riskLevel
```

### Links

```text
productRequirements
orderLines
```

### Functions

```text
findImpactedProducts
```

### Actions

No direct write actions in Version 1.

---

## 6.4 Warehouse

### Business meaning

A physical storage or fulfillment location.

### Backing source

```text
table: warehouses
primary key: warehouse_id
title property: name
```

### Stored properties

```text
warehouseId
name
code
city
region
country
capacity
status
createdAt
updatedAt
```

### Property expectations

```text
warehouseId: string, required, read-only, indexed
name: string, required, searchable
code: string, required, unique
city: string, optional
region: string, optional
country: string, optional
capacity: number greater than or equal to 0
status: enum(active, inactive)
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Derived properties

```text
inventoryUtilization
availablePartCount
openTransferCount
```

### Links

```text
inventoryPositions
outgoingTransfers
incomingTransfers
shipments
```

### Functions

```text
getInventoryAvailability
findAlternativeWarehouses
```

### Actions

No direct write actions in Version 1.

---

## 6.5 SupplierPart

### Business meaning

An object-backed relationship representing a supplier's ability and agreement to provide a specific part.

### Backing source

```text
table: supplier_parts
primary key: supplier_part_id
title property: supplierPartId
```

### Stored properties

```text
supplierPartId
supplierId
partId
unitCost
leadTimeDays
maximumWeeklyCapacity
minimumOrderQuantity
isPreferredSupplier
status
createdAt
updatedAt
```

### Property expectations

```text
supplierPartId: string, required, read-only
supplierId: string, required, indexed
partId: string, required, indexed
unitCost: currency, greater than or equal to 0
leadTimeDays: integer greater than or equal to 0
maximumWeeklyCapacity: number greater than or equal to 0
minimumOrderQuantity: number greater than or equal to 0
isPreferredSupplier: boolean
status: enum(active, inactive, suspended)
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Links

```text
supplier
part
```

### Actions

No direct write actions in Version 1.

---

## 6.6 ProductPartRequirement

### Business meaning

An object-backed relationship representing one part requirement in a product's bill of materials.

### Backing source

```text
table: product_part_requirements
primary key: requirement_id
title property: requirementId
```

### Stored properties

```text
requirementId
productId
partId
quantityRequired
criticality
substitutionAllowed
createdAt
updatedAt
```

### Property expectations

```text
requirementId: string, required, read-only
productId: string, required, indexed
partId: string, required, indexed
quantityRequired: number greater than 0
criticality: enum(low, medium, high, critical)
substitutionAllowed: boolean
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Links

```text
product
requiredPart
```

### Actions

No direct write actions in Version 1.

---

## 6.7 InventoryPosition

### Business meaning

Inventory for one part at one warehouse.

### Backing source

```text
table: inventory_positions
primary key: inventory_position_id
title property: inventoryPositionId
```

### Stored properties

```text
inventoryPositionId
warehouseId
partId
onHandQuantity
reservedQuantity
inTransitQuantity
reorderPoint
lastUpdatedAt
```

### Property expectations

```text
inventoryPositionId: string, required, read-only
warehouseId: string, required, indexed
partId: string, required, indexed
onHandQuantity: number greater than or equal to 0
reservedQuantity: number greater than or equal to 0
inTransitQuantity: number greater than or equal to 0
reorderPoint: number greater than or equal to 0
lastUpdatedAt: datetime, read-only
```

### Derived properties

```text
availableQuantity = onHandQuantity - reservedQuantity
```

### Links

```text
warehouse
stockedPart
```

### Functions

```text
calculateStockoutRisk
getInventoryAvailability
findAlternativeWarehouses
```

### Actions

```text
reallocateInventory
```

Inventory must never be changed through a generic update endpoint.

---

## 6.8 CustomerOrder

### Business meaning

A customer's purchase order for one or more products.

### Backing source

```text
table: customer_orders
primary key: order_id
title property: orderNumber
```

### Stored properties

```text
orderId
orderNumber
customerName
destinationWarehouseId
priority
status
orderDate
requiredDeliveryDate
createdAt
updatedAt
```

### Property expectations

```text
orderId: string, required, read-only
orderNumber: string, required, unique, searchable
customerName: string, required, searchable
destinationWarehouseId: string, optional
priority: enum(low, normal, high, critical)
status: enum(draft, confirmed, allocated, partially_fulfilled, fulfilled, delayed, cancelled)
orderDate: date, required
requiredDeliveryDate: date, required
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Derived properties

```text
riskScore
riskLevel
projectedDelayDays
impactedByOpenRisk
totalOrderedQuantity
totalFulfilledQuantity
```

### Links

```text
orderLines
shipments
destinationWarehouse
```

### Functions

```text
findImpactedOrders
rankImpactedOrders
```

### Actions

No direct write actions in Version 1.

---

## 6.9 OrderLine

### Business meaning

A product and quantity inside a customer order.

### Backing source

```text
table: order_lines
primary key: order_line_id
title property: orderLineId
```

### Stored properties

```text
orderLineId
orderId
productId
quantity
allocatedQuantity
fulfilledQuantity
unitPrice
createdAt
updatedAt
```

### Property expectations

```text
orderLineId: string, required, read-only
orderId: string, required, indexed
productId: string, required, indexed
quantity: number greater than 0
allocatedQuantity: number greater than or equal to 0
fulfilledQuantity: number greater than or equal to 0
unitPrice: currency greater than or equal to 0
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Links

```text
order
orderedProduct
```

### Actions

No direct write actions in Version 1.

---

## 6.10 Shipment

### Business meaning

Physical fulfillment of a customer order from a warehouse.

### Backing source

```text
table: shipments
primary key: shipment_id
title property: shipmentNumber
```

### Stored properties

```text
shipmentId
shipmentNumber
orderId
warehouseId
carrier
priority
status
plannedShipDate
estimatedDeliveryDate
actualDeliveryDate
trackingNumber
createdAt
updatedAt
```

### Property expectations

```text
shipmentId: string, required, read-only
shipmentNumber: string, required, unique
orderId: string, required, indexed
warehouseId: string, required, indexed
carrier: string, optional
priority: enum(low, normal, high, critical)
status: enum(planned, ready, shipped, in_transit, delivered, delayed, cancelled)
plannedShipDate: date, optional
estimatedDeliveryDate: date, optional
actualDeliveryDate: date, optional
trackingNumber: string, optional
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Derived properties

```text
projectedDelayDays
isLate
```

### Links

```text
order
originWarehouse
```

### Actions

```text
prioritizeShipment
```

---

## 6.11 PurchaseOrder

### Business meaning

An order placed with a supplier for one or more parts.

### Backing source

```text
table: purchase_orders
primary key: purchase_order_id
title property: purchaseOrderNumber
```

### Stored properties

```text
purchaseOrderId
purchaseOrderNumber
supplierId
destinationWarehouseId
status
orderDate
expectedDeliveryDate
expedited
expediteCost
createdAt
updatedAt
```

### Property expectations

```text
purchaseOrderId: string, required, read-only
purchaseOrderNumber: string, required, unique
supplierId: string, required, indexed
destinationWarehouseId: string, required, indexed
status: enum(draft, submitted, confirmed, partially_received, received, delayed, cancelled)
orderDate: date, required
expectedDeliveryDate: date, required
expedited: boolean
expediteCost: currency greater than or equal to 0
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Derived properties

```text
openQuantity
receivedQuantity
isLate
projectedDelayDays
```

### Links

```text
supplier
destinationWarehouse
purchaseOrderLines
```

### Functions

```text
findExpeditablePurchaseOrders
```

### Actions

```text
expeditePurchaseOrder
```

---

## 6.12 PurchaseOrderLine

### Business meaning

A part and quantity inside a purchase order.

### Backing source

```text
table: purchase_order_lines
primary key: purchase_order_line_id
title property: purchaseOrderLineId
```

### Stored properties

```text
purchaseOrderLineId
purchaseOrderId
partId
quantityOrdered
quantityReceived
unitCost
createdAt
updatedAt
```

### Property expectations

```text
purchaseOrderLineId: string, required, read-only
purchaseOrderId: string, required, indexed
partId: string, required, indexed
quantityOrdered: number greater than 0
quantityReceived: number greater than or equal to 0
unitCost: currency greater than or equal to 0
createdAt: datetime, read-only
updatedAt: datetime, read-only
```

### Links

```text
purchaseOrder
orderedPart
```

### Actions

No direct write actions in Version 1.

---

## 6.13 RiskEvent

### Business meaning

A detected operational disruption.

Version 1 primarily supports supplier delay risks.

### Backing source

```text
table: risk_events
primary key: risk_event_id
title property: riskEventId
```

### Stored properties

```text
riskEventId
riskType
supplierId
severity
status
delayDays
detectedAt
expectedResolutionDate
reason
source
createdBy
createdAt
updatedAt
resolvedAt
```

### Enum values

```text
riskType:
- supplier_delay

severity:
- low
- medium
- high
- critical

status:
- open
- acknowledged
- mitigated
- resolved
```

### Property expectations

```text
riskEventId: string, required, read-only
riskType: enum, required
supplierId: string, required, indexed
severity: enum, required
status: enum, required
delayDays: integer greater than 0
detectedAt: datetime, required
expectedResolutionDate: date, optional
reason: string, required
source: enum(manual, integration, ai_detected, simulation)
createdBy: string, required
createdAt: datetime, read-only
updatedAt: datetime, read-only
resolvedAt: datetime, optional, read-only
```

### Derived properties

```text
impactedPartCount
impactedProductCount
impactedOrderCount
estimatedRevenueAtRisk
highestOrderRiskScore
```

### Links

```text
supplier
mitigationPlans
```

### Derived links

```text
impactedParts
impactedProducts
impactedOrders
alternativeWarehouses
```

### Functions

```text
findImpactedParts
findImpactedProducts
findImpactedOrders
rankImpactedOrders
recommendMitigationPlan
```

### Actions

```text
acknowledgeRiskEvent
generateMitigationPlan
resolveRiskEvent
```

---

## 6.14 MitigationPlan

### Business meaning

A proposed operational response to a risk event.

### Backing source

```text
table: mitigation_plans
primary key: mitigation_plan_id
title property: mitigationPlanId
```

### Stored properties

```text
mitigationPlanId
riskEventId
status
strategy
summary
confidenceScore
estimatedCost
generatedBy
submittedBy
approvedBy
rejectedBy
createdAt
submittedAt
approvedAt
rejectedAt
completedAt
```

### Enum values

```text
status:
- draft
- pending_approval
- approved
- rejected
- executing
- completed
- failed
```

### Property expectations

```text
mitigationPlanId: string, required, read-only
riskEventId: string, required, indexed
status: enum, required
strategy: string, required
summary: string, required
confidenceScore: number from 0 to 1
estimatedCost: currency greater than or equal to 0
generatedBy: enum(user, ai_agent, system)
submittedBy: string, optional
approvedBy: string, optional
rejectedBy: string, optional
createdAt: datetime, read-only
submittedAt: datetime, optional, read-only
approvedAt: datetime, optional, read-only
rejectedAt: datetime, optional, read-only
completedAt: datetime, optional, read-only
```

### Derived properties

```text
stepCount
projectedOrdersRecovered
projectedRevenueProtected
feasibilityStatus
```

### Links

```text
riskEvent
mitigationSteps
inventoryTransfers
```

### Functions

```text
validateMitigationPlan
```

### Actions

```text
submitMitigationPlan
approveMitigationPlan
rejectMitigationPlan
executeMitigationPlan
```

---

## 6.15 MitigationStep

### Business meaning

One operation inside a mitigation plan.

### Backing source

```text
table: mitigation_steps
primary key: mitigation_step_id
title property: mitigationStepId
```

### Stored properties

```text
mitigationStepId
mitigationPlanId
sequenceNumber
stepType
targetObjectType
targetObjectId
parameters
status
estimatedCost
expectedBenefit
failureReason
createdAt
executedAt
```

### Enum values

```text
stepType:
- reallocate_inventory
- expedite_purchase_order
- prioritize_shipment

status:
- pending
- validated
- executing
- completed
- failed
- skipped
```

### Property expectations

```text
mitigationStepId: string, required, read-only
mitigationPlanId: string, required, indexed
sequenceNumber: integer greater than 0
stepType: enum, required
targetObjectType: string, required
targetObjectId: string, required
parameters: json, required
status: enum, required
estimatedCost: currency greater than or equal to 0
expectedBenefit: json or structured object
failureReason: string, optional
createdAt: datetime, read-only
executedAt: datetime, optional, read-only
```

The `parameters` field must be validated against the corresponding action parameter schema.

### Links

```text
mitigationPlan
```

### Actions

Mitigation steps are executed through `executeMitigationPlan`. Do not expose a generic execute-step action in Version 1.

---

## 6.16 InventoryTransfer

### Business meaning

Inventory moving from one warehouse to another.

### Backing source

```text
table: inventory_transfers
primary key: inventory_transfer_id
title property: transferNumber
```

### Stored properties

```text
inventoryTransferId
transferNumber
mitigationPlanId
partId
sourceWarehouseId
destinationWarehouseId
quantity
status
reason
requestedBy
approvedBy
requestedAt
approvedAt
shippedAt
completedAt
```

### Enum values

```text
status:
- requested
- approved
- in_transit
- completed
- cancelled
- failed
```

### Property expectations

```text
inventoryTransferId: string, required, read-only
transferNumber: string, required, unique
mitigationPlanId: string, required, indexed
partId: string, required, indexed
sourceWarehouseId: string, required, indexed
destinationWarehouseId: string, required, indexed
quantity: number greater than 0
status: enum, required
reason: string, required
requestedBy: string, required
approvedBy: string, optional
requestedAt: datetime, read-only
approvedAt: datetime, optional, read-only
shippedAt: datetime, optional, read-only
completedAt: datetime, optional, read-only
```

### Links

```text
mitigationPlan
part
sourceWarehouse
destinationWarehouse
```

### Actions

```text
completeInventoryTransfer
```

---

# 7. Final link types

Links should be defined centrally under `linkTypes`.

Each link should contain:

```yaml
supplier:
  displayName: Supplier
  fromObjectType: SupplierPart
  toObjectType: Supplier
  cardinality: many-to-one
  backing:
    type: foreignKey
    fromProperty: supplierId
    toProperty: supplierId
```

## 7.1 Stored links

Define at least the following links:

| Link key | From | To | Cardinality |
|---|---|---|---|
| supplierParts | Supplier | SupplierPart | one-to-many |
| supplier | SupplierPart | Supplier | many-to-one |
| part | SupplierPart | Part | many-to-one |
| productRequirements | Product | ProductPartRequirement | one-to-many |
| product | ProductPartRequirement | Product | many-to-one |
| requiredPart | ProductPartRequirement | Part | many-to-one |
| inventoryPositions | Warehouse | InventoryPosition | one-to-many |
| warehouse | InventoryPosition | Warehouse | many-to-one |
| stockedPart | InventoryPosition | Part | many-to-one |
| orderLines | CustomerOrder | OrderLine | one-to-many |
| order | OrderLine | CustomerOrder | many-to-one |
| orderedProduct | OrderLine | Product | many-to-one |
| shipments | CustomerOrder | Shipment | one-to-many |
| originWarehouse | Shipment | Warehouse | many-to-one |
| purchaseOrders | Supplier | PurchaseOrder | one-to-many |
| purchaseOrderSupplier | PurchaseOrder | Supplier | many-to-one |
| purchaseOrderLines | PurchaseOrder | PurchaseOrderLine | one-to-many |
| purchaseOrder | PurchaseOrderLine | PurchaseOrder | many-to-one |
| orderedPart | PurchaseOrderLine | Part | many-to-one |
| riskEvents | Supplier | RiskEvent | one-to-many |
| riskSupplier | RiskEvent | Supplier | many-to-one |
| mitigationPlans | RiskEvent | MitigationPlan | one-to-many |
| riskEvent | MitigationPlan | RiskEvent | many-to-one |
| mitigationSteps | MitigationPlan | MitigationStep | one-to-many |
| mitigationPlan | MitigationStep | MitigationPlan | many-to-one |
| inventoryTransfers | MitigationPlan | InventoryTransfer | one-to-many |
| transferPlan | InventoryTransfer | MitigationPlan | many-to-one |
| transferPart | InventoryTransfer | Part | many-to-one |
| sourceWarehouse | InventoryTransfer | Warehouse | many-to-one |
| destinationWarehouse | InventoryTransfer | Warehouse | many-to-one |
| destinationWarehouse | CustomerOrder | Warehouse | many-to-one |
| purchaseOrderDestinationWarehouse | PurchaseOrder | Warehouse | many-to-one |

Avoid ambiguous duplicate link keys. If the same business label appears for multiple object types, use unique internal keys and a human-readable display name.

## 7.2 Business-facing flattened links

The ontology runtime should expose convenient links resolved through relationship objects:

```text
Supplier supplies Part
Product requires Part
Warehouse stocks Part
CustomerOrder contains Product
PurchaseOrder orders Part
Shipment fulfills CustomerOrder
```

These may be represented as derived or path-based links.

Example:

```text
Supplier
→ SupplierPart
→ Part
```

may be exposed as:

```text
Supplier supplies Part
```

## 7.3 Derived links

The following links are computed at runtime:

```text
RiskEvent impacts Part
RiskEvent impacts Product
RiskEvent impacts CustomerOrder
CustomerOrder affectedBy RiskEvent
RiskEvent hasAlternativeWarehouse
```

Derived links must reference ontology functions and must not create duplicate persisted relationship rows.

---

# 8. Final functions

Functions are read-only.

They may query and calculate, but they must never modify operational data.

Every function definition should contain:

```yaml
findImpactedOrders:
  displayName: Find Impacted Orders
  description: Finds customer orders affected by a risk event.
  handler: findImpactedOrders
  readOnly: true
  inputSchema: {}
  outputSchema: {}
  permissions:
    allowedRoles: []
```

---

## 8.1 findImpactedParts

### Input

```text
riskEventId: string
```

### Output

A list containing:

```text
partId
supplierPartId
delayDays
openPurchaseOrderQuantity
impactReason
```

### Traversal

```text
RiskEvent → Supplier → SupplierPart → Part
```

### Allowed roles

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

---

## 8.2 findImpactedProducts

### Input

```text
riskEventId: string
```

### Output

```text
productId
impactedPartIds
requiredQuantities
partCriticality
productRiskLevel
```

### Traversal

```text
RiskEvent
→ Supplier
→ SupplierPart
→ Part
→ ProductPartRequirement
→ Product
```

### Allowed roles

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

---

## 8.3 findImpactedOrders

### Input

```text
riskEventId: string
```

### Output

```text
orderId
priority
requiredDeliveryDate
impactedProducts
shortageQuantity
riskScore
projectedDelayDays
```

### Traversal

```text
RiskEvent
→ Supplier
→ Part
→ Product
→ OrderLine
→ CustomerOrder
```

### Allowed roles

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

---

## 8.4 calculateStockoutRisk

### Input

```text
partId: string
warehouseId: string
horizonDate: date
```

### Output

```text
availableQuantity
requiredQuantity
shortageQuantity
daysUntilStockout
riskScore
riskLevel
```

### Risk level values

```text
none
low
medium
high
critical
```

### Allowed roles

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

---

## 8.5 getInventoryAvailability

### Input

```text
partId: string
warehouseId: optional string
requiredByDate: optional date
```

### Output

A list containing:

```text
warehouseId
onHandQuantity
reservedQuantity
availableQuantity
inTransitQuantity
```

### Allowed roles

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

---

## 8.6 findAlternativeWarehouses

### Input

```text
partId: string
destinationWarehouseId: string
requiredQuantity: number
requiredByDate: date
```

### Output

```text
warehouseId
availableQuantity
transferableQuantity
estimatedTransferDays
estimatedTransferCost
feasible
```

### Business rule

Transferable inventory must preserve safety stock at the source warehouse.

### Allowed roles

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

---

## 8.7 findExpeditablePurchaseOrders

### Input

```text
partId: string
supplierId: optional string
requiredByDate: date
```

### Output

```text
purchaseOrderId
openQuantity
currentExpectedDate
possibleExpeditedDate
additionalCost
feasible
```

### Allowed roles

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

---

## 8.8 rankImpactedOrders

### Input

```text
riskEventId: string
```

### Output

An ordered list of impacted customer orders.

### Ranking factors

```text
order priority
required delivery date
shortage quantity
projected delay
order value
part criticality
```

### Allowed roles

```text
Viewer
Planner
OperationsManager
Admin
AIAgent
```

---

## 8.9 recommendMitigationPlan

### Input

```text
riskEventId: string
```

### Output

```text
recommendedStrategy
mitigationSteps
estimatedCost
projectedOrdersRecovered
projectedRevenueProtected
confidenceScore
explanation
```

### Possible step recommendations

```text
reallocate_inventory
expedite_purchase_order
prioritize_shipment
```

### Important rule

This function must not create a mitigation plan record.

It only returns a recommendation.

The `generateMitigationPlan` action creates the persisted plan and steps.

### Allowed roles

```text
Planner
OperationsManager
Admin
AIAgent
```

---

## 8.10 validateMitigationPlan

### Input

```text
mitigationPlanId: string
```

### Output

```text
valid
validationErrors
validationWarnings
latestInventorySnapshot
latestPurchaseOrderSnapshot
estimatedCost
```

### Required execution points

Run this function:

```text
before submission
before approval
immediately before execution
```

### Allowed roles

```text
Planner
OperationsManager
Admin
```

The AI may inspect a validation result only when the surrounding workflow explicitly permits it, but should not use this function to bypass approval controls.

---

# 9. Final actions

Actions are the only supported way to change operational data.

Every action definition must contain:

```yaml
createRiskEvent:
  displayName: Create Risk Event
  targetObjectType: Supplier
  handler: createRiskEvent
  parameters: {}
  validationRules: []
  allowedRoles: []
  audit:
    enabled: true
    reasonRequired: true
  transaction:
    required: true
  idempotency:
    required: true
```

## 9.1 Common action requirements

Every action must:

- authenticate the actor
- authorize the actor's role
- validate all input parameters
- validate current object state
- run inside a database transaction when writes occur
- support an idempotency key
- record an action execution
- record all affected objects
- record before and after values
- record changed properties
- record timestamps
- record failure details
- record the action definition version
- reject unknown parameters
- avoid partial writes

---

## 9.2 createRiskEvent

### Target

```text
Supplier
```

### Parameters

```text
supplierId: string
delayDays: integer greater than 0
severity: enum(low, medium, high, critical)
detectedAt: datetime
expectedResolutionDate: optional date
reason: string
source: enum(manual, integration, ai_detected, simulation)
```

### Allowed roles

```text
Planner
OperationsManager
Admin
```

### Validation

```text
Supplier must exist.
Supplier must be active.
delayDays must be greater than zero.
An identical open risk event must not already exist.
reason is required.
```

### Effects

```text
Create RiskEvent.
Record the originating Supplier.
Record audit entry.
```

Do not directly persist a derived supplier risk level unless the implementation explicitly chooses a cached projection.

---

## 9.3 acknowledgeRiskEvent

### Target

```text
RiskEvent
```

### State transition

```text
open → acknowledged
```

### Parameters

```text
riskEventId: string
reason: string
```

### Allowed roles

```text
Planner
OperationsManager
Admin
```

### Validation

```text
RiskEvent must exist.
RiskEvent status must be open.
reason is required.
```

---

## 9.4 generateMitigationPlan

### Target

```text
RiskEvent
```

### Parameters

```text
riskEventId: string
optional strategyPreference: string
optional notes: string
```

### Allowed roles

```text
Planner
OperationsManager
Admin
AIAgent
```

### Process

```text
Run recommendMitigationPlan.
Create MitigationPlan with draft status.
Create MitigationStep objects.
Persist the recommendation snapshot.
Record generator type and actor.
Audit the action.
```

### Important rule

The AI agent may invoke this action because it only creates a draft.

---

## 9.5 submitMitigationPlan

### Target

```text
MitigationPlan
```

### State transition

```text
draft → pending_approval
```

### Parameters

```text
mitigationPlanId: string
reason: string
```

### Allowed roles

```text
Planner
OperationsManager
Admin
```

### Validation

```text
Plan must exist.
Plan status must be draft.
Plan must have at least one MitigationStep.
summary must be present.
estimatedCost must be present.
validateMitigationPlan must return valid = true.
reason is required.
```

### Effects

```text
Set status to pending_approval.
Set submittedBy.
Set submittedAt.
Persist validation snapshot.
Audit the action.
```

---

## 9.6 approveMitigationPlan

### Target

```text
MitigationPlan
```

### State transition

```text
pending_approval → approved
```

### Parameters

```text
mitigationPlanId: string
reason: string
```

### Allowed roles

```text
OperationsManager
Admin
```

### Validation

```text
Plan must exist.
Plan status must be pending_approval.
Approver cannot be the same user who submitted the plan.
validateMitigationPlan must return valid = true.
Current inventory snapshot must be recorded.
Current purchase-order snapshot must be recorded.
reason is required.
```

### Effects

```text
Set status to approved.
Set approvedBy.
Set approvedAt.
Persist approval snapshot.
Audit the action.
```

---

## 9.7 rejectMitigationPlan

### Target

```text
MitigationPlan
```

### State transition

```text
pending_approval → rejected
```

### Parameters

```text
mitigationPlanId: string
reason: string
```

### Allowed roles

```text
OperationsManager
Admin
```

### Validation

```text
Plan must exist.
Plan status must be pending_approval.
reason is required.
```

### Effects

```text
Set status to rejected.
Set rejectedBy.
Set rejectedAt.
Audit the action.
```

---

## 9.8 executeMitigationPlan

### Target

```text
MitigationPlan
```

### State transitions

```text
approved → executing → completed
approved → executing → failed
```

### Parameters

```text
mitigationPlanId: string
reason: string
```

### Allowed roles

```text
OperationsManager
Admin
```

### Validation

```text
Plan must exist.
Plan status must be approved.
validateMitigationPlan must return valid = true immediately before execution.
All required steps must have valid parameters.
reason is required.
```

### Process

```text
Set plan status to executing.
Execute MitigationStep objects in sequence order.
Dispatch each step to the corresponding governed action.
Record success or failure for every step.
Mark plan completed only when all required steps succeed.
Mark plan failed when a required step fails.
Audit every step and the parent action.
```

### Important rule

The AI agent cannot execute this action.

---

## 9.9 reallocateInventory

### Targets

```text
InventoryPosition
InventoryTransfer
MitigationStep
```

### Parameters

```text
partId: string
sourceWarehouseId: string
destinationWarehouseId: string
quantity: number greater than 0
mitigationPlanId: string
reason: string
```

### Allowed roles

```text
OperationsManager
Admin
```

### Validation

```text
Source and destination warehouses must exist.
Source and destination must be different.
Part must exist.
Source inventory position must exist.
Source available inventory must be sufficient.
Transfer must preserve source safety stock.
MitigationPlan must exist.
MitigationPlan status must be approved or executing.
Quantity must be greater than zero.
reason is required.
```

### Effects

```text
Create InventoryTransfer.
Reserve quantity at source warehouse.
Set transfer status to approved or requested according to implementation.
Update related MitigationStep status.
Record all before and after inventory values.
```

### Important rule

Do not immediately increase destination on-hand inventory.

Destination inventory increases only when the transfer is completed.

---

## 9.10 completeInventoryTransfer

### Target

```text
InventoryTransfer
```

### Parameters

```text
inventoryTransferId: string
completedAt: datetime
reason: string
```

### Allowed roles

```text
OperationsManager
Admin
```

### Validation

```text
Transfer must exist.
Transfer status must be approved or in_transit.
Source and destination inventory positions must exist.
Quantity must be positive.
reason is required.
```

### Transactional effects

```text
Decrease source on-hand quantity.
Decrease source reserved quantity.
Increase destination on-hand quantity.
Set transfer status to completed.
Set completedAt.
Update related MitigationStep.
Audit all affected inventory positions and the transfer.
```

All inventory changes must happen in one database transaction.

---

## 9.11 expeditePurchaseOrder

### Target

```text
PurchaseOrder
```

### Parameters

```text
purchaseOrderId: string
newExpectedDeliveryDate: date
additionalCost: currency greater than or equal to 0
mitigationPlanId: string
reason: string
```

### Allowed roles

```text
OperationsManager
Admin
```

### Validation

```text
PurchaseOrder must exist.
PurchaseOrder must be open.
PurchaseOrder cannot be received or cancelled.
newExpectedDeliveryDate must be earlier than current expectedDeliveryDate.
Affected purchase-order part must be relevant to the mitigation plan.
MitigationPlan must be approved or executing.
reason is required.
```

### Effects

```text
Set expedited = true.
Update expectedDeliveryDate.
Record expediteCost.
Update related MitigationStep.
Audit before and after values.
```

---

## 9.12 prioritizeShipment

### Target

```text
Shipment
```

### Parameters

```text
shipmentId: string
newPriority: enum(low, normal, high, critical)
mitigationPlanId: string
reason: string
```

### Allowed roles

```text
OperationsManager
Admin
```

### Validation

```text
Shipment must exist.
Shipment cannot be delivered or cancelled.
Shipment must belong to an impacted customer order.
MitigationPlan must be approved or executing.
reason is required.
```

### Effects

```text
Update Shipment priority.
Update related MitigationStep.
Audit before and after values.
```

---

## 9.13 resolveRiskEvent

### Target

```text
RiskEvent
```

### State transition

```text
open → resolved
acknowledged → resolved
mitigated → resolved
```

### Parameters

```text
riskEventId: string
reason: string
resolvedAt: datetime
```

### Allowed roles

```text
OperationsManager
Admin
```

### Validation

```text
RiskEvent must exist.
RiskEvent must not already be resolved.
No related MitigationPlan may still be executing.
reason is required.
```

### Effects

```text
Set RiskEvent status to resolved.
Set resolvedAt.
Audit the action.
```

---

# 10. Roles

There are five roles in Version 1.

---

## 10.1 Viewer

### Can

```text
View ontology metadata
View business objects
Traverse links
Run read-only impact functions
View mitigation plans
View audit history
```

### Cannot

```text
Create or modify operational objects
Submit plans
Approve plans
Execute actions
Modify ontology definitions
```

---

## 10.2 Planner

### Can

Everything Viewer can do, plus:

```text
Create risk events
Acknowledge risk events
Generate mitigation plans
Submit mitigation plans
```

### Cannot

```text
Approve own plan
Approve plans
Execute mitigation plans
Directly move inventory
Expedite purchase orders
Prioritize shipments
Publish ontology changes
```

---

## 10.3 OperationsManager

### Can

Everything Planner can do, plus:

```text
Approve mitigation plans
Reject mitigation plans
Execute mitigation plans
Reallocate inventory
Complete inventory transfers
Expedite purchase orders
Prioritize shipments
Resolve risk events
```

### Cannot

```text
Publish ontology changes unless separately granted Admin role
```

---

## 10.4 Admin

### Can

Perform every operational action and:

```text
Manage users and role assignments
View all audit records
Retry failed action executions
Manage system configuration
Publish ontology configuration changes
```

### Important rule

Admin operations must still be audited.

Admin does not bypass actions or audit requirements.

---

## 10.5 AIAgent

The AI agent is a restricted service role.

### Can

```text
Search and retrieve objects
Traverse links
Run impact-analysis functions
Calculate stockout risk
Find alternative warehouses
Find expeditable purchase orders
Rank impacted orders
Recommend mitigation plans
Generate draft mitigation plans
Explain recommendations
```

### Cannot

```text
Create risk events
Acknowledge risks
Submit a plan
Approve a plan
Reject a plan
Execute a plan
Move inventory
Complete inventory transfers
Expedite purchase orders
Prioritize shipments
Resolve risk events
Modify ontology definitions
Assign roles
```

The AI prepares decisions. Humans control consequential actions.

---

# 11. Permission matrix

The YAML should encode these permissions explicitly.

| Capability | Viewer | Planner | OperationsManager | Admin | AIAgent |
|---|---:|---:|---:|---:|---:|
| View ontology metadata | Yes | Yes | Yes | Yes | Limited |
| View business objects | Yes | Yes | Yes | Yes | Yes |
| Traverse links | Yes | Yes | Yes | Yes | Yes |
| Run read-only functions | Yes | Yes | Yes | Yes | Yes |
| View audit logs | Yes | Yes | Yes | Yes | Limited |
| Create risk event | No | Yes | Yes | Yes | No |
| Acknowledge risk event | No | Yes | Yes | Yes | No |
| Generate draft plan | No | Yes | Yes | Yes | Yes |
| Submit plan | No | Yes | Yes | Yes | No |
| Approve plan | No | No | Yes | Yes | No |
| Reject plan | No | No | Yes | Yes | No |
| Execute plan | No | No | Yes | Yes | No |
| Reallocate inventory | No | No | Yes | Yes | No |
| Complete inventory transfer | No | No | Yes | Yes | No |
| Expedite purchase order | No | No | Yes | Yes | No |
| Prioritize shipment | No | No | Yes | Yes | No |
| Resolve risk event | No | No | Yes | Yes | No |
| Publish ontology changes | No | No | No | Yes | No |

For limited AI access:

- AI may receive only object properties required by its tools.
- AI should not receive unrestricted audit history.
- AI should not receive secrets, credentials, or sensitive internal metadata.
- MCP tools must enforce the same ontology permissions.

---

# 12. Object-to-action mapping

```text
Supplier
└── createRiskEvent

RiskEvent
├── acknowledgeRiskEvent
├── generateMitigationPlan
└── resolveRiskEvent

MitigationPlan
├── submitMitigationPlan
├── approveMitigationPlan
├── rejectMitigationPlan
└── executeMitigationPlan

InventoryPosition
└── reallocateInventory

InventoryTransfer
└── completeInventoryTransfer

PurchaseOrder
└── expeditePurchaseOrder

Shipment
└── prioritizeShipment
```

Not every object requires actions.

The following remain read-only in Version 1:

```text
Part
Product
Warehouse
SupplierPart
ProductPartRequirement
CustomerOrder
OrderLine
PurchaseOrderLine
MitigationStep
```

---

# 13. Audit requirements

Every action execution must create an action execution record.

Recommended backing table:

```text
action_executions
```

Minimum fields:

```text
actionExecutionId
actionType
actionVersion
actorId
actorRole
status
requestedAt
startedAt
completedAt
reason
idempotencyKey
inputParameters
output
errorMessage
correlationId
```

For every affected object, record:

```text
objectType
objectId
operation
beforeValue
afterValue
changedProperties
```

Recommended backing table:

```text
action_execution_objects
```

or a similarly normalized audit table.

For AI-generated plans, record:

```text
model
toolCalls
inputObjectIds
recommendation
confidenceScore
generatedAt
workflowRunId
```

AI free-form reasoning is not the source of truth.

Auditable evidence consists of:

- function inputs
- function outputs
- object IDs
- object snapshots
- tool calls
- action parameters
- before values
- after values
- actor identity
- timestamps

---

# 14. State transition rules

The YAML should define allowed state transitions.

## RiskEvent

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
```

## MitigationPlan

```text
draft → pending_approval
pending_approval → approved
pending_approval → rejected
approved → executing
executing → completed
executing → failed
```

Invalid examples:

```text
draft → approved
rejected → executing
completed → draft
```

## InventoryTransfer

```text
requested → approved
approved → in_transit
approved → completed
in_transit → completed
requested → cancelled
approved → cancelled
in_transit → failed
```

## Shipment

The `prioritizeShipment` action changes priority, not status.

## PurchaseOrder

The `expeditePurchaseOrder` action updates delivery information but does not bypass normal purchase-order status logic.

---

# 15. Required implementation rules

## 15.1 No generic writes

Do not expose generic ontology object updates such as:

```text
PATCH /objects/:objectType/:objectId
```

All operational writes must pass through actions.

## 15.2 Functions never write

Example:

```text
recommendMitigationPlan
```

returns a recommendation.

Example:

```text
generateMitigationPlan
```

creates a persisted draft plan.

## 15.3 Revalidate before execution

Mitigation plans must follow:

```text
generate
→ validate
→ submit
→ validate
→ approve
→ validate
→ execute
```

## 15.4 Critical actions require reasons

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

## 15.5 Idempotency

All actions must accept an idempotency key.

Repeated requests with the same idempotency key must not create duplicate effects.

## 15.6 Transactions

Actions that update multiple objects must execute in a single transaction when possible.

This is mandatory for:

```text
reallocateInventory
completeInventoryTransfer
executeMitigationPlan
```

## 15.7 Derived impacts

Do not persist derived links such as:

```text
RiskEvent impacts CustomerOrder
```

unless storing an explicit historical snapshot for a submitted or approved mitigation plan.

Runtime impact analysis should be computed through functions.

## 15.8 Safety stock

`findAlternativeWarehouses` and `reallocateInventory` must preserve safety stock at the source warehouse.

## 15.9 Approval separation

The same user must not both submit and approve the same mitigation plan.

## 15.10 AI restrictions

The AI agent may:

- read
- traverse
- calculate
- recommend
- create a draft plan

The AI agent may not:

- approve
- execute
- move inventory
- expedite orders
- change shipment priority
- resolve risks
- publish ontology definitions

---

# 16. Ontology runtime expectations

The ontology runtime should be able to:

```text
Load ontology.yaml
Validate ontology.yaml
Register object types
Register properties
Register links
Register functions
Register actions
Register roles
Resolve handler names
Expose object metadata
Fetch objects by type and ID
Traverse stored links
Resolve derived links
Run functions
Authorize actions
Execute actions
Record audit history
Expose safe MCP tools
```

Recommended runtime APIs:

```text
GET /ontology
GET /ontology/object-types
GET /ontology/object-types/:objectType
GET /ontology/link-types
GET /ontology/functions
GET /ontology/actions
GET /ontology/roles

GET /objects/:objectType
GET /objects/:objectType/:objectId
GET /objects/:objectType/:objectId/links
GET /objects/:objectType/:objectId/links/:linkType

POST /functions/:functionName
POST /actions/:actionName
```

The API layer must enforce ontology permissions.

---

# 17. MCP and AI tool mapping

The MCP layer should expose safe ontology tools.

Recommended read tools:

```text
searchObjects
getObject
getLinkedObjects
findImpactedParts
findImpactedProducts
findImpactedOrders
calculateStockoutRisk
getInventoryAvailability
findAlternativeWarehouses
findExpeditablePurchaseOrders
rankImpactedOrders
recommendMitigationPlan
```

Recommended draft action tool:

```text
generateMitigationPlan
```

Do not expose these tools to the AI agent:

```text
approveMitigationPlan
rejectMitigationPlan
executeMitigationPlan
reallocateInventory
completeInventoryTransfer
expeditePurchaseOrder
prioritizeShipment
resolveRiskEvent
publishOntology
```

---

# 18. Expected backend handler names

The generated YAML should reference these function handlers:

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

The generated YAML should reference these action handlers:

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

The handler registry should fail application startup when the YAML references an unknown handler.

---

# 19. Validation schema requirements

Create a strict schema for `ontology.yaml` using the project's selected validation library.

Use:

- Zod for TypeScript/Node.js
- Pydantic for Python/FastAPI

The schema should validate:

```text
ontology metadata
unique object type keys
unique property keys per object
valid source mappings
valid property types
valid enum definitions
valid title properties
valid link endpoints
valid cardinalities
valid handler references
valid action targets
valid function input/output definitions
valid role references
valid permission references
valid state transitions
valid derived-property resolvers
valid derived-link resolvers
```

The validator should reject:

```text
unknown object types
unknown properties
unknown handlers
duplicate keys
invalid role names
actions assigned to nonexistent objects
links with nonexistent endpoints
state transitions with unknown states
derived properties without resolvers
write actions granted to AIAgent
```

---

# 20. Suggested file structure

```text
ontology/
├── ontology.yaml
├── schema.ts or schema.py
├── loader.ts or loader.py
├── registry.ts or registry.py
└── types.ts or models.py

src/
├── ontology/
│   ├── functions/
│   │   ├── findImpactedParts.ts
│   │   ├── findImpactedProducts.ts
│   │   ├── findImpactedOrders.ts
│   │   ├── calculateStockoutRisk.ts
│   │   ├── getInventoryAvailability.ts
│   │   ├── findAlternativeWarehouses.ts
│   │   ├── findExpeditablePurchaseOrders.ts
│   │   ├── rankImpactedOrders.ts
│   │   ├── recommendMitigationPlan.ts
│   │   └── validateMitigationPlan.ts
│   │
│   ├── actions/
│   │   ├── createRiskEvent.ts
│   │   ├── acknowledgeRiskEvent.ts
│   │   ├── generateMitigationPlan.ts
│   │   ├── submitMitigationPlan.ts
│   │   ├── approveMitigationPlan.ts
│   │   ├── rejectMitigationPlan.ts
│   │   ├── executeMitigationPlan.ts
│   │   ├── reallocateInventory.ts
│   │   ├── completeInventoryTransfer.ts
│   │   ├── expeditePurchaseOrder.ts
│   │   ├── prioritizeShipment.ts
│   │   └── resolveRiskEvent.ts
│   │
│   ├── permissions/
│   ├── audit/
│   ├── handlers/
│   └── runtime/
│
└── mcp/
    └── ontologyTools.ts
```

Adapt file extensions to the selected backend language.

---

# 21. Version 1 exclusions

Do not add these object types to Version 1:

```text
Customer
Carrier
ManufacturingPlant
ProductionOrder
Route
SupplierContract
AlternativePart
DemandForecast
QualityIncident
WeatherEvent
Port
TransportationLane
```

For Version 1:

- customer information remains on `CustomerOrder`
- carrier information remains on `Shipment`
- supplier delay is the primary risk type
- the Ontology Manager is read-only
- ontology definitions are YAML-based
- no database-backed ontology editor is required

---

# 22. Required output from the implementation agent

The implementation agent should produce:

```text
1. ontology/ontology.yaml
2. ontology schema validation file
3. ontology loader
4. ontology registry
5. handler-name registry or interface
6. clear startup validation errors
7. optional ontology type definitions
```

Do not implement all function and action business logic unless explicitly requested.

The main task is to create a complete and valid ontology definition that the runtime can consume.

---

# 23. Acceptance criteria

The generated ontology implementation is complete only when all conditions below are satisfied.

## Metadata

- All 16 object types are defined.
- All required stored properties are defined.
- All required derived properties are defined.
- All object types map to backing PostgreSQL tables.
- All object types define a primary key.
- All object types define a title property.
- All enums are explicitly defined.

## Links

- All stored link types are defined.
- All link endpoints reference valid object types.
- Cardinalities are declared.
- Flattened business links are represented.
- Derived risk-impact links reference functions.

## Functions

- All 10 functions are defined.
- Every function is marked read-only.
- Input and output schemas are defined.
- Every function references a stable handler name.
- Function permissions are defined.
- No function directly modifies operational data.

## Actions

- All 12 actions are defined.
- Every action declares a target object type.
- Every action declares parameters.
- Every action declares validation rules.
- Every action declares allowed roles.
- Every action requires auditing.
- Critical actions require a reason.
- Actions require an idempotency key.
- Transactional requirements are declared.
- State transitions are enforced.

## Permissions

- All five roles are defined.
- The permission matrix is encoded.
- AIAgent cannot execute critical actions.
- Planner cannot approve plans.
- OperationsManager and Admin can execute plans.
- Only Admin can publish ontology changes.

## Audit

- Action execution metadata requirements are declared.
- Before and after object snapshots are required.
- Actor identity and role are required.
- Action version is required.
- AI-generated plan evidence is auditable.

## Runtime

- The ontology YAML validates at startup.
- Invalid references fail with clear errors.
- Unknown handlers fail startup.
- The Ontology Manager can render metadata from the YAML.
- The MCP layer can derive its safe tool list from the YAML.

---

# 24. Final implementation principle

The implementation must preserve this separation:

```text
PostgreSQL
= operational data and execution history

ontology.yaml
= business-object, link, function, action, and permission definitions

backend handlers
= executable business logic

ontology runtime
= loading, querying, authorization, action dispatch, and auditing

Ontology Manager
= read-only visualization of the ontology definition

MCP layer
= safe AI access to approved ontology functions and draft actions
```

The system should demonstrate that data is not only stored in tables. It is represented as connected business objects with governed logic, permissions, actions, and auditability.
