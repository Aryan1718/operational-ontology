# operational-ontology Database Context

## Purpose

This file defines the **core operational PostgreSQL database design** for the operational-ontology project.

operational-ontology is a supply-chain disruption response system. The database should support this business workflow:

```text
Supplier delay detected
→ impacted parts found
→ impacted products found
→ impacted customer orders found
→ warehouse inventory checked
→ mitigation plan created
→ planner approves / executes action
→ audit log records the change
```

## Important Scope Decision

This file only covers the **basic operational database tables**.

Do **not** create ontology metadata tables yet.

Do not create these tables in this migration:

```text
ontology_object_types
ontology_property_types
ontology_link_types
ontology_action_types
ontology_function_types
ontology_permissions
ai_tool_calls
mcp_tools
```

Those will be designed later.

For now, create only the supply-chain operational tables listed in this file.

---

# General PostgreSQL Rules

## Primary Keys

Use UUID primary keys for all tables.

Recommended:

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid()
```

Migration should enable the PostgreSQL extension if needed:

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

## Timestamps

Use `TIMESTAMPTZ` for timestamp columns.

Recommended defaults:

```sql
created_at TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
```

## Naming

Use snake_case table names and column names.

## Money / Quantity Types

Use numeric types instead of floats.

Recommended:

```sql
NUMERIC(12,2)
```

Use this for quantities, costs, and scores unless noted otherwise.

## Status Columns

Use simple `TEXT` columns with `CHECK` constraints for MVP.

Avoid creating PostgreSQL enum types for now because text check constraints are easier to update during early development.

---

# Required Tables

The MVP database should include these tables:

```text
users
suppliers
parts
supplier_parts
products
product_bom_items
warehouses
inventory
customer_orders
customer_order_items
shipments
purchase_orders
purchase_order_items
risk_events
risk_event_impacts
mitigation_plans
mitigation_plan_steps
audit_logs
```

---

# 1. users

## Purpose

Stores application users who create risk events, approve mitigation plans, execute actions, or appear in audit logs.

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| name | TEXT | yes | User display name |
| email | TEXT | yes | Unique user email |
| role | TEXT | yes | Simple MVP role |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed role values

```text
viewer
planner
admin
```

## Constraints

```sql
UNIQUE (email)
CHECK (role IN ('viewer', 'planner', 'admin'))
```

## Suggested Indexes

```sql
CREATE INDEX idx_users_role ON users(role);
```

---

# 2. suppliers

## Purpose

Stores suppliers/vendors that provide parts.

A supplier delay is one of the main starting points for the disruption workflow.

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| supplier_code | TEXT | yes | Human-readable unique code, example: S-102 |
| name | TEXT | yes | Supplier name |
| country | TEXT | no | Supplier country |
| region | TEXT | no | Region such as West, East, APAC, EMEA |
| status | TEXT | yes | Supplier state |
| reliability_score | NUMERIC(5,2) | no | Example: 82.50 |
| default_lead_time_days | INT | no | Default expected lead time |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed status values

```text
active
inactive
blocked
delayed
```

## Constraints

```sql
UNIQUE (supplier_code)
CHECK (status IN ('active', 'inactive', 'blocked', 'delayed'))
CHECK (reliability_score IS NULL OR (reliability_score >= 0 AND reliability_score <= 100))
CHECK (default_lead_time_days IS NULL OR default_lead_time_days >= 0)
```

## Suggested Indexes

```sql
CREATE INDEX idx_suppliers_status ON suppliers(status);
CREATE INDEX idx_suppliers_region ON suppliers(region);
```

---

# 3. parts

## Purpose

Stores raw parts or components supplied by suppliers and used inside products.

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| part_code | TEXT | yes | Human-readable unique code, example: P-501 |
| name | TEXT | yes | Part name |
| category | TEXT | no | Example: battery, chip, sensor, packaging |
| criticality | TEXT | yes | Business criticality level |
| unit_cost | NUMERIC(12,2) | no | Default part cost |
| status | TEXT | yes | Part state |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed criticality values

```text
low
medium
high
critical
```

## Allowed status values

```text
active
inactive
discontinued
```

## Constraints

```sql
UNIQUE (part_code)
CHECK (criticality IN ('low', 'medium', 'high', 'critical'))
CHECK (status IN ('active', 'inactive', 'discontinued'))
CHECK (unit_cost IS NULL OR unit_cost >= 0)
```

## Suggested Indexes

```sql
CREATE INDEX idx_parts_category ON parts(category);
CREATE INDEX idx_parts_criticality ON parts(criticality);
CREATE INDEX idx_parts_status ON parts(status);
```

---

# 4. supplier_parts

## Purpose

Join table connecting suppliers to the parts they can provide.

This table answers:

```text
Which parts does Supplier S-102 provide?
Which suppliers can provide Part P-501?
Which supplier is the primary supplier for a part?
```

## Relationship

```text
suppliers 1..many → supplier_parts ← many..1 parts
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| supplier_id | UUID | yes | FK to suppliers.id |
| part_id | UUID | yes | FK to parts.id |
| supplier_part_code | TEXT | no | Supplier-specific part code |
| is_primary_supplier | BOOLEAN | yes | Default false |
| lead_time_days | INT | no | Supplier-specific lead time |
| minimum_order_quantity | NUMERIC(12,2) | no | MOQ |
| unit_cost | NUMERIC(12,2) | no | Supplier-specific part cost |
| status | TEXT | yes | Relationship status |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed status values

