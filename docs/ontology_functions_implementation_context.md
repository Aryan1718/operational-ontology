# Ontology Functions Implementation Context

> **Short description:** This file defines how the Version 1 read-only ontology functions must be implemented for the supply-chain disruption workflow. It gives Codex the business rules, inputs, outputs, calculations, traversal logic, configuration, edge cases, testing requirements, and strict boundary between functions and governed actions.

---

## 1. Purpose

Use this document when implementing the backend handlers for the ontology functions declared in `ontology/ontology.yaml`.

The ontology metadata already defines the names and public contracts of the functions. This file defines the executable behavior behind those stable handler names.

The required Version 1 functions are:

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

This document is intentionally focused on function implementation. It must not become a database redesign, ontology editor specification, action-engine specification, or frontend specification.

---

## 2. Read this with the existing project context

Before implementing these handlers, read:

```text
AGENT.md or agent.md
supplygraph_database_context.md
SupplyGraph_Ontology_Implementation_Context.md
```

Use the repository's actual filenames and paths when capitalization differs.

Source-of-truth responsibilities:

```text
PostgreSQL
= actual operational records

ontology/ontology.yaml
= ontology metadata and function contracts

this document
= Version 1 function behavior and calculations

backend function handlers
= executable read-only logic

governed actions
= all operational writes
```

When this document and the existing ontology metadata describe the same function, preserve the stable function key, handler name, permission metadata, and public input contract from `ontology.yaml`. Extend the output DTO with explainability fields only when doing so does not break the existing schema. If the public schema must change, update the ontology metadata and its validation tests in the same change.

---

## 3. Core function boundary

An ontology function may:

- read operational records;
- traverse ontology relationships;
- calculate derived values;
- simulate projected inventory and demand;
- rank records;
- validate current feasibility;
- recommend possible actions;
- return structured evidence and explanations.

An ontology function must never:

- insert, update, or delete operational records;
- reserve or move inventory;
- change a purchase order;
- change shipment priority;
- create a `MitigationPlan` or `MitigationStep`;
- submit, approve, reject, execute, or resolve anything;
- silently call a write action;
- use an LLM as the source of numeric or operational truth.

Canonical distinction:

```text
recommendMitigationPlan
= returns a recommendation

generateMitigationPlan action
= persists a draft plan and steps
```

```text
validateMitigationPlan
= reports whether a plan is currently feasible

submit/approve/execute actions
= decide whether to proceed and persist state changes
```

---

## 4. Function groups and dependency flow

### 4.1 Impact traversal

```text
findImpactedParts
findImpactedProducts
findImpactedOrders
```

### 4.2 Inventory and supply analysis

```text
calculateStockoutRisk
getInventoryAvailability
findAlternativeWarehouses
findExpeditablePurchaseOrders
```

### 4.3 Prioritization and recommendation

```text
rankImpactedOrders
recommendMitigationPlan
```

### 4.4 Governance validation

```text
validateMitigationPlan
```

Expected dependency flow:

```text
findImpactedParts
        ↓
findImpactedProducts
        ↓
findImpactedOrders
        ↓
rankImpactedOrders
        ↓
recommendMitigationPlan
        ↓
generateMitigationPlan action
        ↓
validateMitigationPlan
        ↓
submit / approve / execute actions
```

Do not duplicate the same impact calculation in several handlers. Extract shared domain services or pure calculation helpers and reuse them.

---

## 5. Common execution requirements

### 5.1 Runtime context

Every function handler should receive a runtime context equivalent to:

```ts
interface FunctionExecutionContext {
  actorId: string;
  actorRoles: string[];
  requestId: string;
  executedAt: Date;
  ontologyVersion: string;
}
```

Use `executedAt` as the calculation clock. Do not call the system clock repeatedly inside domain calculations.

### 5.2 Authorization

The ontology runtime must authorize function execution using the loaded metadata from `ontology.yaml`.

Do not duplicate role lists inside each handler unless the repository already requires a defense-in-depth check. The YAML/registry remains the permission source of truth.

### 5.3 Consistent reads

A multi-query function must use one consistent PostgreSQL read snapshot when the database layer supports it.

This is especially important for:

```text
findImpactedOrders
recommendMitigationPlan
validateMitigationPlan
```

The function must not read inventory before a concurrent change and purchase orders after that change as though both belonged to one operational snapshot.

### 5.4 Deterministic output

The same inputs, configuration, `executedAt`, and database snapshot must produce the same output.

Always define deterministic tie-breakers. Use stable object IDs as the final tie-breaker.

### 5.5 Typed DTOs

Do not return raw ORM records or database rows.

Return explicit DTOs containing:

- stable ontology object IDs;
- user-facing identifying fields when useful;
- calculated values;
- evidence used by the calculation;
- warnings and assumptions;
- deterministic explanations.

### 5.6 Explainability

Important scores must return their component values.

Example:

```json
{
  "riskScore": 73,
  "riskLevel": "high",
  "scoreBreakdown": {
    "shortageSeverity": {
      "rawScore": 60,
      "weight": 0.5,
      "weightedScore": 30
    },
    "stockoutUrgency": {
      "rawScore": 80,
      "weight": 0.25,
      "weightedScore": 20
    },
    "safetyStockBreach": {
      "rawScore": 100,
      "weight": 0.15,
      "weightedScore": 15
    },
    "partCriticality": {
      "rawScore": 75,
      "weight": 0.1,
      "weightedScore": 7.5
    }
  }
}
```

Do not return only a score without enough evidence to explain it.

### 5.7 Numeric rules

- Quantities must never be represented as negative available stock in public quantity fields unless the field is explicitly named `projectedEndingQuantity` or `netPosition`.
- Use `max(0, value)` for shortage and transferable quantities.
- Avoid binary floating-point errors for currency. Use the repository's decimal or money type.
- Round final scores to the nearest integer.
- Preserve unrounded component values internally and in tests when needed.
- Dates must be interpreted in the application's configured operational timezone or as date-only values, not through accidental local-machine conversion.

### 5.8 Empty results are valid

An empty list is not an error when no objects are impacted or no mitigation option is feasible.

Return:

```json
{
  "items": [],
  "warnings": [],
  "summary": {
    "count": 0
  }
}
```

or the repository's equivalent envelope.

### 5.9 Function telemetry

The runtime may record technical telemetry such as:

- function name;
- request ID;
- actor ID;
- duration;
- result count;
- success or failure;
- ontology version.

Telemetry is not a business mutation. Do not create action audit records that imply operational state changed.

---

## 6. Version 1 business assumptions

These assumptions are required because the Version 1 data model intentionally excludes several advanced supply-chain entities.

### 6.1 Supported disruption

Version 1 function logic primarily supports:

```text
riskType = supplier_delay
```

Return a structured unsupported-risk error for unknown risk types. Do not silently apply supplier-delay logic to another disruption type.

### 6.2 Supplier delay affects open purchase orders

A supplier-delay `RiskEvent` shifts the expected delivery date of every open purchase order from that supplier by `delayDays` for simulation purposes.

```text
projectedExpectedDeliveryDate
= currentExpectedDeliveryDate + riskEvent.delayDays
```

Open purchase-order statuses:

```text
submitted
confirmed
partially_received
delayed
```

Excluded statuses:

```text
draft
received
cancelled
```

