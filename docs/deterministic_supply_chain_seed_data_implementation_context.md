# Deterministic Supply-Chain Seed Data — Implementation Context

> **Short description:** This file defines the deterministic Version 1 PostgreSQL seed data for the supply-chain disruption demo. It specifies fixed records, relationships, dates, seed profiles, expected function outcomes, action-ready state, verification rules, and implementation boundaries for a coding agent.

---

## 1. Purpose

Use this document when implementing or reviewing the deterministic database seed for the project.

The seed must support:

- database migration validation;
- ontology object and link traversal;
- read-only function tests;
- the supplier-delay demonstration;
- governed action tests;
- Object Explorer and relationship-graph examples;
- repeatable integration and end-to-end tests.

The seed is not random sample data. It is a controlled operational fixture whose results must remain stable across machines and repeated runs.

---

## 2. Read this with the existing project context

Before implementing the seed, read the repository's actual versions of:

```text
AGENT.md or agent.md
supplygraph_database_context.md
SupplyGraph_Ontology_Implementation_Context.md
ontology_functions_implementation_context.md
ontology_actions_implementation_context.md
BACKEND_IMPLEMENTATION_PLAN.md
```

Use the repository's actual paths and filename capitalization.

Source-of-truth responsibilities:

```text
supplygraph_database_context.md
= tables, columns, constraints, indexes, and persisted relationships

ontology/ontology.yaml
= object, property, link, function, action, and permission metadata

ontology_functions_implementation_context.md
= deterministic calculations and expected impact semantics

ontology_actions_implementation_context.md
= governed workflow and transactional write semantics

this document
= exact Version 1 seed records, dates, relationships, and expected outcomes
```

When this document names a business field that has a different physical column name in the finalized database context, use the database context's physical name without changing the business meaning.

Do not add a new database column merely to fit this seed. Map to the existing equivalent or omit an optional display-only value.

---

## 3. Seed goals

The seed must prove all of the following:

1. A supplier can be linked to several parts.
2. A part can be linked to several suppliers.
3. Products depend on parts through a bill of materials.
4. Customer-order demand becomes part demand through that bill of materials.
5. A supplier delay can create a new shortage.
6. A supplier delay can worsen an existing shortage.
7. A linked part can remain unaffected because current inventory is sufficient.
8. A linked part can remain unaffected because another supplier covers demand.
9. Another warehouse can safely cover a shortage while preserving safety stock.
10. An open purchase order can be evaluated for expedited delivery.
11. Impacted products and orders can be derived through ontology links.
12. A mitigation recommendation can map to governed action schemas.
13. The full human-approved action lifecycle can run from the seeded operational state.
14. Repeated seed execution produces the same records and results.

The seed must not merely populate every table with arbitrary rows.

---

## 4. Fixed deterministic clock

Use one fixed seed clock:

```text
SEED_REFERENCE_TIME = 2026-07-14T12:00:00Z
SEED_REFERENCE_DATE = 2026-07-14
```

All seed timestamps and dates must be explicit values derived from this reference.

Do not use:

```text
CURRENT_TIMESTAMP
NOW()
datetime.now()
date.today()
random UUIDs
Faker-generated values
```

inside deterministic seed construction.

Runtime function tests must pass the same fixed time as `executedAt` when asserting golden results.

---

## 5. Seed profiles

Implement two supported profiles.

### 5.1 `base`

Contains operational master and transaction data, but no `RiskEvent`.

Use it for testing:

- `createRiskEvent`;
- duplicate-active-risk protection;
- base object/link traversal;
- migrations and foreign keys.

### 5.2 `golden`

Contains everything in `base` plus the open supplier-delay risk:

```text
RISK-102
```

Use it for:

- impact functions;
- stockout calculations;
- order ranking;
- mitigation recommendation;
- acknowledgement and the remaining action workflow;
- the primary application demo.

Recommended local default:

```text
SEED_PROFILE=golden
```

Do not seed mitigation plans, mitigation steps, inventory transfers, action executions, or audit logs in either profile. Those records should be created by governed actions so the workflow proves its own behavior.

Tests that require later workflow states should reach those states by invoking actions or by using narrowly scoped test-only fixture builders. Do not add many pre-seeded lifecycle variants to the main developer seed.

---

## 6. Stable identifiers and naming

Use the exact identifiers in this document unless an existing database constraint requires a documented formatting adjustment.

Identifiers must be human-readable and stable.

Examples:

```text
Supplier:              S-102
Part:                  PART-B
Product:               PROD-100
Warehouse:             WH-A
SupplierPart:          SP-S102-B
BOM requirement:       BOM-P100-B
Inventory position:    INV-WHA-B
Customer order:        ORD-881
Order line:            OL-881-1
Purchase order:        PO-201
Purchase-order line:   POL-201-B
Shipment:              SHIP-881
Risk event:            RISK-102
```