```text
active
inactive
blocked
```

## Constraints

```sql
UNIQUE (supplier_id, part_id)
FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
FOREIGN KEY (part_id) REFERENCES parts(id)
CHECK (status IN ('active', 'inactive', 'blocked'))
CHECK (lead_time_days IS NULL OR lead_time_days >= 0)
CHECK (minimum_order_quantity IS NULL OR minimum_order_quantity >= 0)
CHECK (unit_cost IS NULL OR unit_cost >= 0)
```

## Suggested Indexes

```sql
CREATE INDEX idx_supplier_parts_supplier_id ON supplier_parts(supplier_id);
CREATE INDEX idx_supplier_parts_part_id ON supplier_parts(part_id);
CREATE INDEX idx_supplier_parts_primary ON supplier_parts(part_id, is_primary_supplier);
```

---

# 5. products

## Purpose

Stores finished products that customers order.

Products are built from parts through the bill-of-materials table.

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| product_code | TEXT | yes | Human-readable unique code, example: PROD-10 |
| name | TEXT | yes | Product name |
| category | TEXT | no | Product category |
| status | TEXT | yes | Product state |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed status values

```text
active
inactive
discontinued
```

## Constraints

```sql
UNIQUE (product_code)
CHECK (status IN ('active', 'inactive', 'discontinued'))
```

## Suggested Indexes

```sql
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_status ON products(status);
```

---

# 6. product_bom_items

## Purpose

Stores bill-of-materials relationships.

BOM means Bill of Materials.

This table defines which parts are required to build each product.

This table answers:

```text
Which products depend on this delayed part?
Which parts are needed to build this product?
How many units of each part are required per product?
```

## Relationship

```text
products 1..many → product_bom_items ← many..1 parts
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| product_id | UUID | yes | FK to products.id |
| part_id | UUID | yes | FK to parts.id |
| quantity_required | NUMERIC(12,2) | yes | Quantity of this part required per product unit |
| is_critical | BOOLEAN | yes | Default true |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Constraints

```sql
UNIQUE (product_id, part_id)
FOREIGN KEY (product_id) REFERENCES products(id)
FOREIGN KEY (part_id) REFERENCES parts(id)
CHECK (quantity_required > 0)
```

## Suggested Indexes

```sql
CREATE INDEX idx_product_bom_items_product_id ON product_bom_items(product_id);
CREATE INDEX idx_product_bom_items_part_id ON product_bom_items(part_id);
CREATE INDEX idx_product_bom_items_part_critical ON product_bom_items(part_id, is_critical);
```

---

# 7. warehouses

## Purpose

Stores warehouse or distribution center locations.

Warehouses store part inventory and product inventory.

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| warehouse_code | TEXT | yes | Human-readable unique code, example: W-1 |
| name | TEXT | yes | Warehouse name |
| city | TEXT | no | City |
| state | TEXT | no | State/province |
| country | TEXT | no | Country |
| region | TEXT | no | Operational region |
| status | TEXT | yes | Warehouse state |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed status values

```text
active
inactive
blocked
```

## Constraints

```sql
UNIQUE (warehouse_code)
CHECK (status IN ('active', 'inactive', 'blocked'))
```

## Suggested Indexes

```sql
CREATE INDEX idx_warehouses_region ON warehouses(region);
CREATE INDEX idx_warehouses_status ON warehouses(status);
```

---

# 8. inventory

## Purpose

Stores available inventory for both parts and finished products at warehouses.

For MVP, use one generic inventory table with an `item_type`.

This table answers:

```text
How much stock is available in each warehouse?
Can another warehouse help fulfill an at-risk order?
Do we have enough parts/products after accounting for reserved quantity and safety stock?
```

## Relationship

```text
warehouses 1..many → inventory
parts 1..many → inventory, when item_type = 'part'
products 1..many → inventory, when item_type = 'product'
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| warehouse_id | UUID | yes | FK to warehouses.id |
| item_type | TEXT | yes | Either part or product |
| part_id | UUID | no | FK to parts.id; required when item_type = part |
| product_id | UUID | no | FK to products.id; required when item_type = product |
| on_hand_quantity | NUMERIC(12,2) | yes | Physical stock |
| reserved_quantity | NUMERIC(12,2) | yes | Stock already reserved |
| safety_stock_quantity | NUMERIC(12,2) | yes | Minimum buffer |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed item_type values