Open quantity:

```text
openQuantity
= max(0, quantityOrdered - quantityReceived)
```

Already received quantity is not affected by the delay.

### 6.3 Definition of impacted

A connected object is not automatically operationally impacted.

A part is impacted only when the risk event creates a new projected shortage or makes an existing projected shortage worse inside the evaluation horizon.

```text
isImpacted
= delayedScenarioShortage > baselineScenarioShortage
```

A product is impacted when an impacted part limits the quantity of that product that can be built or fulfilled.

A customer order is impacted when the delayed scenario reduces the quantity that can be fulfilled by its required delivery date or increases its projected delay.

### 6.4 Demand source

Version 1 demand comes from unfulfilled customer order lines.

```text
remainingProductDemand
= max(0, orderLine.quantity - orderLine.fulfilledQuantity)
```

Convert product demand into part demand using `ProductPartRequirement`:

```text
requiredPartQuantity
= remainingProductDemand × quantityRequired
```

Cancelled and fully fulfilled orders must not contribute demand.

### 6.5 Allocation policy

When simulated supply must be allocated across competing orders, use:

```text
priority descending
requiredDeliveryDate ascending
orderDate ascending
orderId ascending
```

Priority order:

```text
critical
high
normal
low
```

The final `orderId` comparison guarantees deterministic allocation.

### 6.6 Evaluation horizon

Use the explicit function horizon when provided.

For a `RiskEvent`-based function without an explicit horizon:

1. inspect relevant open customer orders;
2. use the latest relevant `requiredDeliveryDate`;
3. cap the evaluation to `executedAt + impactAnalysisHorizonDays`;
4. use the configured default horizon when no relevant order date exists.

Recommended Version 1 default:

```text
impactAnalysisHorizonDays = 30
```

Keep this value configurable.

### 6.7 Missing transportation-lane data

Version 1 has no `TransportationLane`, carrier-rate, warehouse-distance, or transit-calendar object.

`findAlternativeWarehouses` must use a named, injectable transfer estimator. The default estimator may use warehouse region and country only.

Recommended demo defaults:

```text
same region:   1 transfer day
same country:  2 transfer days
cross-country: 5 transfer days
```

Do not hide this assumption. Include the estimator name and assumptions in the result.

### 6.8 Missing supplier expedite terms

Version 1 has no supplier-contract or expedite-capability table.

`findExpeditablePurchaseOrders` must use named configuration rather than invented supplier-specific facts.

Recommended defaults:

```text
defaultExpediteLeadTimeReductionPercent = 0.40
defaultExpeditePremiumPercent = 0.15
minimumExpediteLeadTimeDays = 1
```

The result must expose that these are configured estimates.

### 6.9 AI boundary

An AI agent may call approved read-only functions and explain their results.

An AI model must not calculate inventory truth, risk scores, rankings, or action feasibility independently of these deterministic handlers.

---

## 7. Shared configuration

Define a typed configuration object equivalent to:

```ts
interface OntologyFunctionConfig {
  impactAnalysisHorizonDays: number;

  stockoutRiskWeights: {
    shortageSeverity: number;
    stockoutUrgency: number;
    safetyStockBreach: number;
    partCriticality: number;
  };

  orderRankingWeights: {
    orderPriority: number;
    deliveryUrgency: number;
    shortageRatio: number;
    projectedDelay: number;
    orderValue: number;
    partCriticality: number;
  };

  maximumProjectedDelayScoreDays: number;
  transferEstimator: {
    sameRegionDays: number;
    sameCountryDays: number;
    crossCountryDays: number;
    baseCost: Decimal;
    costPerUnitPerDay: Decimal;
  };

  expediteEstimator: {
    leadTimeReductionPercent: number;
    premiumPercent: number;
    minimumLeadTimeDays: number;
  };

  validationCostTolerancePercent: number;
  validationStaleAfterMinutes: number;
}
```

Validate at startup:

- every weight is between 0 and 1;
- each scoring weight group sums to 1;
- day values are non-negative;
- percentages are valid;
- currency values are non-negative.

Recommended Version 1 values:

```text
stockout risk
shortageSeverity   = 0.50
stockoutUrgency    = 0.25
safetyStockBreach  = 0.15
partCriticality    = 0.10

order ranking
orderPriority      = 0.25
deliveryUrgency    = 0.20
shortageRatio      = 0.20
projectedDelay     = 0.15
orderValue         = 0.10
partCriticality    = 0.10

maximumProjectedDelayScoreDays = 10
validationCostTolerancePercent = 5
validationStaleAfterMinutes = 15
```

Do not scatter these numbers across handlers.

---

## 8. Shared domain services

Prefer reusable services or pure helpers equivalent to:

```text
RiskEventReader
SupplyProjectionService
DemandProjectionService
InventoryLedgerService
BillOfMaterialsService
OrderAllocationService
StockoutRiskCalculator
OrderRankingCalculator
TransferEstimator
ExpediteEstimator
RecommendationPolicy
MitigationPlanValidator
```

Expected responsibility examples:

```text
SupplyProjectionService
= baseline and delayed inbound quantities by part, warehouse, and date

DemandProjectionService
= part demand derived from order lines and product requirements

InventoryLedgerService
= dated starting balance, inbound movements, and outbound movements

OrderAllocationService
= deterministic allocation of available supply across orders
```

Handlers should orchestrate these services and map results into ontology DTOs. Avoid putting all SQL, calculations, and DTO mapping into one large function file.

---

# 9. Function specification: `findImpactedParts`

## 9.1 Purpose

Find parts whose projected shortage is created or increased by a supplier-delay risk event.

The function must answer:

> Because this supplier is delayed, which parts will have less usable supply when they are needed?

It must not merely list every part linked to the supplier.

## 9.2 Input

```text
riskEventId: string
```

## 9.3 Required reads

```text
risk_events
suppliers
supplier_parts
parts
purchase_orders
purchase_order_lines
inventory_positions
customer_orders
order_lines
product_part_requirements
```

Include active incoming inventory transfers when the existing database context supports them.

## 9.4 Traversal

```text
RiskEvent
→ Supplier
→ SupplierPart
→ Part
→ PurchaseOrderLine / InventoryPosition / ProductPartRequirement
→ OrderLine
→ CustomerOrder
```

## 9.5 Algorithm

1. Load the `RiskEvent`.
2. Fail with `RISK_EVENT_NOT_FOUND` when it does not exist.
3. Validate `riskType = supplier_delay`.
4. Load the affected supplier and require it to exist.
5. Load active `SupplierPart` relationships for that supplier.
6. Load open purchase-order lines from that supplier for those parts.
7. Build two dated supply projections per part and destination warehouse:
   - baseline using current expected dates;
   - delayed using expected dates plus `delayDays`.
8. Load starting available inventory:

   ```text
   availableQuantity = max(0, onHandQuantity - reservedQuantity)
   ```

9. Derive time-phased part demand from unfulfilled customer orders and the BOM.
10. Calculate baseline and delayed shortages inside the evaluation horizon.
11. Return a part only when:

   ```text
   delayedShortageQuantity > baselineShortageQuantity
   ```

12. Sort results by:
   - shortage increase descending;
   - earliest shortage date ascending;
   - part ID ascending.

## 9.6 Recommended output