Do not generate identifiers from insertion order or database sequences when tests or demos refer to them directly.

---

## 7. Suppliers

Seed exactly these three suppliers.

| supplierId | name | country | region | status | reliabilityScore | defaultLeadTimeDays |
|---|---|---|---|---|---:|---:|
| `S-101` | Northstar Components | United States | West | active | 94 | 4 |
| `S-102` | Vertex Electronics | United States | West | active | 72 | 5 |
| `S-103` | Midwest Power Systems | United States | Central | active | 91 | 3 |

Common timestamps:

```text
createdAt = 2026-07-01T09:00:00Z
updatedAt = 2026-07-14T08:00:00Z
```

Business role:

```text
S-102 = affected supplier
S-103 = unaffected supplier that covers Part D
S-101 = unaffected comparison supplier
```

Do not set `S-102.status = delayed` merely because an open risk exists. Supplier status and risk state are separate concepts unless a governed action explicitly changes supplier status in a later version.

---

## 8. Parts

Seed exactly these five active parts.

| partId | sku | name | category | unitOfMeasure | safetyStockQuantity | status |
|---|---|---|---|---|---:|---|
| `PART-A` | `PART-A` | Aluminum Housing | Mechanical | each | 20 | active |
| `PART-B` | `PART-B` | Control Board | Electronics | each | 30 | active |
| `PART-C` | `PART-C` | Power Cable | Electrical | each | 20 | active |
| `PART-D` | `PART-D` | Battery Pack | Power | each | 15 | active |
| `PART-E` | `PART-E` | Sensor Module | Electronics | each | 10 | active |

Common timestamps:

```text
createdAt = 2026-07-01T09:15:00Z
updatedAt = 2026-07-14T08:00:00Z
```

---

## 9. Products

Seed exactly these three active products.

| productId | sku | name | category | status |
|---|---|---|---|---|
| `PROD-100` | `PROD-100` | Edge Controller | Industrial Control | active |
| `PROD-200` | `PROD-200` | Battery Gateway | Industrial Gateway | active |
| `PROD-300` | `PROD-300` | Vision Sensor | Machine Vision | active |

Common timestamps:

```text
createdAt = 2026-07-01T09:30:00Z
updatedAt = 2026-07-14T08:00:00Z
```

---

## 10. Warehouses

Seed exactly these three active warehouses.

| warehouseId | code | name | city | region | country | capacity | status |
|---|---|---|---|---|---|---:|---|
| `WH-A` | `LAX-01` | Los Angeles Fulfillment Center | Los Angeles | West | United States | 10000 | active |
| `WH-B` | `SFO-01` | San Francisco Reserve Center | San Francisco | West | United States | 8000 | active |
| `WH-C` | `CHI-01` | Chicago Distribution Center | Chicago | Central | United States | 9000 | active |

Business role:

```text
WH-A = destination warehouse for the affected orders and purchase orders
WH-B = same-region alternative warehouse with safe surplus of PART-B
WH-C = comparison warehouse without enough transferable PART-B or PART-E
```

Common timestamps:

```text
createdAt = 2026-07-01T09:45:00Z
updatedAt = 2026-07-14T08:00:00Z
```

---

## 11. Supplier-part relationships

Seed these eight `SupplierPart` records.

| supplierPartId | supplierId | partId | unitCost | leadTimeDays | maximumWeeklyCapacity | minimumOrderQuantity | preferred | status |
|---|---|---|---:|---:|---:|---:|---:|---|
| `SP-S102-A` | `S-102` | `PART-A` | 45.00 | 5 | 500 | 10 | false | active |
| `SP-S102-B` | `S-102` | `PART-B` | 100.00 | 5 | 300 | 10 | true | active |
| `SP-S102-C` | `S-102` | `PART-C` | 12.00 | 4 | 1000 | 25 | false | active |
| `SP-S102-D` | `S-102` | `PART-D` | 140.00 | 5 | 200 | 10 | false | active |
| `SP-S102-E` | `S-102` | `PART-E` | 80.00 | 5 | 400 | 10 | true | active |
| `SP-S103-D` | `S-103` | `PART-D` | 145.00 | 3 | 250 | 10 | true | active |
| `SP-S101-A` | `S-101` | `PART-A` | 47.00 | 4 | 400 | 10 | true | active |
| `SP-S101-C` | `S-101` | `PART-C` | 13.00 | 4 | 800 | 25 | true | active |

Use decimal arithmetic for costs.

Common timestamps:

```text
createdAt = 2026-07-02T09:00:00Z
updatedAt = 2026-07-14T08:00:00Z
```