```text
part
product
```

## Available Quantity Formula

Application logic can calculate:

```text
available_quantity = on_hand_quantity - reserved_quantity - safety_stock_quantity
```

Do not store `available_quantity` as a normal column in MVP. Calculate it in queries or views later.

## Constraints

```sql
FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
FOREIGN KEY (part_id) REFERENCES parts(id)
FOREIGN KEY (product_id) REFERENCES products(id)

CHECK (item_type IN ('part', 'product'))
CHECK (on_hand_quantity >= 0)
CHECK (reserved_quantity >= 0)
CHECK (safety_stock_quantity >= 0)

-- Exactly one item reference must be present based on item_type:
CHECK (
    (item_type = 'part' AND part_id IS NOT NULL AND product_id IS NULL)
    OR
    (item_type = 'product' AND product_id IS NOT NULL AND part_id IS NULL)
)
```

## Uniqueness

PostgreSQL cannot create one simple unique constraint for nullable part/product columns in a clean way.

Use partial unique indexes:

```sql
CREATE UNIQUE INDEX uniq_inventory_warehouse_part
ON inventory(warehouse_id, part_id)
WHERE item_type = 'part';

CREATE UNIQUE INDEX uniq_inventory_warehouse_product
ON inventory(warehouse_id, product_id)
WHERE item_type = 'product';
```

## Suggested Indexes

```sql
CREATE INDEX idx_inventory_warehouse_id ON inventory(warehouse_id);
CREATE INDEX idx_inventory_part_id ON inventory(part_id) WHERE item_type = 'part';
CREATE INDEX idx_inventory_product_id ON inventory(product_id) WHERE item_type = 'product';
CREATE INDEX idx_inventory_item_type ON inventory(item_type);
```

---

# 9. customer_orders

## Purpose

Stores customer orders.

Customer orders represent the real business impact of a supply-chain disruption.

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| order_code | TEXT | yes | Human-readable unique code, example: ORD-881 |
| customer_name | TEXT | yes | Customer/account name |
| priority | TEXT | yes | Order priority |
| status | TEXT | yes | Order state |
| requested_delivery_date | DATE | yes | Customer requested delivery date |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed priority values

```text
low
normal
high
critical
```

## Allowed status values

```text
open
allocated
partially_allocated
shipped
delivered
delayed
cancelled
```

## Constraints

```sql
UNIQUE (order_code)
CHECK (priority IN ('low', 'normal', 'high', 'critical'))
CHECK (status IN ('open', 'allocated', 'partially_allocated', 'shipped', 'delivered', 'delayed', 'cancelled'))
```

## Suggested Indexes

```sql
CREATE INDEX idx_customer_orders_status ON customer_orders(status);
CREATE INDEX idx_customer_orders_priority ON customer_orders(priority);
CREATE INDEX idx_customer_orders_requested_delivery_date ON customer_orders(requested_delivery_date);
CREATE INDEX idx_customer_orders_priority_date ON customer_orders(priority, requested_delivery_date);
```