```ts
interface ImpactedPartResult {
  partId: string;
  partName: string;
  supplierPartId: string;
  delayDays: number;
  delayedPurchaseOrderIds: string[];
  delayedInboundQuantity: number;
  baselineAvailableByHorizon: number;
  delayedAvailableByHorizon: number;
  projectedDemandQuantity: number;
  baselineShortageQuantity: number;
  delayedShortageQuantity: number;
  shortageIncreaseQuantity: number;
  firstBaselineShortageDate: string | null;
  firstDelayedShortageDate: string | null;
  alternativeSupplierCount: number;
  impactReason: string;
  evidence: {
    purchaseOrderLineIds: string[];
    demandOrderIds: string[];
    horizonDate: string;
  };
}
```

Preserve existing public output fields such as:

```text
partId
supplierPartId
delayDays
openPurchaseOrderQuantity
impactReason
```

when already defined in `ontology.yaml`.

## 9.7 Example

```text
Current inventory: 10
Demand before July 20: 50
Incoming from delayed supplier: 50
Original arrival: July 18
Projected arrival after delay: July 23

Baseline shortage: 0
Delayed shortage: 40
Shortage increase: 40

Result: impacted
```

A part with 100 current units and demand of 20 is not impacted even when linked to the delayed supplier.

## 9.8 Edge cases

- Ignore inactive `SupplierPart` relationships.
- Do not delay already received quantities.
- A part with no demand inside the horizon is not currently impacted.
- A part already short before the event is impacted only when the delayed scenario makes the shortage worse.
- Another on-time supplier or purchase order may fully remove the impact.
- Return warnings for incomplete BOM or destination data rather than inventing values.

## 9.9 Minimum tests

- connected part with enough inventory is excluded;
- delay creates a new shortage;
- delay worsens an existing shortage;
- no demand means no impact;
- another supplier covers demand;
- partially received PO delays only open quantity;
- inactive supplier-part link is ignored;
- deterministic result ordering.

---

# 10. Function specification: `findImpactedProducts`

## 10.1 Purpose

Find products whose buildable or fulfillable quantity is reduced by the impacted parts from a risk event.

## 10.2 Input

```text
riskEventId: string
```

## 10.3 Dependencies

Reuse `findImpactedParts` or the same shared impact-analysis service. Do not implement a separate definition of impacted parts.

## 10.4 Traversal

```text
RiskEvent
→ impacted Part
→ ProductPartRequirement
→ Product
```

## 10.5 Core calculations

For one product requirement:

```text
buildableQuantityFromPart
= floor(projectedAvailablePartQuantity / quantityRequired)
```

For a product with several required parts:

```text
maximumBuildableQuantity
= minimum buildableQuantityFromPart across all required active parts
```

Calculate baseline and delayed maximum buildable quantities.

A product is impacted when:

```text
delayedMaximumBuildableQuantity < baselineMaximumBuildableQuantity
```

or when the delayed buildable quantity is below open product demand and the delay increases the product shortfall.

## 10.6 Algorithm

1. Resolve impacted parts for the risk event.
2. Find active products using those parts through `ProductPartRequirement`.
3. Ignore inactive or discontinued products.
4. Load all active BOM requirements for each candidate product, not only the impacted requirement.
5. Calculate baseline and delayed buildable quantities using the limiting part.
6. Calculate unfulfilled product demand from open order lines.
7. Calculate baseline and delayed production shortfalls.
8. Return only products whose delayed scenario is worse.
9. Sort by:
   - production shortfall increase descending;
   - highest part criticality descending;
   - product ID ascending.

## 10.7 Recommended output

```ts
interface ImpactedProductResult {
  productId: string;
  productName: string;
  impactedPartIds: string[];
  requiredQuantities: Array<{
    partId: string;
    quantityRequiredPerProduct: number;
  }>;
  limitingPartId: string;
  baselineMaximumBuildableQuantity: number;
  delayedMaximumBuildableQuantity: number;
  openOrderQuantity: number;
  baselineProductionShortfallQuantity: number;
  delayedProductionShortfallQuantity: number;
  shortfallIncreaseQuantity: number;
  highestPartCriticality: "low" | "medium" | "high" | "critical";
  productRiskLevel: "none" | "low" | "medium" | "high" | "critical";
  impactReason: string;
}
```

## 10.8 Important rules

- A product must be evaluated using its complete BOM.
- `substitutionAllowed = true` does not automatically mean a substitute exists. Version 1 has no `AlternativePart` object.
- Mention substitution eligibility as a warning or future option, but do not invent substitute inventory.
- When a BOM is incomplete, return a warning and do not overstate confidence.

## 10.9 Minimum tests

- one impacted part limits a product;
- non-limiting impacted part does not reduce buildable quantity;
- product with several parts uses the minimum buildable quantity;
- inactive product is excluded;
- product with no open demand may still show reduced buildability but should have zero order shortfall;
- deterministic limiting-part tie-breaker.

---

# 11. Function specification: `findImpactedOrders`

## 11.1 Purpose

Find customer orders that cannot be fulfilled by their required delivery date because the risk event reduces available parts or product capacity.

## 11.2 Input

```text
riskEventId: string
```

## 11.3 Dependencies

Use the same baseline/delayed supply projection and BOM services as the previous functions.

## 11.4 Traversal

```text
RiskEvent
→ impacted Parts
→ ProductPartRequirement
→ Product
→ OrderLine
→ CustomerOrder
```

## 11.5 Candidate orders

Include orders whose status is operationally open, such as:

```text
confirmed
allocated
partially_fulfilled
delayed
```

Exclude:

```text
draft
fulfilled
cancelled
```

Use the exact status model implemented by the database and ontology.

## 11.6 Allocation simulation

The function must run two deterministic simulations:

```text
baseline scenario
= current supplier delivery dates

delayed scenario
= affected supplier delivery dates shifted by delayDays
```

For each scenario:

1. Build available part balances by warehouse and date.
2. Convert each remaining order-line quantity into required parts through the BOM.
3. Sort orders by the allocation policy:

   ```text
   priority descending
   requiredDeliveryDate ascending
   orderDate ascending
   orderId ascending
   ```

4. Allocate required parts to orders up to the required delivery date.
5. Calculate the fulfillable product quantity for every order line.
6. Record unresolved product and part shortages.
7. Estimate the earliest date on which missing supply becomes available.
8. Calculate projected delay days.

An order is impacted when the delayed scenario has one or more of:

```text
lower fulfillable quantity
higher shortage quantity
later projected fulfillment date
higher projected delay days
```

than the baseline scenario.

## 11.7 Order quantities

For each order line:

```text
remainingQuantity
= max(0, quantity - fulfilledQuantity)
```

Order value at risk:

```text
estimatedOrderValue
= sum(remainingQuantity × unitPrice)
```

Shortage ratio:

```text
shortageRatio
= shortageQuantity / requiredQuantity
```

Return `0` when required quantity is `0`.

## 11.8 Recommended output