The active `S-103 → PART-D` relationship is required to prove that a linked part is not automatically impacted when another supplier provides enough on-time supply.

---

## 12. Product bill of materials

Seed these seven active `ProductPartRequirement` records.

| requirementId | productId | partId | quantityRequired | substitutionAllowed | status |
|---|---|---|---:|---:|---|
| `BOM-P100-A` | `PROD-100` | `PART-A` | 1 | false | active |
| `BOM-P100-B` | `PROD-100` | `PART-B` | 1 | false | active |
| `BOM-P100-C` | `PROD-100` | `PART-C` | 2 | false | active |
| `BOM-P200-B` | `PROD-200` | `PART-B` | 1 | false | active |
| `BOM-P200-D` | `PROD-200` | `PART-D` | 1 | false | active |
| `BOM-P300-C` | `PROD-300` | `PART-C` | 1 | false | active |
| `BOM-P300-E` | `PROD-300` | `PART-E` | 1 | false | active |

Common timestamps:

```text
createdAt = 2026-07-02T10:00:00Z
updatedAt = 2026-07-14T08:00:00Z
```

Expected open demand after BOM expansion:

| partId | calculation | required quantity |
|---|---|---:|
| `PART-A` | 40 × 1 | 40 |
| `PART-B` | (40 × 1) + (10 × 1) | 50 |
| `PART-C` | (40 × 2) + (50 × 1) | 130 |
| `PART-D` | 10 × 1 | 10 |
| `PART-E` | 50 × 1 | 50 |

Cancelled and fully fulfilled control orders must not contribute to these totals.

---

## 13. Inventory positions

Seed one position for every part in every warehouse: 15 rows total.

This avoids missing destination rows during object traversal and transfer tests.

| inventoryPositionId | warehouseId | partId | onHand | reserved | available | transferable after safety stock |
|---|---|---|---:|---:|---:|---:|
| `INV-WHA-A` | `WH-A` | `PART-A` | 120 | 20 | 100 | 80 |
| `INV-WHA-B` | `WH-A` | `PART-B` | 20 | 10 | 10 | 0 |
| `INV-WHA-C` | `WH-A` | `PART-C` | 200 | 40 | 160 | 140 |
| `INV-WHA-D` | `WH-A` | `PART-D` | 0 | 0 | 0 | 0 |
| `INV-WHA-E` | `WH-A` | `PART-E` | 20 | 10 | 10 | 0 |
| `INV-WHB-A` | `WH-B` | `PART-A` | 50 | 10 | 40 | 20 |
| `INV-WHB-B` | `WH-B` | `PART-B` | 100 | 20 | 80 | 50 |
| `INV-WHB-C` | `WH-B` | `PART-C` | 80 | 10 | 70 | 50 |
| `INV-WHB-D` | `WH-B` | `PART-D` | 20 | 5 | 15 | 0 |
| `INV-WHB-E` | `WH-B` | `PART-E` | 10 | 0 | 10 | 0 |
| `INV-WHC-A` | `WH-C` | `PART-A` | 40 | 5 | 35 | 15 |
| `INV-WHC-B` | `WH-C` | `PART-B` | 20 | 10 | 10 | 0 |
| `INV-WHC-C` | `WH-C` | `PART-C` | 60 | 10 | 50 | 30 |
| `INV-WHC-D` | `WH-C` | `PART-D` | 30 | 10 | 20 | 5 |
| `INV-WHC-E` | `WH-C` | `PART-E` | 10 | 0 | 10 | 0 |

Calculations:

```text
availableQuantity
= max(0, onHandQuantity - reservedQuantity)

transferableQuantity
= max(0, onHandQuantity - reservedQuantity - part.safetyStockQuantity)
```

Required golden invariant:

```text
WH-B / PART-B transferableQuantity = 100 - 20 - 30 = 50
```

Therefore a 40-unit transfer to `WH-A` is feasible and leaves 10 transferable units above safety stock.

If the finalized schema contains `inTransitQuantity`, seed it as `0` for all positions. If in-transit supply is derived from `InventoryTransfer`, do not add or duplicate the column.

Common timestamps:

```text
updatedAt = 2026-07-14T08:30:00Z
```

---

## 14. Customer orders

Seed these four orders.

| orderId | customer display value | destinationWarehouseId | status | priority | orderDate | requiredDeliveryDate |
|---|---|---|---|---|---|---|
| `ORD-881` | Apex Retail | `WH-A` | confirmed | critical | 2026-07-10 | 2026-07-20 |
| `ORD-882` | Metro Systems | `WH-A` | confirmed | high | 2026-07-11 | 2026-07-21 |
| `ORD-883` | Nova Vision | `WH-A` | confirmed | normal | 2026-07-12 | 2026-07-22 |
| `ORD-884` | Cancelled Control Order | `WH-A` | cancelled | critical | 2026-07-09 | 2026-07-19 |