---

# 10. customer_order_items

## Purpose

Stores products inside each customer order.

This table answers:

```text
Which orders require this product?
How many units of this product did the customer order?
How much has already been allocated?
```

## Relationship

```text
customer_orders 1..many → customer_order_items ← many..1 products
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| order_id | UUID | yes | FK to customer_orders.id |
| product_id | UUID | yes | FK to products.id |
| quantity_ordered | NUMERIC(12,2) | yes | Ordered quantity |
| quantity_allocated | NUMERIC(12,2) | yes | Allocated quantity, default 0 |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Constraints

```sql
FOREIGN KEY (order_id) REFERENCES customer_orders(id)
FOREIGN KEY (product_id) REFERENCES products(id)
CHECK (quantity_ordered > 0)
CHECK (quantity_allocated >= 0)
CHECK (quantity_allocated <= quantity_ordered)
```

## Suggested Indexes

```sql
CREATE INDEX idx_customer_order_items_order_id ON customer_order_items(order_id);
CREATE INDEX idx_customer_order_items_product_id ON customer_order_items(product_id);
```

---

# 11. shipments

## Purpose

Stores shipments that fulfill customer orders.

Shipments may be delayed, rerouted, split, or updated as part of a mitigation plan.

## Relationship

```text
customer_orders 1..many → shipments
warehouses 1..many → shipments
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| shipment_code | TEXT | yes | Human-readable unique code, example: SH-991 |
| order_id | UUID | yes | FK to customer_orders.id |
| warehouse_id | UUID | no | FK to warehouses.id |
| status | TEXT | yes | Shipment state |
| carrier | TEXT | no | Carrier name |
| tracking_number | TEXT | no | External tracking number |
| planned_ship_date | DATE | no | Planned ship date |
| actual_ship_date | DATE | no | Actual ship date |
| planned_delivery_date | DATE | no | Planned delivery date |
| actual_delivery_date | DATE | no | Actual delivery date |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed status values

```text
planned
allocated
in_transit
delivered
delayed
cancelled
```

## Constraints

```sql
UNIQUE (shipment_code)
FOREIGN KEY (order_id) REFERENCES customer_orders(id)
FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
CHECK (status IN ('planned', 'allocated', 'in_transit', 'delivered', 'delayed', 'cancelled'))
```

## Suggested Indexes

```sql
CREATE INDEX idx_shipments_order_id ON shipments(order_id);
CREATE INDEX idx_shipments_warehouse_id ON shipments(warehouse_id);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_planned_delivery_date ON shipments(planned_delivery_date);
```

---

# 12. purchase_orders

## Purpose

Stores purchase orders sent to suppliers.

This table helps understand incoming supply and whether an existing order can be expedited.

## Relationship

```text
suppliers 1..many → purchase_orders
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| purchase_order_code | TEXT | yes | Human-readable unique code, example: PO-44 |
| supplier_id | UUID | yes | FK to suppliers.id |
| status | TEXT | yes | Purchase order state |
| order_date | DATE | yes | Date PO was placed |
| expected_delivery_date | DATE | no | Expected arrival date |
| actual_delivery_date | DATE | no | Actual arrival date |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed status values

```text
draft
open
confirmed
partially_received
received
delayed
cancelled
```

## Constraints

```sql
UNIQUE (purchase_order_code)
FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
CHECK (status IN ('draft', 'open', 'confirmed', 'partially_received', 'received', 'delayed', 'cancelled'))
```

## Suggested Indexes

```sql
CREATE INDEX idx_purchase_orders_supplier_id ON purchase_orders(supplier_id);
CREATE INDEX idx_purchase_orders_status ON purchase_orders(status);
CREATE INDEX idx_purchase_orders_expected_delivery_date ON purchase_orders(expected_delivery_date);
```

---

# 13. purchase_order_items

## Purpose

Stores parts inside each purchase order.

This table answers:

```text
Which parts are expected from this supplier?
How much quantity was ordered?
How much quantity has been received?
```

## Relationship

```text
purchase_orders 1..many → purchase_order_items ← many..1 parts
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| purchase_order_id | UUID | yes | FK to purchase_orders.id |
| part_id | UUID | yes | FK to parts.id |
| quantity_ordered | NUMERIC(12,2) | yes | Ordered part quantity |
| quantity_received | NUMERIC(12,2) | yes | Received quantity, default 0 |
| unit_cost | NUMERIC(12,2) | no | Cost at time of purchase |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Constraints