```ts
interface ImpactedOrderResult {
  orderId: string;
  orderNumber: string;
  priority: "low" | "normal" | "high" | "critical";
  requiredDeliveryDate: string;
  destinationWarehouseId: string | null;
  impactedProducts: Array<{
    productId: string;
    requiredQuantity: number;
    baselineFulfillableQuantity: number;
    delayedFulfillableQuantity: number;
    shortageQuantity: number;
  }>;
  impactedPartIds: string[];
  requiredQuantity: number;
  baselineFulfillableQuantity: number;
  delayedFulfillableQuantity: number;
  shortageQuantity: number;
  shortageRatio: number;
  baselineProjectedDelayDays: number;
  projectedDelayDays: number;
  estimatedOrderValue: Decimal;
  riskScore: number;
  impactReason: string;
  warnings: string[];
}
```

## 11.9 Destination warehouse rule

When `destinationWarehouseId` is present, evaluate supply for that warehouse.

When it is absent:

- do not silently select a warehouse;
- evaluate network availability only as informational evidence;
- add `DESTINATION_WAREHOUSE_UNASSIGNED` warning;
- lower recommendation confidence;
- do not mark a specific transfer as feasible until a destination exists.

## 11.10 Minimum tests

- delayed supply reduces fulfillment before due date;
- order fully covered by current inventory is excluded;
- critical order receives supply before normal order during allocation;
- earlier due order wins a tie within the same priority;
- fulfilled and cancelled orders are excluded;
- missing destination produces a warning;
- baseline shortage unchanged by delay is not classified as event impact;
- multi-line order aggregates product and value results correctly.

---

# 12. Function specification: `calculateStockoutRisk`

## 12.1 Purpose

Calculate the projected inventory risk for one part at one warehouse through a horizon date.

The function answers:

> Will this warehouse fall below safety stock or run out of this part, how soon, and how serious is the shortage?

## 12.2 Input

```text
partId: string
warehouseId: string
horizonDate: date
```

## 12.3 Inventory ledger

Create a dated projection ledger.

Starting balance:

```text
startingAvailableQuantity
= max(0, onHandQuantity - reservedQuantity)
```

Positive movements:

- open purchase-order quantities arriving at this warehouse by date;
- incoming inventory transfers expected by date when available.

Negative movements:

- part demand derived from unfulfilled customer orders for this warehouse;
- outgoing approved or in-transit inventory transfers when available.

Apply movements in chronological order. When multiple movements occur on one date, apply inbound and outbound ordering consistently and document the convention. Recommended convention:

```text
beginning-of-day inbound
then due-date demand/outbound
```

## 12.4 Core outputs

```text
currentAvailableQuantity
projectedInboundQuantity
projectedDemandQuantity
projectedEndingQuantity
safetyStockQuantity
shortageQuantity
safetyStockBreachDate
stockoutDate
daysUntilStockout
riskScore
riskLevel
```

Definitions:

```text
projectedEndingQuantity
= startingAvailable + eligibleInbound - projectedDemand - outgoingTransfers

shortageQuantity
= max(0, -projectedEndingQuantity)
```

`stockoutDate` is the first date the running projected balance reaches `0` or below.

`safetyStockBreachDate` is the first date the running balance falls below `safetyStockQuantity`.

## 12.5 Stockout-risk score

Final score:

```text
riskScore
= shortageSeverityScore × 0.50
+ stockoutUrgencyScore × 0.25
+ safetyStockBreachScore × 0.15
+ partCriticalityScore × 0.10
```

Round to the nearest integer and clamp to `0..100`.

### 12.5.1 Shortage severity

```text
shortageSeverityScore
= clamp((shortageQuantity / projectedDemandQuantity) × 100, 0, 100)
```

When projected demand is `0`, this component is `0`.

### 12.5.2 Stockout urgency

```text
already out / stockout today = 100
1–3 days                    = 80
4–7 days                    = 60
8–14 days                   = 40
15–30 days                  = 20
more than 30 days           = 0
no projected stockout       = 0
```

### 12.5.3 Safety-stock breach

When projected ending quantity is at or above safety stock:

```text
safetyStockBreachScore = 0
```

Otherwise:

```text
safetyStockBreachScore
= clamp(((safetyStockQuantity - projectedEndingQuantity)
         / safetyStockQuantity) × 100, 0, 100)
```

When safety stock is `0`, this component is `0`.

### 12.5.4 Part criticality

Map the highest active `ProductPartRequirement.criticality`:

```text
low      = 25
medium   = 50
high     = 75
critical = 100
```

When no active product requirement exists, use `0` and add a warning.

### 12.5.5 No-risk override

Criticality alone must not create inventory risk.

When both conditions are true:

```text
shortageQuantity = 0
projectedEndingQuantity >= safetyStockQuantity
```

force:

```text
riskScore = 0
riskLevel = none
```

## 12.6 Risk levels

```text
0       = none
1–24    = low
25–49   = medium
50–74   = high
75–100  = critical
```

## 12.7 Recommended output

```ts
interface StockoutRiskResult {
  partId: string;
  warehouseId: string;
  horizonDate: string;
  currentAvailableQuantity: number;
  projectedInboundQuantity: number;
  projectedDemandQuantity: number;
  projectedEndingQuantity: number;
  safetyStockQuantity: number;
  shortageQuantity: number;
  safetyStockBreachDate: string | null;
  stockoutDate: string | null;
  daysUntilStockout: number | null;
  riskScore: number;
  riskLevel: "none" | "low" | "medium" | "high" | "critical";
  scoreBreakdown: Record<string, {
    rawScore: number;
    weight: number;
    weightedScore: number;
  }>;
  ledger: Array<{
    date: string;
    movementType: string;
    quantity: number;
    runningBalance: number;
    sourceObjectType: string;
    sourceObjectId: string;
  }>;
  warnings: string[];
}
```

## 12.8 Worked example

```text
Demand: 100
Available by horizon: 40
Shortage: 60
Stockout in: 3 days
Safety-stock breach score: 100
Part criticality: high = 75

Shortage:   60 × 0.50 = 30
Urgency:    80 × 0.25 = 20
Safety:    100 × 0.15 = 15
Critical:   75 × 0.10 = 7.5

Final = 72.5 → 73 → high
```

## 12.9 Minimum tests

- no demand and healthy inventory returns zero risk;
- shortage severity formula;
- every urgency bucket boundary;
- safety stock of zero avoids division by zero;
- score is capped at 100;
- critical part with enough stock returns zero;
- first breach and stockout dates are correct;
- ledger ordering is deterministic.

---

# 13. Function specification: `getInventoryAvailability`

## 13.1 Purpose

Return current and projected inventory availability for a part at one warehouse or across all warehouses.

## 13.2 Input

```text
partId: string
warehouseId: optional string
requiredByDate: optional date
```

## 13.3 Core calculations

```text
availableQuantity
= max(0, onHandQuantity - reservedQuantity)
```

```text
eligibleInboundQuantity
= open inbound quantity expected on or before requiredByDate
```

```text
projectedAvailableByRequiredDate
= availableQuantity
+ eligibleInboundQuantity
+ eligibleIncomingTransferQuantity
- committedOutgoingTransferQuantity
```

```text
surplusAboveSafetyStock
= max(0, projectedAvailableByRequiredDate - safetyStockQuantity)
```

When `requiredByDate` is absent, return current availability and separate `inTransitQuantity`; do not assume every in-transit unit is immediately usable.

## 13.4 Recommended output