Use the database context's existing customer-name or customer-identifier fields. Do not create a new `Customer` table for Version 1.

Common timestamps:

```text
createdAt = orderDate at 09:00:00Z
updatedAt = 2026-07-14T08:45:00Z
```

The cancelled order exists to prove that cancelled demand is excluded even when it has an urgent date and high priority.

---

## 15. Order lines

Seed these four order lines.

| orderLineId | orderId | productId | quantity | allocatedQuantity | fulfilledQuantity | unitPrice |
|---|---|---|---:|---:|---:|---:|
| `OL-881-1` | `ORD-881` | `PROD-100` | 40 | 0 | 0 | 1500.00 |
| `OL-882-1` | `ORD-882` | `PROD-200` | 10 | 0 | 0 | 2200.00 |
| `OL-883-1` | `ORD-883` | `PROD-300` | 50 | 0 | 0 | 900.00 |
| `OL-884-1` | `ORD-884` | `PROD-300` | 100 | 0 | 0 | 900.00 |

Common timestamps:

```text
createdAt = corresponding orderDate at 09:05:00Z
updatedAt = 2026-07-14T08:45:00Z
```

Open order values:

```text
ORD-881 = 40 × 1500 = 60000.00
ORD-882 = 10 × 2200 = 22000.00
ORD-883 = 50 × 900  = 45000.00
```

---

## 16. Shipments

Seed one eligible planned shipment for each active order.

| shipmentId | orderId | warehouseId | carrier | priority | status | plannedShipDate | estimatedDeliveryDate |
|---|---|---|---|---|---|---|---|
| `SHIP-881` | `ORD-881` | `WH-A` | Atlas Freight | normal | planned | 2026-07-19 | 2026-07-21 |
| `SHIP-882` | `ORD-882` | `WH-A` | Atlas Freight | normal | planned | 2026-07-20 | 2026-07-22 |
| `SHIP-883` | `ORD-883` | `WH-A` | Pacific Logistics | normal | planned | 2026-07-21 | 2026-07-23 |

Use the same value for `shipmentNumber` when the schema separates ID and display number.

Seed:

```text
actualDeliveryDate = null
trackingNumber = null
createdAt = 2026-07-13T10:00:00Z
updatedAt = 2026-07-14T08:50:00Z
```

These records allow `prioritizeShipment` to be tested. They do not prove that shipment priority alone can solve missing inventory.

---

## 17. Purchase orders

Seed these six open purchase orders.

| purchaseOrderId | supplierId | destinationWarehouseId | status | orderDate | expectedDeliveryDate | expedited | expediteCost |
|---|---|---|---|---|---|---:|---:|
| `PO-200` | `S-102` | `WH-A` | confirmed | 2026-07-09 | 2026-07-19 | false | 0.00 |
| `PO-201` | `S-102` | `WH-A` | confirmed | 2026-07-08 | 2026-07-18 | false | 0.00 |
| `PO-202` | `S-102` | `WH-A` | confirmed | 2026-07-08 | 2026-07-18 | false | 0.00 |
| `PO-203` | `S-102` | `WH-A` | confirmed | 2026-07-08 | 2026-07-18 | false | 0.00 |
| `PO-204` | `S-102` | `WH-A` | confirmed | 2026-07-09 | 2026-07-19 | false | 0.00 |
| `PO-205` | `S-103` | `WH-A` | confirmed | 2026-07-10 | 2026-07-18 | false | 0.00 |

Use the same value for `purchaseOrderNumber` when the schema separates ID and display number.

Common timestamps:

```text
createdAt = orderDate at 10:00:00Z
updatedAt = 2026-07-14T08:55:00Z
```

---

## 18. Purchase-order lines

Seed one line for each purchase order.

| purchaseOrderLineId | purchaseOrderId | partId | quantityOrdered | quantityReceived | openQuantity | unitCost |
|---|---|---|---:|---:|---:|---:|
| `POL-200-E` | `PO-200` | `PART-E` | 30 | 0 | 30 | 80.00 |
| `POL-201-B` | `PO-201` | `PART-B` | 50 | 0 | 50 | 100.00 |
| `POL-202-A` | `PO-202` | `PART-A` | 20 | 0 | 20 | 45.00 |
| `POL-203-C` | `PO-203` | `PART-C` | 50 | 0 | 50 | 12.00 |
| `POL-204-D` | `PO-204` | `PART-D` | 10 | 0 | 10 | 140.00 |
| `POL-205-D` | `PO-205` | `PART-D` | 10 | 0 | 10 | 145.00 |

Calculation:

```text
openQuantity
= max(0, quantityOrdered - quantityReceived)
```