```sql
FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id)
FOREIGN KEY (part_id) REFERENCES parts(id)
CHECK (quantity_ordered > 0)
CHECK (quantity_received >= 0)
CHECK (quantity_received <= quantity_ordered)
CHECK (unit_cost IS NULL OR unit_cost >= 0)
```

## Suggested Indexes

```sql
CREATE INDEX idx_purchase_order_items_purchase_order_id ON purchase_order_items(purchase_order_id);
CREATE INDEX idx_purchase_order_items_part_id ON purchase_order_items(part_id);
```

---

# 14. risk_events

## Purpose

Stores supply-chain disruptions.

Examples:

```text
Supplier delay
Part shortage
Warehouse outage
Shipment delay
Quality issue
```

For the main demo, a supplier delay should create a risk event.

## Relationship

A risk event may optionally reference one main supplier, part, warehouse, or shipment.

The broader set of impacted objects should be stored in `risk_event_impacts`.

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| risk_code | TEXT | yes | Human-readable unique code, example: RISK-1001 |
| risk_type | TEXT | yes | Type of risk |
| severity | TEXT | yes | Risk severity |
| status | TEXT | yes | Risk state |
| supplier_id | UUID | no | FK to suppliers.id |
| part_id | UUID | no | FK to parts.id |
| warehouse_id | UUID | no | FK to warehouses.id |
| shipment_id | UUID | no | FK to shipments.id |
| delay_days | INT | no | Delay duration if relevant |
| description | TEXT | no | Human-readable explanation |
| detected_at | TIMESTAMPTZ | yes | Default now() |
| resolved_at | TIMESTAMPTZ | no | Set when resolved |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed risk_type values

```text
supplier_delay
part_shortage
warehouse_outage
shipment_delay
quality_issue
demand_spike
```

## Allowed severity values

```text
low
medium
high
critical
```

## Allowed status values

```text
open
investigating
mitigating
resolved
cancelled
```

## Constraints

```sql
UNIQUE (risk_code)
FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
FOREIGN KEY (part_id) REFERENCES parts(id)
FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
FOREIGN KEY (shipment_id) REFERENCES shipments(id)
CHECK (risk_type IN ('supplier_delay', 'part_shortage', 'warehouse_outage', 'shipment_delay', 'quality_issue', 'demand_spike'))
CHECK (severity IN ('low', 'medium', 'high', 'critical'))
CHECK (status IN ('open', 'investigating', 'mitigating', 'resolved', 'cancelled'))
CHECK (delay_days IS NULL OR delay_days >= 0)
```

## Suggested Indexes

```sql
CREATE INDEX idx_risk_events_risk_type ON risk_events(risk_type);
CREATE INDEX idx_risk_events_status ON risk_events(status);
CREATE INDEX idx_risk_events_severity ON risk_events(severity);
CREATE INDEX idx_risk_events_supplier_id ON risk_events(supplier_id);
CREATE INDEX idx_risk_events_part_id ON risk_events(part_id);
CREATE INDEX idx_risk_events_detected_at ON risk_events(detected_at);
```

---

# 15. risk_event_impacts

## Purpose

Stores which objects are affected by a risk event.

One risk event can impact many parts, products, customer orders, shipments, warehouses, or purchase orders.

This table is intentionally generic because it stores impacts across multiple object types.

## Example

```text
Risk RISK-1001 impacts Part P-501
Risk RISK-1001 impacts Product PROD-10
Risk RISK-1001 impacts CustomerOrder ORD-881
Risk RISK-1001 impacts Shipment SH-991
```

## Relationship