```ts
interface InventoryAvailabilityResult {
  warehouseId: string;
  warehouseName: string;
  partId: string;
  onHandQuantity: number;
  reservedQuantity: number;
  availableQuantity: number;
  inTransitQuantity: number;
  eligibleInboundQuantity: number;
  eligibleIncomingTransferQuantity: number;
  committedOutgoingTransferQuantity: number;
  projectedAvailableByRequiredDate: number;
  safetyStockQuantity: number;
  surplusAboveSafetyStock: number;
  inventoryUpdatedAt: string;
  requiredByDate: string | null;
  warnings: string[];
}
```

## 13.5 Sorting

When returning several warehouses, sort by:

1. projected available quantity descending;
2. inventory freshness descending;
3. warehouse ID ascending.

## 13.6 Important rules

- Do not count delayed inbound inventory as eligible when it arrives after `requiredByDate`.
- Do not double-count `InventoryPosition.inTransitQuantity` and explicit purchase-order or transfer records when they represent the same movement. Choose one authoritative projection path based on the implemented schema.
- Include inventory freshness so users can judge stale records.
- Inactive warehouses may be returned for audit visibility only when explicitly requested; exclude them from operational availability by default.

## 13.7 Minimum tests

- current availability calculation;
- warehouse filter;
- eligible inbound date boundary;
- safety-stock surplus;
- inactive warehouse exclusion;
- no double-counting of transit quantities;
- deterministic sorting.

---

# 14. Function specification: `findAlternativeWarehouses`

## 14.1 Purpose

Find source warehouses that can transfer a part to a destination without violating source safety stock.

## 14.2 Input

```text
partId: string
destinationWarehouseId: string
requiredQuantity: number
requiredByDate: date
```

## 14.3 Transferable quantity

```text
sourceAvailableQuantity
= max(0, onHandQuantity - reservedQuantity)
```

```text
transferableQuantity
= max(
    0,
    sourceAvailableQuantity
    + eligibleSourceInboundBeforeTransfer
    - safetyStockQuantity
    - committedOutgoingTransferQuantity
  )
```

Do not rely on future inbound supply unless it is expected early enough to preserve source safety stock before the proposed transfer ships.

## 14.4 Feasibility

A candidate is feasible only when all are true:

```text
source warehouse is active
source warehouse != destination warehouse
transferableQuantity > 0
estimated arrival <= requiredByDate
source remains at or above safety stock
```

A candidate may partially cover the requested quantity. Report:

```text
coveredQuantity = min(requiredQuantity, transferableQuantity)
remainingShortage = max(0, requiredQuantity - coveredQuantity)
```

## 14.5 Transfer estimate

Use the configured `TransferEstimator`.

Default days:

```text
same region   = 1
same country  = 2
cross-country = 5
```

Suggested demo cost formula:

```text
estimatedTransferCost
= baseCost
+ coveredQuantity × costPerUnitPerDay × estimatedTransferDays
```

Use decimal arithmetic.

## 14.6 Recommended output

```ts
interface AlternativeWarehouseResult {
  warehouseId: string;
  warehouseName: string;
  availableQuantity: number;
  safetyStockQuantity: number;
  committedOutgoingTransferQuantity: number;
  transferableQuantity: number;
  coveredQuantity: number;
  remainingShortage: number;
  estimatedTransferDays: number;
  estimatedArrivalDate: string;
  estimatedTransferCost: Decimal;
  feasible: boolean;
  infeasibilityReasons: string[];
  estimator: {
    name: string;
    assumptions: string[];
  };
}
```

## 14.7 Ranking

Rank feasible candidates first using:

1. can fully cover the request;
2. estimated arrival date ascending;
3. estimated transfer cost ascending;
4. transferable quantity descending;
5. warehouse ID ascending.

Return infeasible candidates after feasible candidates only when the caller requests diagnostic detail; otherwise return feasible candidates only.

## 14.8 Minimum tests

- source safety stock is preserved;
- destination warehouse is excluded;
- partial coverage is reported;
- late transfer is infeasible;
- inactive source is excluded;
- same-region estimate is faster than cross-country;
- committed transfer reduces transferable quantity;
- deterministic ranking.

---

# 15. Function specification: `findExpeditablePurchaseOrders`

## 15.1 Purpose

Find open purchase orders containing a part that could be expedited early enough to reduce a projected shortage.

## 15.2 Input

```text
partId: string
supplierId: optional string
requiredByDate: date
```

## 15.3 Eligible purchase orders

Eligible statuses:

```text
submitted
confirmed
partially_received
delayed
```

Exclude:

```text
draft
received
cancelled
```

Require:

```text
openQuantity > 0
```

When `expedited = true`, treat the current expected date and cost as the current state. Do not repeatedly apply the default premium as though it had never been expedited.

## 15.4 Estimate

For a non-expedited order:

```text
remainingLeadTimeDays
= max(0, currentExpectedDate - executedAtDate)
```

```text
reducedDays
= floor(remainingLeadTimeDays × leadTimeReductionPercent)
```

```text
expeditedLeadTimeDays
= max(minimumLeadTimeDays, remainingLeadTimeDays - reducedDays)
```

```text
possibleExpeditedDate
= executedAtDate + expeditedLeadTimeDays
```

Suggested additional cost:

```text
remainingLineValue
= openQuantity × unitCost

additionalCost
= remainingLineValue × premiumPercent
```

Aggregate multiple lines for the same part and purchase order when necessary.

## 15.5 Feasibility

```text
feasible
= possibleExpeditedDate <= requiredByDate
  and openQuantity > 0
  and status is eligible
```

The result is an estimate, not a supplier commitment. Include that assumption.

## 15.6 Recommended output

```ts
interface ExpeditablePurchaseOrderResult {
  purchaseOrderId: string;
  purchaseOrderNumber: string;
  supplierId: string;
  destinationWarehouseId: string;
  openQuantity: number;
  currentExpectedDate: string;
  possibleExpeditedDate: string;
  daysSaved: number;
  currentRemainingValue: Decimal;
  additionalCost: Decimal;
  feasible: boolean;
  infeasibilityReasons: string[];
  estimator: {
    name: string;
    leadTimeReductionPercent: number;
    premiumPercent: number;
    assumptions: string[];
  };
}
```

## 15.7 Ranking

Rank feasible candidates by:

1. possible expedited date ascending;
2. open quantity descending;
3. additional cost ascending;
4. purchase-order ID ascending.

## 15.8 Minimum tests

- open quantity calculation after partial receipt;
- ineligible statuses excluded;
- supplier filter;
- date and cost estimate;
- already expedited order is not double-premiumed;
- candidate arriving after required date is infeasible;
- decimal currency arithmetic;
- deterministic ranking.

---

# 16. Function specification: `rankImpactedOrders`

## 16.1 Purpose

Rank impacted customer orders so planners can address the most serious operational consequences first.

## 16.2 Input

```text
riskEventId: string
```

When the existing ontology contract supports optional filters, preserve them. Do not invent mandatory new inputs.

## 16.3 Dependency

Reuse `findImpactedOrders` or its shared analysis result. Do not recalculate order impact differently.

## 16.4 Final score

```text
orderRiskScore
= orderPriorityScore × 0.25
+ deliveryUrgencyScore × 0.20
+ shortageRatioScore × 0.20
+ projectedDelayScore × 0.15
+ orderValueScore × 0.10
+ partCriticalityScore × 0.10
```