The seed should also support a separate test that changes one line to partially received. Do not alter the golden fixture for that edge case.

---

## 19. Golden risk event

The `golden` profile seeds this event. The `base` profile does not.

| field | value |
|---|---|
| riskEventId | `RISK-102` |
| riskType | `supplier_delay` |
| supplierId | `S-102` |
| severity | `high` |
| status | `open` |
| delayDays | `5` |
| detectedAt | `2026-07-14T09:00:00Z` |
| expectedResolutionDate | `2026-07-24` |
| reason | `Supplier reported a five-day production delay.` |
| source | `manual_demo` |
| createdBy | `planner-001` |
| createdAt | `2026-07-14T09:00:00Z` |
| updatedAt | `2026-07-14T09:00:00Z` |
| resolvedAt | `null` |

The first governed write in the golden action demo is:

```text
acknowledgeRiskEvent(RISK-102)
```

The `base` profile should call `createRiskEvent` to create an equivalent event when testing the complete action chain from the beginning.

---

## 20. Golden baseline and delayed projections

For the risk event, simulate every open purchase order from `S-102` as arriving five days later.

```text
projectedExpectedDeliveryDate
= expectedDeliveryDate + 5 days
```

Purchase orders from `S-101` and `S-103` remain unchanged.

### 20.1 Expected part-level results

| part | starting available at WH-A | open demand | relevant baseline inbound by due horizon | baseline shortage | delayed inbound by due horizon | delayed shortage | risk-caused increase | impacted? |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `PART-A` | 100 | 40 | 20 | 0 | 0 | 0 | 0 | no |
| `PART-B` | 10 | 50 | 50 | 0 | 0 | 40 | 40 | yes |
| `PART-C` | 160 | 130 | 50 | 0 | 0 | 0 | 0 | no |
| `PART-D` | 0 | 10 | 20 | 0 | 10 from `S-103` | 0 | 0 | no |
| `PART-E` | 10 | 50 | 30 | 10 | 0 | 40 | 30 | yes |

Required assertions:

```text
PART-B develops a new 40-unit shortage.
PART-E's existing shortage grows from 10 to 40.
PART-A and PART-C remain unaffected because current inventory is sufficient.
PART-D remains unaffected because PO-205 from S-103 covers demand on time.
```

A connected part is returned by `findImpactedParts` only when:

```text
delayedShortageQuantity > baselineShortageQuantity
```

Expected impacted-part order:

```text
1. PART-B  shortage increase 40
2. PART-E  shortage increase 30
```

Final tie-breaking must still follow the function implementation context.

---

## 21. Expected impacted products

Expected impacted products:

```text
PROD-100 because PART-B limits buildability
PROD-200 because PART-B limits buildability
PROD-300 because PART-E limits buildability
```

Required non-impact evidence:

```text
PART-A and PART-C are connected to products but do not create additional risk-caused product shortages.
PART-D is connected to PROD-200 but remains covered by the unaffected supplier.
```

The implementation must evaluate each product's complete BOM. It must not mark a product impacted merely because one of its parts is linked to `S-102`.

---

## 22. Expected impacted orders

The deterministic allocation policy is:

```text
priority descending
requiredDeliveryDate ascending
orderDate ascending
orderId ascending
```

Expected impacted active orders:

```text
ORD-881
ORD-882
ORD-883
```

Expected reasons:

```text
ORD-881 and ORD-882 compete for delayed PART-B supply.
ORD-883 is constrained by PART-E.
ORD-884 is excluded because its status is cancelled.
```

For `PART-B`, delayed available quantity is 10 against 50 units of demand.

Under deterministic order allocation:

```text
ORD-881 receives the first 10 buildable units of PROD-100.
ORD-881 has a remaining 30-unit product shortage.
ORD-882 then has a 10-unit product shortage.
Total PART-B-driven delayed shortage = 40.
```

For `PART-E`:

```text
ORD-883 delayed shortage = 40 units.
Baseline shortage = 10 units.
Risk-caused shortage increase = 30 units.
```

`ORD-881` must rank ahead of `ORD-882` because it has higher priority and an earlier required date. Exact numeric risk scores should be asserted from the finalized function configuration and stored in expected-result fixtures after the scoring configuration is implemented.

Do not hardcode a score in the seed script.

---

## 23. Expected alternative-warehouse result

For this input:

```text
partId = PART-B
destinationWarehouseId = WH-A
requiredQuantity = 40
requiredByDate = 2026-07-20
executedAt = 2026-07-14T12:00:00Z
```

Expected primary candidate:

```text
warehouseId = WH-B
availableQuantity = 80
safetyStockQuantity = 30
transferableQuantity = 50
coveredQuantity = 40
remainingShortage = 0
estimatedTransferDays = 1
estimatedArrivalDate = 2026-07-15
feasible = true
```