```text
risk_events 1..many → risk_event_impacts
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| risk_event_id | UUID | yes | FK to risk_events.id |
| impacted_object_type | TEXT | yes | Type of impacted object |
| impacted_object_id | UUID | yes | UUID of impacted object |
| impact_level | TEXT | yes | Impact level |
| risk_score | NUMERIC(5,2) | no | 0 to 100 |
| estimated_delay_days | INT | no | Estimated delay caused |
| impact_reason | TEXT | no | Why this object is impacted |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed impacted_object_type values

```text
supplier
part
product
warehouse
customer_order
shipment
purchase_order
```

## Allowed impact_level values

```text
low
medium
high
critical
```

## Constraints

```sql
FOREIGN KEY (risk_event_id) REFERENCES risk_events(id)
UNIQUE (risk_event_id, impacted_object_type, impacted_object_id)
CHECK (impacted_object_type IN ('supplier', 'part', 'product', 'warehouse', 'customer_order', 'shipment', 'purchase_order'))
CHECK (impact_level IN ('low', 'medium', 'high', 'critical'))
CHECK (risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100))
CHECK (estimated_delay_days IS NULL OR estimated_delay_days >= 0)
```

## Suggested Indexes

```sql
CREATE INDEX idx_risk_event_impacts_risk_event_id ON risk_event_impacts(risk_event_id);
CREATE INDEX idx_risk_event_impacts_object ON risk_event_impacts(impacted_object_type, impacted_object_id);
CREATE INDEX idx_risk_event_impacts_level ON risk_event_impacts(impact_level);
```

---

# 16. mitigation_plans

## Purpose

Stores recommended plans to reduce the impact of a risk event.

A risk event can have multiple mitigation plans.

Example plan types:

```text
Reallocate inventory from another warehouse
Expedite a purchase order
Use an alternate supplier
Split a shipment
Delay a low-priority order
```

## Relationship

```text
risk_events 1..many → mitigation_plans
users 1..many → mitigation_plans, through created_by and approved_by
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| mitigation_code | TEXT | yes | Human-readable unique code, example: MIT-1001 |
| risk_event_id | UUID | yes | FK to risk_events.id |
| plan_type | TEXT | yes | Type of mitigation |
| status | TEXT | yes | Plan status |
| recommended_action | TEXT | yes | Short action description |
| explanation | TEXT | no | Why this plan is recommended |
| estimated_cost | NUMERIC(12,2) | no | Estimated cost |
| estimated_delay_reduction_days | INT | no | Expected delay reduction |
| confidence_score | NUMERIC(5,2) | no | 0 to 100 |
| created_by | UUID | no | FK to users.id |
| approved_by | UUID | no | FK to users.id |
| approved_at | TIMESTAMPTZ | no | Approval timestamp |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed plan_type values

```text
reallocate_inventory
expedite_purchase_order
use_alternate_supplier
split_shipment
delay_order
```

## Allowed status values

```text
draft
proposed
approved
rejected
executing
executed
cancelled
```

## Constraints

```sql
UNIQUE (mitigation_code)
FOREIGN KEY (risk_event_id) REFERENCES risk_events(id)
FOREIGN KEY (created_by) REFERENCES users(id)
FOREIGN KEY (approved_by) REFERENCES users(id)
CHECK (plan_type IN ('reallocate_inventory', 'expedite_purchase_order', 'use_alternate_supplier', 'split_shipment', 'delay_order'))
CHECK (status IN ('draft', 'proposed', 'approved', 'rejected', 'executing', 'executed', 'cancelled'))
CHECK (estimated_cost IS NULL OR estimated_cost >= 0)
CHECK (estimated_delay_reduction_days IS NULL OR estimated_delay_reduction_days >= 0)
CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100))
```

## Suggested Indexes

```sql
CREATE INDEX idx_mitigation_plans_risk_event_id ON mitigation_plans(risk_event_id);
CREATE INDEX idx_mitigation_plans_status ON mitigation_plans(status);
CREATE INDEX idx_mitigation_plans_plan_type ON mitigation_plans(plan_type);
CREATE INDEX idx_mitigation_plans_created_by ON mitigation_plans(created_by);
CREATE INDEX idx_mitigation_plans_approved_by ON mitigation_plans(approved_by);
```

---

# 17. mitigation_plan_steps

## Purpose

Stores executable steps inside a mitigation plan.

A single mitigation plan may require multiple operational steps.

Example:

```text
1. Reallocate 50 units of Product PROD-10 from Warehouse W-2 to Warehouse W-1
2. Expedite Purchase Order PO-44
3. Update Shipment SH-991 planned delivery date
```

## Relationship