Round and clamp to `0..100`.

### 16.4.1 Order priority

```text
low      = 25
normal   = 50
high     = 75
critical = 100
```

### 16.4.2 Delivery urgency

Based on `requiredDeliveryDate - executedAtDate`:

```text
overdue or due today = 100
1–2 days             = 90
3–5 days             = 75
6–10 days            = 50
11–20 days           = 25
more than 20 days    = 10
```

### 16.4.3 Shortage ratio

```text
shortageRatioScore
= clamp((shortageQuantity / requiredQuantity) × 100, 0, 100)
```

When required quantity is `0`, use `0`.

### 16.4.4 Projected delay

```text
projectedDelayScore
= clamp(
    (projectedDelayDays / maximumProjectedDelayScoreDays) × 100,
    0,
    100
  )
```

Default maximum score threshold:

```text
10 days
```

### 16.4.5 Order value

Recommended Version 1 buckets:

```text
less than $5,000       = 20
$5,000–$19,999         = 40
$20,000–$49,999        = 60
$50,000–$99,999        = 80
$100,000 or more       = 100
```

Make currency thresholds configurable when possible.

### 16.4.6 Part criticality

Use the highest criticality among parts preventing fulfillment:

```text
low      = 25
medium   = 50
high     = 75
critical = 100
```

## 16.5 Tie-breakers

When final scores are equal:

```text
1. earlier requiredDeliveryDate
2. larger shortageQuantity
3. higher estimatedOrderValue
4. earlier orderDate
5. orderId ascending
```

## 16.6 Recommended output

```ts
interface RankedImpactedOrderResult {
  rank: number;
  orderId: string;
  orderNumber: string;
  riskScore: number;
  scoreBreakdown: Record<string, {
    rawScore: number;
    weight: number;
    weightedScore: number;
  }>;
  shortageQuantity: number;
  shortageRatio: number;
  projectedDelayDays: number;
  estimatedOrderValue: Decimal;
  highestPartCriticality: "low" | "medium" | "high" | "critical";
  recommendedAttention: "monitor" | "review" | "urgent" | "immediate";
  rankingExplanation: string;
}
```

Suggested attention labels:

```text
0–24   monitor
25–49  review
50–74  urgent
75–100 immediate
```

## 16.7 Worked example

```text
Priority: normal = 50
Due in 1 day = 90
Shortage ratio = 90
Projected delay = 7 days = 70
Order value = $80,000 = 80
Missing part criticality = critical = 100

50 × .25  = 12.5
90 × .20  = 18
90 × .20  = 18
70 × .15  = 10.5
80 × .10  = 8
100 × .10 = 10

Final = 77
```

## 16.8 Minimum tests

- every factor mapping;
- exact bucket boundaries;
- weights sum correctly;
- score rounding;
- tie-breaking order;
- critical priority does not automatically outrank a much worse operational impact;
- no duplicate impact calculation;
- deterministic rank numbering.

---

# 17. Function specification: `recommendMitigationPlan`

## 17.1 Purpose

Generate a deterministic, read-only recommendation for mitigating a risk event.

The function must answer:

> Which feasible combination of inventory transfer, purchase-order expedite, or shipment prioritization best reduces the current order impact?

It must not persist a plan or execute any step.

## 17.2 Input

Preserve the ontology contract. Expected input:

```text
riskEventId: string
optional strategyPreference: string
optional notes: string
```

When the function metadata currently accepts only `riskEventId`, keep strategy preference in the action layer unless the ontology schema is intentionally updated.

## 17.3 Dependencies

Orchestrate:

```text
findImpactedParts
findImpactedProducts
findImpactedOrders
rankImpactedOrders
findAlternativeWarehouses
findExpeditablePurchaseOrders
```

Reuse one shared analysis snapshot so child calculations do not observe different database states.

## 17.4 Candidate strategy order

Default Version 1 policy:

```text
1. Reallocate safe surplus inventory.
2. Expedite an existing purchase order.
3. Prioritize a planned or ready shipment when it can improve the affected order.
4. Combine options when one option cannot cover the shortage.
```

This order is a policy default, not an unconditional choice. Reject an earlier strategy when it is infeasible, too late, or materially worse than another option.

## 17.5 Shipment-priority candidates

Version 1 may recommend `prioritize_shipment` only when:

- a shipment already exists for an impacted order;
- shipment status is `planned` or `ready`;
- raising priority can still improve the planned ship or delivery outcome;
- the recommendation does not pretend that missing inventory already exists.

Shipment prioritization cannot solve a part shortage by itself. Use it only after supply becomes available or for an already allocated order.

## 17.6 Candidate evaluation

Evaluate every candidate or combination using:

```text
feasible
quantityRecovered
ordersFullyRecovered
ordersPartiallyRecovered
projectedRevenueProtected
estimatedCost
latestRequiredArrivalDate
remainingAtRiskOrders
operationalWarnings
```

Suggested deterministic comparison:

1. feasible candidates only;
2. highest number of fully recovered orders;
3. highest projected revenue protected;
4. highest total quantity recovered;
5. earliest recovery date;
6. lowest estimated cost;
7. fewest operational steps;
8. stable strategy key ascending.

Do not hide alternative strategies. Return the recommended option and useful alternatives.

## 17.7 Step representation

Each proposed step must map to a governed action schema.

```ts
interface RecommendedMitigationStep {
  sequenceNumber: number;
  stepType:
    | "reallocate_inventory"
    | "expedite_purchase_order"
    | "prioritize_shipment";
  targetObjectType: string;
  targetObjectId: string;
  parameters: Record<string, unknown>;
  estimatedCost: Decimal;
  expectedBenefit: {
    quantityRecovered: number;
    impactedOrderIds: string[];
    projectedRevenueProtected: Decimal;
    expectedArrivalDate: string | null;
  };
  evidence: Record<string, unknown>;
}
```

The parameters must already match the target action's validation schema so `generateMitigationPlan` can safely persist the recommendation snapshot.

## 17.8 Confidence score

Confidence is not an LLM confidence value.

Calculate it from data completeness and estimator certainty.

Suggested components:

```text
inventory freshness
complete destination assignment
complete BOM coverage
known expected delivery dates
percentage of shortage covered
whether estimated transfer/expedite defaults were required
```

Return `0..1`.

A recommendation based on configured transport and expedite assumptions should have lower confidence than one based on explicit operational records.

## 17.9 Recommended output

```ts
interface MitigationRecommendationResult {
  riskEventId: string;
  recommendedStrategy: string;
  summary: string;
  confidenceScore: number;
  estimatedCost: Decimal;
  projectedOrdersRecovered: number;
  projectedRevenueProtected: Decimal;
  remainingAtRiskOrderIds: string[];
  mitigationSteps: RecommendedMitigationStep[];
  alternativeStrategies: Array<{
    strategy: string;
    feasible: boolean;
    estimatedCost: Decimal;
    projectedOrdersRecovered: number;
    projectedRevenueProtected: Decimal;
    rejectionReasons: string[];
  }>;
  assumptions: string[];
  warnings: string[];
  evidence: {
    impactedPartIds: string[];
    impactedProductIds: string[];
    impactedOrderIds: string[];
    rankedOrderIds: string[];
    snapshotExecutedAt: string;
  };
  explanation: string;
}
```