Reason:

```text
WH-A and WH-B are in the same region.
WH-B retains PART-B safety stock after the proposed transfer.
```

`WH-C` must not be returned as a feasible source for `PART-B` because:

```text
20 on hand - 10 reserved - 30 safety stock <= 0 transferable
```

Transfer cost must be calculated from the configured transfer estimator. Do not store a derived transfer cost in the seed.

---

## 24. Expected expedite candidate

For `PO-200` and the default estimator:

```text
executedAtDate = 2026-07-14
currentExpectedDeliveryDate = 2026-07-19
remainingLeadTimeDays = 5
leadTimeReductionPercent = 0.40
reducedDays = floor(5 × 0.40) = 2
possibleExpeditedDate = 2026-07-17
openQuantity = 30
remainingLineValue = 30 × 80.00 = 2400.00
premiumPercent = 0.15
additionalCost = 360.00
```

Expected assertions:

```text
PO-200 is open and eligible.
PO-200 can be moved earlier to 2026-07-17 under the estimator.
The result clearly labels this as a configured estimate, not a supplier commitment.
```

In the supplier-delay simulation, an updated expected date of `2026-07-17` plus the five-day delay yields `2026-07-22`, which restores the original 10-unit baseline shortage rather than leaving the 40-unit delayed shortage.

Do not pre-expedite `PO-200` in the seed.

---

## 25. Expected mitigation recommendation

The golden recommendation should prefer a deterministic combination that addresses the risk-caused shortages:

```text
Step 1:
  action = reallocateInventory
  partId = PART-B
  sourceWarehouseId = WH-B
  destinationWarehouseId = WH-A
  quantity = 40

Step 2:
  action = expeditePurchaseOrder
  purchaseOrderId = PO-200
  newExpectedDeliveryDate = 2026-07-17
  additionalCost = 360.00
```

Expected behavior:

```text
The PART-B transfer covers the new 40-unit shortage.
The PART-E expedite restores the baseline arrival position.
The recommendation is read-only and explainable.
The generateMitigationPlan action may persist the recommendation as a draft.
```

`SHIP-881` is present so shipment-priority behavior can be tested, but shipment prioritization must not be presented as a substitute for missing inventory. Include it only when the recommendation logic proves supply is or will be available and the action can improve the order outcome.

The recommendation function must return useful alternatives and warnings according to its existing contract. It must not write a plan, reserve inventory, expedite a purchase order, or change a shipment.

---

## 26. Action-ready workflow from the golden profile

Expected action sequence:

```text
1. acknowledgeRiskEvent(RISK-102)
2. generateMitigationPlan(RISK-102)
3. submitMitigationPlan(planId)
4. approveMitigationPlan(planId) by a different human actor
5. executeMitigationPlan(planId)
6. completeInventoryTransfer(transferId) when physical stock arrives
7. resolveRiskEvent(RISK-102) after current impact and unfinished work are gone
```

Actors used by tests may be stable fixtures such as:

```text
planner-001         role: Planner
ops-manager-001     role: OperationsManager
admin-001           role: Admin
ai-agent-001        role: AIAgent
```

Actor identities belong to authentication/test fixtures, not necessarily to operational seed tables unless the database context includes users.

Governance assertions:

- `planner-001` may acknowledge, generate, and submit.
- The plan submitter cannot approve the same plan.
- `ops-manager-001` may approve and execute.
- `ai-agent-001` may generate only a draft plan.
- All write actions use idempotency keys.
- All write actions record execution and audit history.

---

## 27. Expected inventory state transitions

### 27.1 After `reallocateInventory` for 40 units of `PART-B`

Before:

```text
WH-B / PART-B:
  onHand = 100
  reserved = 20
  safetyStock = 30
  transferable = 50
```

After governed reallocation:

```text
WH-B / PART-B:
  onHand = 100
  reserved = 60
  transferable = 10

WH-A / PART-B:
  onHand = 20
  reserved = 10

InventoryTransfer:
  quantity = 40
  status = approved
```

Required rule:

```text
The destination on-hand quantity does not change when the transfer is merely approved.
```

### 27.2 After `completeInventoryTransfer`

Before completion:

```text
source WH-B: onHand 100, reserved 60
destination WH-A: onHand 20
transfer quantity: 40
```

After completion:

```text
source WH-B: onHand 60, reserved 20
destination WH-A: onHand 60
transfer status: completed
```

No quantity may become negative.

---

## 28. Expected purchase-order and shipment transitions

### 28.1 `expeditePurchaseOrder`

Expected `PO-200` transition:

```text
expectedDeliveryDate: 2026-07-19 → 2026-07-17
expedited: false → true
expediteCost: 0.00 → 360.00
status: confirmed → confirmed
```