```text
mitigation_plans 1..many → mitigation_plan_steps
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| mitigation_plan_id | UUID | yes | FK to mitigation_plans.id |
| step_order | INT | yes | Order inside the plan |
| action_type | TEXT | yes | Action to perform |
| status | TEXT | yes | Step status |
| source_warehouse_id | UUID | no | FK to warehouses.id |
| target_warehouse_id | UUID | no | FK to warehouses.id |
| supplier_id | UUID | no | FK to suppliers.id |
| purchase_order_id | UUID | no | FK to purchase_orders.id |
| shipment_id | UUID | no | FK to shipments.id |
| part_id | UUID | no | FK to parts.id |
| product_id | UUID | no | FK to products.id |
| quantity | NUMERIC(12,2) | no | Quantity affected |
| notes | TEXT | no | Step explanation |
| executed_at | TIMESTAMPTZ | no | Set when step is executed |
| created_at | TIMESTAMPTZ | yes | Default now() |
| updated_at | TIMESTAMPTZ | yes | Default now() |

## Allowed action_type values

```text
reallocate_inventory
expedite_purchase_order
use_alternate_supplier
split_shipment
update_shipment_date
delay_order
```

## Allowed status values

```text
pending
approved
executing
executed
failed
cancelled
```

## Constraints

```sql
FOREIGN KEY (mitigation_plan_id) REFERENCES mitigation_plans(id)
FOREIGN KEY (source_warehouse_id) REFERENCES warehouses(id)
FOREIGN KEY (target_warehouse_id) REFERENCES warehouses(id)
FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(id)
FOREIGN KEY (shipment_id) REFERENCES shipments(id)
FOREIGN KEY (part_id) REFERENCES parts(id)
FOREIGN KEY (product_id) REFERENCES products(id)

UNIQUE (mitigation_plan_id, step_order)