## 17.10 No feasible mitigation

A valid result may contain no steps.

Return:

```text
recommendedStrategy = no_feasible_mitigation
mitigationSteps = []
confidenceScore based on data completeness
warnings explaining why options failed
```

Do not invent an executable plan merely to avoid an empty recommendation.

## 17.11 Minimum tests

- safe transfer fully covers shortage;
- expedite chosen when transfer is too late;
- combination chosen when one step is insufficient;
- shipment priority is not used to fabricate missing supply;
- lower-cost strategy does not win when it recovers fewer critical orders;
- no feasible option returns a valid empty recommendation;
- step parameters match action schemas;
- repeated execution on same snapshot returns identical recommendation.

---

# 18. Function specification: `validateMitigationPlan`

## 18.1 Purpose

Revalidate a persisted mitigation plan against the current operational state without changing the plan.

Plans must be revalidated because inventory, purchase orders, shipments, and dates may have changed after recommendation generation.

Required workflow:

```text
generate
→ validate
→ submit
→ validate
→ approve
→ validate
→ execute
```

## 18.2 Input

```text
mitigationPlanId: string
```

## 18.3 Validation categories

### 18.3.1 Structural validation

Validate:

- plan exists;
- at least one step exists;
- sequence numbers are positive, unique, and continuous;
- step types are supported;
- target object types and IDs exist;
- parameters match the governed action schema;
- required fields are present;
- unknown parameters are rejected;
- currency and quantities are non-negative;
- source and destination warehouses differ for transfers.

### 18.3.2 Plan-state validation

The function may validate plans in states where a caller needs feasibility checking:

```text
draft
pending_approval
approved
```

Return a warning or error for terminal states depending on caller intent. The surrounding action still enforces the exact allowed transition.

### 18.3.3 Inventory validation

For every transfer step:

- source inventory exists;
- source warehouse is active;
- destination warehouse is active;
- part exists and is active;
- requested quantity is currently transferable;
- source remains above safety stock;
- existing approved/in-transit transfers are included;
- the same source quantity is not allocated twice across plan steps;
- estimated arrival is still useful.

### 18.3.4 Purchase-order validation

For every expedite step:

- purchase order exists;
- status remains expeditable;
- target part has positive open quantity;
- expected date and open quantity have not invalidated the step;
- order has not already been received or cancelled;
- possible expedited date remains useful;
- additional cost is recalculated.

### 18.3.5 Shipment validation

For every priority step:

- shipment exists;
- status is still `planned` or `ready`;
- shipment belongs to the expected customer order;
- inventory or allocation exists for what will be shipped;
- the requested priority differs from or improves the current priority;
- prioritization still has operational benefit.

### 18.3.6 Timing validation

Recalculate:

- transfer arrival;
- expedited PO arrival;
- shipment timing benefit;
- impacted order required dates.

A step that arrives after every affected required date is not feasible unless explicitly marked as partial late mitigation.

### 18.3.7 Cost validation

Recalculate plan and step costs.

```text
costDifferencePercent
= abs(recalculatedCost - savedEstimatedCost)
  / max(savedEstimatedCost, 1)
  × 100
```

Use the configured tolerance.

A material cost difference may be:

- a warning during draft review;
- an error before approval or execution.

The function should return severity. The surrounding action determines policy based on its stage.

### 18.3.8 Staleness

Report whether the recommendation or latest validation snapshot is older than configured `validationStaleAfterMinutes`.

Staleness alone does not prove infeasibility, but it should trigger fresh validation.

## 18.4 Double-allocation prevention inside the plan

Maintain a temporary allocation map while validating steps:

```text
(sourceWarehouseId, partId) → totalQuantityClaimedByPlan
```

Each later step sees the quantity already claimed by earlier steps.

Validation must fail when the sum of transfer steps exceeds current transferable stock, even when each step appears individually valid.

## 18.5 Recommended output

```ts
interface MitigationPlanValidationResult {
  mitigationPlanId: string;
  valid: boolean;
  validatedAt: string;
  staleSinceGeneration: boolean;
  validationErrors: Array<{
    code: string;
    message: string;
    stepId: string | null;
    path: string | null;
  }>;
  validationWarnings: Array<{
    code: string;
    message: string;
    stepId: string | null;
    path: string | null;
  }>;
  stepValidationResults: Array<{
    mitigationStepId: string;
    valid: boolean;
    errors: string[];
    warnings: string[];
    recalculatedEstimatedCost: Decimal;
    currentExpectedBenefit: Record<string, unknown>;
  }>;
  inventorySnapshot: Record<string, unknown>;
  purchaseOrderSnapshot: Record<string, unknown>;
  shipmentSnapshot: Record<string, unknown>;
  recalculatedEstimatedCost: Decimal;
  savedEstimatedCost: Decimal;
  costDifference: Decimal;
  costDifferencePercent: number;
  snapshotExecutedAt: string;
}
```

## 18.6 Important boundary

This function must not:

- change plan status;
- update saved costs;
- update steps;
- reserve inventory;
- persist a validation snapshot by itself.

The calling action may persist the returned snapshot as part of its governed transaction.

## 18.7 Minimum tests

- valid draft plan;
- missing target object;
- invalid step parameters;
- duplicate sequence numbers;
- transfer violates source safety stock;
- two individually valid transfers double-allocate the same inventory;
- PO received after plan generation invalidates expedite step;
- shipment already shipped invalidates priority step;
- cost difference warning/error data;
- no writes occur during validation.

---

## 19. Error contract

Use the repository's standard error shape. Error codes should remain stable and machine-readable.

Recommended function errors:

```text
FUNCTION_NOT_FOUND
FUNCTION_NOT_ALLOWED
INVALID_FUNCTION_INPUT
RISK_EVENT_NOT_FOUND
UNSUPPORTED_RISK_TYPE
SUPPLIER_NOT_FOUND
PART_NOT_FOUND
WAREHOUSE_NOT_FOUND
CUSTOMER_ORDER_NOT_FOUND
MITIGATION_PLAN_NOT_FOUND
INVALID_HORIZON_DATE
INCOMPLETE_BOM_DATA
INCONSISTENT_OPERATIONAL_DATA
FUNCTION_EXECUTION_FAILED
```

Distinguish:

```text
fatal error
= function cannot produce a trustworthy result

warning
= function can produce a result, but assumptions or missing data reduce certainty

empty result
= valid calculation found nothing
```

Do not convert a database or programming error into an empty result.

---

## 20. API and runtime integration

Expected runtime endpoint pattern:

```http
POST /functions/:functionName
```

The runtime should:

1. load function metadata from the ontology registry;
2. authenticate the actor;
3. authorize allowed roles;
4. validate input against the ontology schema;
5. resolve the stable handler name;
6. create `FunctionExecutionContext`;
7. execute inside a consistent read snapshot when needed;
8. validate or serialize the handler output;
9. return ontology version and request ID metadata;
10. record technical telemetry.

Do not build function-specific public routes when the existing runtime already provides generic ontology dispatch, unless a typed application adapter is useful internally.

Suggested envelope:

```json
{
  "function": "findImpactedOrders",
  "ontologyVersion": "1.0.0",
  "executedAt": "...",
  "requestId": "...",
  "data": {},
  "warnings": []
}
```

---

## 21. MCP integration