The normal purchase-order status does not change.

### 28.2 `prioritizeShipment`

An eligible shipment such as `SHIP-881` may transition:

```text
priority: normal → critical
status: planned → planned
```

The action changes priority, not shipment status, inventory, or order fulfillment quantities.

---

## 29. Tables intentionally empty after seeding

For both standard profiles, these tables must start empty:

```text
mitigation_plans
mitigation_steps
inventory_transfers
action_executions
action_affected_objects or equivalent
audit_logs
AI tool-call history tables, when present
```

Reason:

```text
The demo should show governed actions creating workflow and audit records.
Pre-seeding those records would hide whether the Action Engine works correctly.
```

The `golden` profile contains one `RiskEvent` because read-only impact functions require it. The `base` profile leaves `risk_events` empty so `createRiskEvent` can be tested.

---

## 30. Expected row counts

After a clean `base` seed:

| resource | expected rows |
|---|---:|
| suppliers | 3 |
| parts | 5 |
| products | 3 |
| warehouses | 3 |
| supplier_parts | 8 |
| product_part_requirements | 7 |
| inventory_positions | 15 |
| customer_orders | 4 |
| order_lines | 4 |
| shipments | 3 |
| purchase_orders | 6 |
| purchase_order_lines | 6 |
| risk_events | 0 |
| mitigation_plans | 0 |
| mitigation_steps | 0 |
| inventory_transfers | 0 |
| action_executions | 0 |
| audit_logs | 0 |

After a clean `golden` seed:

```text
same counts as base
risk_events = 1
```

Adapt table names only when the finalized database context uses a different physical name.

---

## 31. Seed implementation requirements

Recommended backend location:

```text
app/db/seed.py
```

The implementation should expose a clear entry point equivalent to:

```python
seed_database(profile: SeedProfile, reset: bool = False) -> SeedResult
```

Recommended profile enum:

```text
base
golden
```

### 31.1 Transaction

Run the complete seed inside one database transaction.

If any row violates a constraint, roll back the entire seed.

### 31.2 Dependency order

Insert in foreign-key-safe order:

```text
1. suppliers
2. parts
3. products
4. warehouses
5. supplier_parts
6. product_part_requirements
7. inventory_positions
8. customer_orders
9. order_lines
10. shipments
11. purchase_orders
12. purchase_order_lines
13. risk_events for golden profile
```

Use the actual migration dependency order when it differs.

### 31.3 Repeatability

Running the same seed twice must not create duplicates.

Acceptable approaches:

- deterministic upserts keyed by stable IDs;
- a documented development-only reset followed by deterministic inserts.

Do not silently swallow conflicting records whose business fields differ from the expected fixture.

Recommended behavior for an existing stable ID with unexpected values:

```text
fail with a clear seed-drift error
```

or deliberately update it when `reset=true` according to repository conventions.

### 31.4 Reset behavior

A reset must delete only known development/test data and must follow reverse foreign-key order.

Never provide an unrestricted production reset path.

### 31.5 Environment protection

Refuse to run destructive reset or demo seeding when:

```text
APP_ENV=production
```

unless the repository already has a stricter explicit safety mechanism.

### 31.6 Numeric and date types

Use:

```text
Decimal or the repository money type for currency
integer or exact numeric types for whole-unit quantities
UTC-aware datetime values
date objects for date-only fields
```

Do not use binary floating-point arithmetic for currency assertions.

### 31.7 No business-action execution inside seed

The seed may insert the golden `RiskEvent` directly as fixture setup.

It must not call the Action Engine to create plans, reserve inventory, expedite orders, prioritize shipments, or create audit history.

The purpose of later integration tests is to prove those governed actions.

---

## 32. Expected-result fixtures

Create machine-readable expected fixtures when the repository testing conventions support them.

Recommended files:

```text
tests/fixtures/seed/golden_expected_impacted_parts.json
tests/fixtures/seed/golden_expected_impacted_products.json
tests/fixtures/seed/golden_expected_impacted_orders.json
tests/fixtures/seed/golden_expected_alternative_warehouses.json
tests/fixtures/seed/golden_expected_expedite_candidates.json
tests/fixtures/seed/golden_expected_recommendation.json
```

Expected fixtures must contain calculated DTOs, not copies of raw database rows.

Store exact score values only after the scoring weights and bucket configuration are finalized. The seed context defines operational inputs and core invariants; the function configuration defines numeric scores.

---

## 33. Verification tests

### 33.1 Database verification

Test that:

- migrations apply before seeding;
- all foreign keys resolve;
- unique constraints pass;
- domain checks pass;
- row counts match the selected profile;
- every object ID is stable;
- every expected relationship exists;
- workflow tables are empty initially.