CHECK (step_order > 0)
CHECK (action_type IN ('reallocate_inventory', 'expedite_purchase_order', 'use_alternate_supplier', 'split_shipment', 'update_shipment_date', 'delay_order'))
CHECK (status IN ('pending', 'approved', 'executing', 'executed', 'failed', 'cancelled'))
CHECK (quantity IS NULL OR quantity > 0)
```

## Suggested Indexes

```sql
CREATE INDEX idx_mitigation_plan_steps_plan_id ON mitigation_plan_steps(mitigation_plan_id);
CREATE INDEX idx_mitigation_plan_steps_status ON mitigation_plan_steps(status);
CREATE INDEX idx_mitigation_plan_steps_action_type ON mitigation_plan_steps(action_type);
CREATE INDEX idx_mitigation_plan_steps_source_warehouse_id ON mitigation_plan_steps(source_warehouse_id);
CREATE INDEX idx_mitigation_plan_steps_target_warehouse_id ON mitigation_plan_steps(target_warehouse_id);
```

---

# 18. audit_logs

## Purpose

Stores important changes and actions.

This table is required because the system should track who changed what, when, and why.

Examples:

```text
User created risk event RISK-1001
User approved mitigation plan MIT-1001
System updated shipment SH-991
System reallocated inventory from Warehouse W-2 to Warehouse W-1
```

## Columns

| Column | Type | Required | Notes |
|---|---:|---:|---|
| id | UUID | yes | Primary key |
| actor_user_id | UUID | no | FK to users.id; nullable for system actions |
| action_type | TEXT | yes | Example: create_risk_event, approve_mitigation_plan |
| object_type | TEXT | yes | Type of changed object |
| object_id | UUID | yes | UUID of changed object |
| previous_value | JSONB | no | Snapshot before change |
| new_value | JSONB | no | Snapshot after change |
| reason | TEXT | no | Human/system explanation |
| created_at | TIMESTAMPTZ | yes | Default now() |

## Suggested action_type values

These can stay flexible as text for MVP.

```text
create_risk_event
update_risk_event
create_mitigation_plan
approve_mitigation_plan
reject_mitigation_plan
execute_mitigation_step
update_inventory
update_shipment
create_purchase_order
expedite_purchase_order
```

## Allowed object_type values

```text
supplier
part
product
warehouse
inventory
customer_order
shipment
purchase_order
risk_event
risk_event_impact
mitigation_plan
mitigation_plan_step
```

## Constraints

```sql
FOREIGN KEY (actor_user_id) REFERENCES users(id)
CHECK (object_type IN ('supplier', 'part', 'product', 'warehouse', 'inventory', 'customer_order', 'shipment', 'purchase_order', 'risk_event', 'risk_event_impact', 'mitigation_plan', 'mitigation_plan_step'))
```

## Suggested Indexes

```sql
CREATE INDEX idx_audit_logs_actor_user_id ON audit_logs(actor_user_id);
CREATE INDEX idx_audit_logs_action_type ON audit_logs(action_type);
CREATE INDEX idx_audit_logs_object ON audit_logs(object_type, object_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

---

# Main Relationship Flow

The most important query path is:

```text
Supplier
→ supplier_parts
→ Part
→ product_bom_items
→ Product
→ customer_order_items
→ CustomerOrder
→ Shipments
```

This path supports the main demo question:

```text
If Supplier S-102 is delayed, which customer orders are impacted?
```

---

# Risk Workflow Relationship Flow

```text
RiskEvent
→ RiskEventImpact
→ MitigationPlan
→ MitigationPlanStep
→ AuditLog
```

This path supports the operational workflow:

```text
Create risk event
→ calculate impacted objects
→ create mitigation plan
→ approve plan
→ execute plan steps
→ audit everything
```

---

# Recommended Table Creation Order

Use this order in the migration to avoid foreign key problems:

```text
1. users
2. suppliers
3. parts
4. products
5. warehouses
6. supplier_parts
7. product_bom_items
8. inventory
9. customer_orders
10. customer_order_items
11. shipments
12. purchase_orders
13. purchase_order_items
14. risk_events
15. risk_event_impacts
16. mitigation_plans
17. mitigation_plan_steps
18. audit_logs
```

---

# Expected MVP Queries

The database should make these queries straightforward.

## Query 1: Find parts supplied by a delayed supplier

```text
Supplier → supplier_parts → parts
```

## Query 2: Find products affected by delayed parts

```text
parts → product_bom_items → products
```

## Query 3: Find customer orders affected by products

```text
products → customer_order_items → customer_orders
```

## Query 4: Check available inventory across warehouses

```text
inventory + warehouses
```

Available inventory:

```text
on_hand_quantity - reserved_quantity - safety_stock_quantity
```

## Query 5: Store risk event impact results

```text
risk_events → risk_event_impacts
```

## Query 6: Store mitigation recommendation

```text
risk_events → mitigation_plans → mitigation_plan_steps
```

## Query 7: Record approved or executed actions

```text
audit_logs
```

---

# MVP Data Example

The seed data should include at least one controlled demo scenario:

```text
Supplier S-102 is delayed by 5 days.

S-102 supplies:
- P-501 Battery Cell
- P-502 Sensor Module

Affected products:
- PROD-10 Smart Hub
- PROD-11 Industrial Tracker

Affected customer orders:
- ORD-881
- ORD-882
- ORD-883

Warehouse W-2 has available stock that can help fulfill one or more affected orders.

Mitigation plan:
- Reallocate inventory from W-2 to W-1
- Expedite existing purchase order PO-44
- Update shipment SH-991
```

---

# Design Notes for Codex

When creating the migration:

1. Create all tables using PostgreSQL.
2. Use UUID primary keys.
3. Enable `pgcrypto`.
4. Use `TIMESTAMPTZ` for timestamps.
5. Use `NUMERIC(12,2)` for quantities and costs.
6. Use `NUMERIC(5,2)` for scores.
7. Use `TEXT` plus `CHECK` constraints for statuses and types.
8. Add foreign keys according to this file.
9. Add unique constraints for human-readable codes.
10. Add suggested indexes.
11. Do not create ontology metadata tables yet.
12. Do not create AI/MCP-related tables yet.
13. Keep the schema simple and operational.
14. Use nullable foreign keys only where the risk or mitigation object may reference different entity types.
15. For `inventory`, use partial unique indexes for part/product uniqueness.

---

# Final MVP Table List

```text
users
suppliers
parts
supplier_parts
products
product_bom_items
warehouses
inventory
customer_orders
customer_order_items
shipments
purchase_orders
purchase_order_items
risk_events
risk_event_impacts
mitigation_plans
mitigation_plan_steps
audit_logs
```