Approved read-only functions may be exposed through MCP tools according to ontology permissions.

Recommended AI-readable tools:

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
```

`validateMitigationPlan` may be exposed only when useful and when the caller is allowed to inspect the plan.

MCP adapters must:

- call the same ontology runtime and handlers as the application;
- never duplicate calculations in prompt logic;
- preserve authorization;
- return structured evidence;
- clearly distinguish recommendation from execution;
- never expose critical write actions as though they were read tools.

---

## 22. Performance guidance

### 22.1 Avoid N+1 queries

Batch-load:

- supplier parts;
- purchase-order lines;
- BOM requirements;
- order lines;
- inventory positions;
- transfers.

Use joins, grouped queries, or repository batch methods.

### 22.2 Query indexes

Reuse indexes defined by the database context. Expected high-value access patterns include:

```text
risk_events by risk_event_id
supplier_parts by supplier_id and status
purchase_orders by supplier_id, status, expected_delivery_date
purchase_order_lines by purchase_order_id and part_id
inventory_positions by part_id and warehouse_id
product_part_requirements by part_id and product_id
order_lines by product_id and order_id
customer_orders by status, required_delivery_date, priority
inventory_transfers by part_id, source/destination warehouse, status
```

Do not add speculative indexes without checking query plans and the database context.

### 22.3 Caching

Correctness is more important than caching for Version 1.

Safe cache candidates:

- static configuration;
- normalized ontology metadata;
- active BOM mappings with explicit invalidation;
- warehouse region/country metadata.

Do not broadly cache operational impact, inventory availability, recommendation, or validation results unless the cache key includes the operational snapshot/version and invalidation is reliable.

### 22.4 Bounded output

Large ledgers and evidence lists should support pagination or an optional detail level when real data grows.

Version 1 may return full demo data, but core summary fields must not depend on truncating evidence.

---

## 23. Testing strategy

### 23.1 Pure unit tests

Test pure helpers for:

- open quantity;
- available quantity;
- BOM conversion;
- buildable quantity;
- stockout ledger;
- risk-score factors;
- order-ranking factors;
- transfer estimates;
- expedite estimates;
- tie-breakers;
- cost tolerance.

Use fixed `executedAt` values.

### 23.2 Repository/service tests

Test:

- filters by status;
- batched reads;
- correct table relationships;
- no duplicate rows from joins;
- consistent transaction/snapshot use;
- decimal and date mapping.

### 23.3 Handler integration tests

Seed a complete supplier-delay scenario and verify the end-to-end chain:

```text
RiskEvent
→ impacted parts
→ impacted products
→ impacted orders
→ ranked orders
→ mitigation recommendation
```

### 23.4 Read-only enforcement tests

For every function:

- verify no operational insert/update/delete occurs;
- verify no action handler is dispatched;
- verify validation does not persist changes;
- verify repeated calls do not alter results or database state.

### 23.5 Golden scenario

Create a deterministic demo scenario equivalent to:

```text
Supplier S-102 delayed by 5 days.
Part B develops a 40-unit shortage.
Part E's existing shortage grows from 10 to 40.
A and C are not impacted.
Another supplier covers Part D.
Impacted products and orders are derived through the BOM.
An alternative warehouse covers some or all shortage.
The recommendation proposes a draftable, explainable mitigation.
```

Store expected DTOs as fixtures when that matches repository testing conventions.

---

## 24. Implementation order for Codex

Implement in this order unless the repository already contains some pieces:

### Phase 1: Contracts and configuration

- inspect `ontology.yaml` function schemas;
- define shared input/output DTOs;
- define and validate function configuration;
- define runtime context and error types.

### Phase 2: Pure calculation helpers

- quantity helpers;
- date helpers;
- stockout ledger;
- scoring calculators;
- transfer estimator;
- expedite estimator.

Add unit tests before orchestration handlers.

### Phase 3: Shared projection services

- supply projection;
- demand projection;
- BOM traversal;
- order allocation.

### Phase 4: Impact handlers

```text
findImpactedParts
findImpactedProducts
findImpactedOrders
```

### Phase 5: Inventory handlers

```text
calculateStockoutRisk
getInventoryAvailability
findAlternativeWarehouses
findExpeditablePurchaseOrders
```

### Phase 6: Ranking and recommendation

```text
rankImpactedOrders
recommendMitigationPlan
```

### Phase 7: Plan validation

```text
validateMitigationPlan
```

### Phase 8: Runtime and MCP adapters

- register stable handler names;
- validate runtime input/output;
- enforce permissions;
- expose approved read tools;
- add telemetry.

### Phase 9: Final validation

Run:

```text
formatter
lint
type checking
unit tests
integration tests
production build or backend startup check
```

Do not disable checks to make the implementation pass.

---

## 25. Version 1 exclusions

Do not add these to complete this task:

```text
ontology editor
new ontology object types
transportation-lane database model
supplier-contract database model
alternative-part solver
forecasting or machine-learning demand model
optimization solver dependency
LLM-generated numeric recommendations
automatic plan approval
automatic plan execution
inventory writes inside functions
generic CRUD writes
background job system unless already required by the repository
```

A deterministic policy engine is sufficient for the Version 1 demo.

---

## 26. Acceptance criteria

The function implementation is complete only when:

### Common behavior

- all 10 stable handlers exist and are registered;
- all functions are read-only;
- runtime permissions come from ontology metadata;
- inputs and outputs are validated;
- calculations use a fixed execution context time;
- multi-query functions use a consistent read snapshot;
- outputs are deterministic and typed;
- important scores include evidence and breakdowns;
- warnings are separate from errors;
- empty results are handled cleanly.

### Impact analysis

- linked parts are not automatically considered impacted;
- baseline and delayed scenarios are compared;
- received PO quantity is not delayed;
- demand is derived through the BOM;
- order allocation is deterministic;
- only risk-event-caused impact is returned.

### Inventory analysis

- available inventory subtracts reservations;
- inbound eligibility respects required dates;
- source safety stock is preserved;
- transfers and purchase orders are not double-counted;
- stockout ledger and dates are correct.

### Scoring

- stockout-risk weights are `50/25/15/10`;
- order-ranking weights are `25/20/20/15/10/10`;
- configured weights are startup-validated;
- score boundaries and tie-breakers have tests;
- criticality alone cannot create stockout risk.

### Recommendation and validation

- recommendation returns steps but creates no records;
- each step maps to a governed action schema;
- alternatives and assumptions are visible;
- no-feasible-option is a valid result;
- plan validation checks current state and cross-step allocation;
- validation performs no writes;
- submit, approve, and execute actions can consume the validation result.

### Quality

- no N+1 query pattern in the main impact workflow;
- focused unit and integration tests exist;
- the golden supplier-delay scenario passes;
- existing repository tests continue to pass;
- no unrelated refactor or future-phase scope is added.

---

## 27. Expected final report from Codex

After implementation, report:

```text
1. Files created
2. Files modified
3. Stable handler registrations added
4. Function contracts implemented
5. Configuration values and defaults added
6. Database queries or repositories reused
7. Tests added
8. Commands run
9. Test and build results
10. Assumptions or limitations that remain
```

Do not claim a function is complete when it returns placeholder data, hardcoded demo results, unvalidated LLM output, or performs hidden writes.