### 33.2 Idempotent seed verification

Run the same profile twice and assert:

```text
row counts are unchanged
stable record values are unchanged
no duplicate unique values exist
the seed checksum is unchanged
```

A checksum may be calculated from a canonical serialization of seeded business fields ordered by table and stable ID.

Exclude database-generated technical metadata from the checksum unless those values are explicitly fixed.

### 33.3 Function golden tests

At `executedAt = 2026-07-14T12:00:00Z`, assert:

```text
findImpactedParts(RISK-102)
→ PART-B and PART-E only

PART-B
→ baseline shortage 0
→ delayed shortage 40
→ increase 40

PART-E
→ baseline shortage 10
→ delayed shortage 40
→ increase 30

findImpactedProducts(RISK-102)
→ PROD-100, PROD-200, PROD-300

findImpactedOrders(RISK-102)
→ ORD-881, ORD-882, ORD-883
→ ORD-884 excluded

findAlternativeWarehouses(PART-B, WH-A, 40, 2026-07-20)
→ WH-B feasible
→ transferable 50
→ covered 40
→ arrival 2026-07-15

findExpeditablePurchaseOrders(PART-E, S-102, 2026-07-22)
→ PO-200 eligible
→ possible date 2026-07-17
→ estimated additional cost 360.00
```

### 33.4 Read-only verification

For every read-only function, record table counts and relevant row hashes before and after execution.

Assert no operational insert, update, or delete occurs.

### 33.5 Action workflow verification

Using the golden profile, test:

```text
open risk → acknowledged
no plan → draft plan
 draft → pending_approval
pending_approval → approved by different actor
approved → completed through transactional execution
risk acknowledged → mitigated
approved transfer → completed physical transfer
mitigated risk → resolved when valid
```

Also verify:

- same idempotency key returns the original result;
- a different payload with the same key is rejected;
- failed plan execution rolls back all operational child effects;
- action and audit records contain affected objects and before/after values;
- AI cannot submit, approve, execute, or directly change operational state.

---

## 34. Seed result reporting

Return or print a concise deterministic summary equivalent to:

```json
{
  "profile": "golden",
  "referenceTime": "2026-07-14T12:00:00Z",
  "insertedOrVerified": {
    "suppliers": 3,
    "parts": 5,
    "products": 3,
    "warehouses": 3,
    "supplierParts": 8,
    "productPartRequirements": 7,
    "inventoryPositions": 15,
    "customerOrders": 4,
    "orderLines": 4,
    "shipments": 3,
    "purchaseOrders": 6,
    "purchaseOrderLines": 6,
    "riskEvents": 1
  },
  "goldenRiskEventId": "RISK-102",
  "checksum": "<stable checksum>"
}
```

Do not print secrets, connection strings, or unrestricted row payloads.

---

## 35. Version 1 exclusions

Do not add these merely to enrich the seed:

```text
new ontology object types
Customer table
Carrier table
TransportationLane table
SupplierContract table
AlternativePart table
DemandForecast table
ProductionOrder table
ManufacturingPlant table
real supplier or customer data
random bulk data
historical action logs
pre-approved plans
pre-completed transfers
machine-learning predictions
LLM-generated quantities or costs
```

The Version 1 seed should remain small enough to understand manually and complete enough to exercise the full workflow.

---

## 36. Acceptance criteria

The deterministic seed implementation is complete only when:

- both `base` and `golden` profiles exist;
- all stable IDs and fixed dates match this document;
- the golden profile contains exactly one open `RISK-102` supplier-delay event;
- repeat execution does not create duplicates;
- destructive reset is blocked in production;
- all database constraints pass;
- the documented row counts match;
- `PART-B` develops a 40-unit shortage;
- `PART-E` worsens from a 10-unit to a 40-unit shortage;
- `PART-A`, `PART-C`, and `PART-D` are excluded from impacted parts for the documented reasons;
- `WH-B` can safely transfer 40 units of `PART-B` while preserving safety stock;
- `PO-200` produces the documented expedite estimate;
- impacted products and orders are derived through the BOM and active orders;
- the cancelled control order is excluded;
- the recommendation maps to valid governed action parameters;
- no mitigation, transfer, execution, or audit rows are pre-seeded;
- read-only functions make no operational writes;
- the governed action workflow can run successfully from the golden state;
- expected-result fixtures and tests use the fixed execution clock;
- no random data or current-time dependency remains.

---

## 37. Final implementation principle

The seed is an executable specification of the demo.

```text
Fixed operational facts
+ fixed relationships
+ fixed dates
+ fixed function configuration
= repeatable impact and mitigation results
```

A developer should be able to inspect the seed manually and explain why each part, product, order, warehouse, purchase order, and action appears in the result.
