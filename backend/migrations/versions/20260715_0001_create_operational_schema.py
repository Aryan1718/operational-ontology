# ruff: noqa: E501
"""Create operational PostgreSQL schema.

Revision ID: 20260715_0001
Revises:
Create Date: 2026-07-15 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "role IN ('viewer', 'planner', 'admin')", name="ck_users_users_role_allowed"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("idx_users_role", "users", ["role"])

    op.create_table(
        "suppliers",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("supplier_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("country", sa.Text()),
        sa.Column("region", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reliability_score", sa.Numeric(5, 2)),
        sa.Column("default_lead_time_days", sa.Integer()),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'blocked', 'delayed')",
            name="ck_suppliers_suppliers_status_allowed",
        ),
        sa.CheckConstraint(
            "reliability_score IS NULL OR (reliability_score >= 0 AND reliability_score <= 100)",
            name="ck_suppliers_suppliers_reliability_score_range",
        ),
        sa.CheckConstraint(
            "default_lead_time_days IS NULL OR default_lead_time_days >= 0",
            name="ck_suppliers_suppliers_default_lead_time_days_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_suppliers"),
        sa.UniqueConstraint("supplier_code", name="uq_suppliers_supplier_code"),
    )
    op.create_index("idx_suppliers_region", "suppliers", ["region"])
    op.create_index("idx_suppliers_status", "suppliers", ["status"])

    op.create_table(
        "parts",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("part_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text()),
        sa.Column("criticality", sa.Text(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2)),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "criticality IN ('low', 'medium', 'high', 'critical')",
            name="ck_parts_parts_criticality_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'discontinued')",
            name="ck_parts_parts_status_allowed",
        ),
        sa.CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_parts_parts_unit_cost_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_parts"),
        sa.UniqueConstraint("part_code", name="uq_parts_part_code"),
    )
    op.create_index("idx_parts_category", "parts", ["category"])
    op.create_index("idx_parts_criticality", "parts", ["criticality"])
    op.create_index("idx_parts_status", "parts", ["status"])

    op.create_table(
        "products",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("product_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'discontinued')",
            name="ck_products_products_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("product_code", name="uq_products_product_code"),
    )
    op.create_index("idx_products_category", "products", ["category"])
    op.create_index("idx_products_status", "products", ["status"])

    op.create_table(
        "warehouses",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("warehouse_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text()),
        sa.Column("state", sa.Text()),
        sa.Column("country", sa.Text()),
        sa.Column("region", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'blocked')",
            name="ck_warehouses_warehouses_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_warehouses"),
        sa.UniqueConstraint("warehouse_code", name="uq_warehouses_warehouse_code"),
    )
    op.create_index("idx_warehouses_region", "warehouses", ["region"])
    op.create_index("idx_warehouses_status", "warehouses", ["status"])
    op.create_table(
        "supplier_parts",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("supplier_id", UUID, nullable=False),
        sa.Column("part_id", UUID, nullable=False),
        sa.Column("supplier_part_code", sa.Text()),
        sa.Column(
            "is_primary_supplier",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("lead_time_days", sa.Integer()),
        sa.Column("minimum_order_quantity", sa.Numeric(12, 2)),
        sa.Column("unit_cost", sa.Numeric(12, 2)),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'blocked')",
            name="ck_supplier_parts_supplier_parts_status_allowed",
        ),
        sa.CheckConstraint(
            "lead_time_days IS NULL OR lead_time_days >= 0",
            name="ck_supplier_parts_supplier_parts_lead_time_days_nonnegative",
        ),
        sa.CheckConstraint(
            "minimum_order_quantity IS NULL OR minimum_order_quantity >= 0",
            name="ck_supplier_parts_supplier_parts_minimum_order_quantity_nonnegative",
        ),
        sa.CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_supplier_parts_supplier_parts_unit_cost_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"], ["parts.id"], name="fk_supplier_parts_part_id_parts"
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_supplier_parts_supplier_id_suppliers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_supplier_parts"),
    )
    op.create_index("idx_supplier_parts_part_id", "supplier_parts", ["part_id"])
    op.create_index(
        "idx_supplier_parts_primary",
        "supplier_parts",
        ["part_id", "is_primary_supplier"],
    )
    op.create_index("idx_supplier_parts_supplier_id", "supplier_parts", ["supplier_id"])
    op.create_index(
        "uq_supplier_parts_supplier_part",
        "supplier_parts",
        ["supplier_id", "part_id"],
        unique=True,
    )

    op.create_table(
        "product_bom_items",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("part_id", UUID, nullable=False),
        sa.Column("quantity_required", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "is_critical", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "quantity_required > 0",
            name="ck_product_bom_items_product_bom_items_quantity_required_positive",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"], ["parts.id"], name="fk_product_bom_items_part_id_parts"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_product_bom_items_product_id_products",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_product_bom_items"),
    )
    op.create_index(
        "idx_product_bom_items_part_critical",
        "product_bom_items",
        ["part_id", "is_critical"],
    )
    op.create_index("idx_product_bom_items_part_id", "product_bom_items", ["part_id"])
    op.create_index(
        "idx_product_bom_items_product_id", "product_bom_items", ["product_id"]
    )
    op.create_index(
        "uq_product_bom_items_product_part",
        "product_bom_items",
        ["product_id", "part_id"],
        unique=True,
    )

    op.create_table(
        "inventory",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("warehouse_id", UUID, nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("part_id", UUID),
        sa.Column("product_id", UUID),
        sa.Column("on_hand_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "reserved_quantity",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "safety_stock_quantity",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "item_type IN ('part', 'product')",
            name="ck_inventory_inventory_item_type_allowed",
        ),
        sa.CheckConstraint(
            "on_hand_quantity >= 0",
            name="ck_inventory_inventory_on_hand_quantity_nonnegative",
        ),
        sa.CheckConstraint(
            "reserved_quantity >= 0",
            name="ck_inventory_inventory_reserved_quantity_nonnegative",
        ),
        sa.CheckConstraint(
            "safety_stock_quantity >= 0",
            name="ck_inventory_inventory_safety_stock_quantity_nonnegative",
        ),
        sa.CheckConstraint(
            "((item_type = 'part' AND part_id IS NOT NULL AND product_id IS NULL) OR (item_type = 'product' AND product_id IS NOT NULL AND part_id IS NULL))",
            name="ck_inventory_inventory_single_item_reference",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"], ["parts.id"], name="fk_inventory_part_id_parts"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_inventory_product_id_products"
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_inventory_warehouse_id_warehouses",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory"),
    )
    op.create_index("idx_inventory_item_type", "inventory", ["item_type"])
    op.create_index(
        "idx_inventory_part_id",
        "inventory",
        ["part_id"],
        postgresql_where=sa.text("item_type = 'part'"),
    )
    op.create_index(
        "idx_inventory_product_id",
        "inventory",
        ["product_id"],
        postgresql_where=sa.text("item_type = 'product'"),
    )
    op.create_index("idx_inventory_warehouse_id", "inventory", ["warehouse_id"])
    op.create_index(
        "uniq_inventory_warehouse_part",
        "inventory",
        ["warehouse_id", "part_id"],
        unique=True,
        postgresql_where=sa.text("item_type = 'part'"),
    )
    op.create_index(
        "uniq_inventory_warehouse_product",
        "inventory",
        ["warehouse_id", "product_id"],
        unique=True,
        postgresql_where=sa.text("item_type = 'product'"),
    )

    op.create_table(
        "customer_orders",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("order_code", sa.Text(), nullable=False),
        sa.Column("customer_name", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("requested_delivery_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'critical')",
            name="ck_customer_orders_customer_orders_priority_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'allocated', 'partially_allocated', 'shipped', 'delivered', 'delayed', 'cancelled')",
            name="ck_customer_orders_customer_orders_status_allowed",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_orders"),
        sa.UniqueConstraint("order_code", name="uq_customer_orders_order_code"),
    )
    op.create_index("idx_customer_orders_priority", "customer_orders", ["priority"])
    op.create_index(
        "idx_customer_orders_priority_date",
        "customer_orders",
        ["priority", "requested_delivery_date"],
    )
    op.create_index(
        "idx_customer_orders_requested_delivery_date",
        "customer_orders",
        ["requested_delivery_date"],
    )
    op.create_index("idx_customer_orders_status", "customer_orders", ["status"])

    op.create_table(
        "customer_order_items",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "quantity_allocated",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "quantity_ordered > 0",
            name="ck_customer_order_items_customer_order_items_quantity_ordered_positive",
        ),
        sa.CheckConstraint(
            "quantity_allocated >= 0",
            name="ck_customer_order_items_customer_order_items_quantity_allocated_nonnegative",
        ),
        sa.CheckConstraint(
            "quantity_allocated <= quantity_ordered",
            name="ck_customer_order_items_customer_order_items_quantity_allocated_lte_ordered",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["customer_orders.id"],
            name="fk_customer_order_items_order_id_customer_orders",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_customer_order_items_product_id_products",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_order_items"),
    )
    op.create_index(
        "idx_customer_order_items_order_id", "customer_order_items", ["order_id"]
    )
    op.create_index(
        "idx_customer_order_items_product_id", "customer_order_items", ["product_id"]
    )
    op.create_table(
        "shipments",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("shipment_code", sa.Text(), nullable=False),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("warehouse_id", UUID),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("carrier", sa.Text()),
        sa.Column("tracking_number", sa.Text()),
        sa.Column("planned_ship_date", sa.Date()),
        sa.Column("actual_ship_date", sa.Date()),
        sa.Column("planned_delivery_date", sa.Date()),
        sa.Column("actual_delivery_date", sa.Date()),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'allocated', 'in_transit', 'delivered', 'delayed', 'cancelled')",
            name="ck_shipments_shipments_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["customer_orders.id"],
            name="fk_shipments_order_id_customer_orders",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_shipments_warehouse_id_warehouses",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_shipments"),
        sa.UniqueConstraint("shipment_code", name="uq_shipments_shipment_code"),
    )
    op.create_index("idx_shipments_order_id", "shipments", ["order_id"])
    op.create_index(
        "idx_shipments_planned_delivery_date", "shipments", ["planned_delivery_date"]
    )
    op.create_index("idx_shipments_status", "shipments", ["status"])
    op.create_index("idx_shipments_warehouse_id", "shipments", ["warehouse_id"])

    op.create_table(
        "purchase_orders",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("purchase_order_code", sa.Text(), nullable=False),
        sa.Column("supplier_id", UUID, nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date()),
        sa.Column("actual_delivery_date", sa.Date()),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'open', 'confirmed', 'partially_received', 'received', 'delayed', 'cancelled')",
            name="ck_purchase_orders_purchase_orders_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_purchase_orders_supplier_id_suppliers",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_purchase_orders"),
        sa.UniqueConstraint(
            "purchase_order_code", name="uq_purchase_orders_purchase_order_code"
        ),
    )
    op.create_index(
        "idx_purchase_orders_expected_delivery_date",
        "purchase_orders",
        ["expected_delivery_date"],
    )
    op.create_index("idx_purchase_orders_status", "purchase_orders", ["status"])
    op.create_index(
        "idx_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"]
    )

    op.create_table(
        "purchase_order_items",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("purchase_order_id", UUID, nullable=False),
        sa.Column("part_id", UUID, nullable=False),
        sa.Column("quantity_ordered", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "quantity_received",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("unit_cost", sa.Numeric(12, 2)),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "quantity_ordered > 0",
            name="ck_purchase_order_items_purchase_order_items_quantity_ordered_positive",
        ),
        sa.CheckConstraint(
            "quantity_received >= 0",
            name="ck_purchase_order_items_purchase_order_items_quantity_received_nonnegative",
        ),
        sa.CheckConstraint(
            "quantity_received <= quantity_ordered",
            name="ck_purchase_order_items_purchase_order_items_quantity_received_lte_ordered",
        ),
        sa.CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="ck_purchase_order_items_purchase_order_items_unit_cost_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"], ["parts.id"], name="fk_purchase_order_items_part_id_parts"
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name="fk_purchase_order_items_purchase_order_id_purchase_orders",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_purchase_order_items"),
    )
    op.create_index(
        "idx_purchase_order_items_part_id", "purchase_order_items", ["part_id"]
    )
    op.create_index(
        "idx_purchase_order_items_purchase_order_id",
        "purchase_order_items",
        ["purchase_order_id"],
    )

    op.create_table(
        "risk_events",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("risk_code", sa.Text(), nullable=False),
        sa.Column("risk_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("supplier_id", UUID),
        sa.Column("part_id", UUID),
        sa.Column("warehouse_id", UUID),
        sa.Column("shipment_id", UUID),
        sa.Column("delay_days", sa.Integer()),
        sa.Column("description", sa.Text()),
        sa.Column(
            "detected_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("resolved_at", TIMESTAMPTZ),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "risk_type IN ('supplier_delay', 'part_shortage', 'warehouse_outage', 'shipment_delay', 'quality_issue', 'demand_spike')",
            name="ck_risk_events_risk_events_risk_type_allowed",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_risk_events_risk_events_severity_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'mitigating', 'resolved', 'cancelled')",
            name="ck_risk_events_risk_events_status_allowed",
        ),
        sa.CheckConstraint(
            "delay_days IS NULL OR delay_days >= 0",
            name="ck_risk_events_risk_events_delay_days_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"], ["parts.id"], name="fk_risk_events_part_id_parts"
        ),
        sa.ForeignKeyConstraint(
            ["shipment_id"],
            ["shipments.id"],
            name="fk_risk_events_shipment_id_shipments",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_risk_events_supplier_id_suppliers",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name="fk_risk_events_warehouse_id_warehouses",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_events"),
        sa.UniqueConstraint("risk_code", name="uq_risk_events_risk_code"),
    )
    op.create_index("idx_risk_events_detected_at", "risk_events", ["detected_at"])
    op.create_index("idx_risk_events_part_id", "risk_events", ["part_id"])
    op.create_index("idx_risk_events_risk_type", "risk_events", ["risk_type"])
    op.create_index("idx_risk_events_severity", "risk_events", ["severity"])
    op.create_index("idx_risk_events_status", "risk_events", ["status"])
    op.create_index("idx_risk_events_supplier_id", "risk_events", ["supplier_id"])
    op.create_table(
        "risk_event_impacts",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("risk_event_id", UUID, nullable=False),
        sa.Column("impacted_object_type", sa.Text(), nullable=False),
        sa.Column("impacted_object_id", UUID, nullable=False),
        sa.Column("impact_level", sa.Text(), nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 2)),
        sa.Column("estimated_delay_days", sa.Integer()),
        sa.Column("impact_reason", sa.Text()),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "impacted_object_type IN ('supplier', 'part', 'product', 'warehouse', 'customer_order', 'shipment', 'purchase_order')",
            name="ck_risk_event_impacts_risk_event_impacts_object_type_allowed",
        ),
        sa.CheckConstraint(
            "impact_level IN ('low', 'medium', 'high', 'critical')",
            name="ck_risk_event_impacts_risk_event_impacts_impact_level_allowed",
        ),
        sa.CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="ck_risk_event_impacts_risk_event_impacts_risk_score_range",
        ),
        sa.CheckConstraint(
            "estimated_delay_days IS NULL OR estimated_delay_days >= 0",
            name="ck_risk_event_impacts_risk_event_impacts_estimated_delay_days_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["risk_event_id"],
            ["risk_events.id"],
            name="fk_risk_event_impacts_risk_event_id_risk_events",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_event_impacts"),
    )
    op.create_index(
        "idx_risk_event_impacts_level", "risk_event_impacts", ["impact_level"]
    )
    op.create_index(
        "idx_risk_event_impacts_object",
        "risk_event_impacts",
        ["impacted_object_type", "impacted_object_id"],
    )
    op.create_index(
        "idx_risk_event_impacts_risk_event_id", "risk_event_impacts", ["risk_event_id"]
    )
    op.create_index(
        "uq_risk_event_impacts_event_object",
        "risk_event_impacts",
        ["risk_event_id", "impacted_object_type", "impacted_object_id"],
        unique=True,
    )

    op.create_table(
        "mitigation_plans",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("mitigation_code", sa.Text(), nullable=False),
        sa.Column("risk_event_id", UUID, nullable=False),
        sa.Column("plan_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("estimated_cost", sa.Numeric(12, 2)),
        sa.Column("estimated_delay_reduction_days", sa.Integer()),
        sa.Column("confidence_score", sa.Numeric(5, 2)),
        sa.Column("created_by", UUID),
        sa.Column("approved_by", UUID),
        sa.Column("approved_at", TIMESTAMPTZ),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "plan_type IN ('reallocate_inventory', 'expedite_purchase_order', 'use_alternate_supplier', 'split_shipment', 'delay_order')",
            name="ck_mitigation_plans_mitigation_plans_plan_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'proposed', 'approved', 'rejected', 'executing', 'executed', 'cancelled')",
            name="ck_mitigation_plans_mitigation_plans_status_allowed",
        ),
        sa.CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="ck_mitigation_plans_mitigation_plans_estimated_cost_nonnegative",
        ),
        sa.CheckConstraint(
            "estimated_delay_reduction_days IS NULL OR estimated_delay_reduction_days >= 0",
            name="ck_mitigation_plans_mitigation_plans_estimated_delay_reduction_nonnegative",
        ),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)",
            name="ck_mitigation_plans_mitigation_plans_confidence_score_range",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"], name="fk_mitigation_plans_approved_by_users"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_mitigation_plans_created_by_users"
        ),
        sa.ForeignKeyConstraint(
            ["risk_event_id"],
            ["risk_events.id"],
            name="fk_mitigation_plans_risk_event_id_risk_events",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mitigation_plans"),
        sa.UniqueConstraint(
            "mitigation_code", name="uq_mitigation_plans_mitigation_code"
        ),
    )
    op.create_index(
        "idx_mitigation_plans_approved_by", "mitigation_plans", ["approved_by"]
    )
    op.create_index(
        "idx_mitigation_plans_created_by", "mitigation_plans", ["created_by"]
    )
    op.create_index("idx_mitigation_plans_plan_type", "mitigation_plans", ["plan_type"])
    op.create_index(
        "idx_mitigation_plans_risk_event_id", "mitigation_plans", ["risk_event_id"]
    )
    op.create_index("idx_mitigation_plans_status", "mitigation_plans", ["status"])

    op.create_table(
        "mitigation_plan_steps",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("mitigation_plan_id", UUID, nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source_warehouse_id", UUID),
        sa.Column("target_warehouse_id", UUID),
        sa.Column("supplier_id", UUID),
        sa.Column("purchase_order_id", UUID),
        sa.Column("shipment_id", UUID),
        sa.Column("part_id", UUID),
        sa.Column("product_id", UUID),
        sa.Column("quantity", sa.Numeric(12, 2)),
        sa.Column("notes", sa.Text()),
        sa.Column("executed_at", TIMESTAMPTZ),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "step_order > 0",
            name="ck_mitigation_plan_steps_mitigation_plan_steps_step_order_positive",
        ),
        sa.CheckConstraint(
            "action_type IN ('reallocate_inventory', 'expedite_purchase_order', 'use_alternate_supplier', 'split_shipment', 'update_shipment_date', 'delay_order')",
            name="ck_mitigation_plan_steps_mitigation_plan_steps_action_type_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'executing', 'executed', 'failed', 'cancelled')",
            name="ck_mitigation_plan_steps_mitigation_plan_steps_status_allowed",
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity > 0",
            name="ck_mitigation_plan_steps_mitigation_plan_steps_quantity_positive",
        ),
        sa.ForeignKeyConstraint(
            ["mitigation_plan_id"],
            ["mitigation_plans.id"],
            name="fk_mitigation_plan_steps_mitigation_plan_id_mitigation_plans",
        ),
        sa.ForeignKeyConstraint(
            ["part_id"], ["parts.id"], name="fk_mitigation_plan_steps_part_id_parts"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_mitigation_plan_steps_product_id_products",
        ),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"],
            ["purchase_orders.id"],
            name="fk_mitigation_plan_steps_purchase_order_id_purchase_orders",
        ),
        sa.ForeignKeyConstraint(
            ["shipment_id"],
            ["shipments.id"],
            name="fk_mitigation_plan_steps_shipment_id_shipments",
        ),
        sa.ForeignKeyConstraint(
            ["source_warehouse_id"],
            ["warehouses.id"],
            name="fk_mitigation_plan_steps_source_warehouse_id_warehouses",
        ),
        sa.ForeignKeyConstraint(
            ["supplier_id"],
            ["suppliers.id"],
            name="fk_mitigation_plan_steps_supplier_id_suppliers",
        ),
        sa.ForeignKeyConstraint(
            ["target_warehouse_id"],
            ["warehouses.id"],
            name="fk_mitigation_plan_steps_target_warehouse_id_warehouses",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mitigation_plan_steps"),
    )
    op.create_index(
        "idx_mitigation_plan_steps_action_type",
        "mitigation_plan_steps",
        ["action_type"],
    )
    op.create_index(
        "idx_mitigation_plan_steps_plan_id",
        "mitigation_plan_steps",
        ["mitigation_plan_id"],
    )
    op.create_index(
        "idx_mitigation_plan_steps_source_warehouse_id",
        "mitigation_plan_steps",
        ["source_warehouse_id"],
    )
    op.create_index(
        "idx_mitigation_plan_steps_status", "mitigation_plan_steps", ["status"]
    )
    op.create_index(
        "idx_mitigation_plan_steps_target_warehouse_id",
        "mitigation_plan_steps",
        ["target_warehouse_id"],
    )
    op.create_index(
        "uq_mitigation_plan_steps_plan_step_order",
        "mitigation_plan_steps",
        ["mitigation_plan_id", "step_order"],
        unique=True,
    )

    op.create_table(
        "audit_logs",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("actor_user_id", UUID),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("object_id", UUID, nullable=False),
        sa.Column("previous_value", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "created_at", TIMESTAMPTZ, nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "object_type IN ('supplier', 'part', 'product', 'warehouse', 'inventory', 'customer_order', 'shipment', 'purchase_order', 'risk_event', 'risk_event_impact', 'mitigation_plan', 'mitigation_plan_step')",
            name="ck_audit_logs_audit_logs_object_type_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], name="fk_audit_logs_actor_user_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index("idx_audit_logs_action_type", "audit_logs", ["action_type"])
    op.create_index("idx_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("idx_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("idx_audit_logs_object", "audit_logs", ["object_type", "object_id"])


def downgrade() -> None:
    op.drop_index("idx_audit_logs_object", table_name="audit_logs")
    op.drop_index("idx_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_logs_actor_user_id", table_name="audit_logs")
    op.drop_index("idx_audit_logs_action_type", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index(
        "uq_mitigation_plan_steps_plan_step_order", table_name="mitigation_plan_steps"
    )
    op.drop_index(
        "idx_mitigation_plan_steps_target_warehouse_id",
        table_name="mitigation_plan_steps",
    )
    op.drop_index(
        "idx_mitigation_plan_steps_status", table_name="mitigation_plan_steps"
    )
    op.drop_index(
        "idx_mitigation_plan_steps_source_warehouse_id",
        table_name="mitigation_plan_steps",
    )
    op.drop_index(
        "idx_mitigation_plan_steps_plan_id", table_name="mitigation_plan_steps"
    )
    op.drop_index(
        "idx_mitigation_plan_steps_action_type", table_name="mitigation_plan_steps"
    )
    op.drop_table("mitigation_plan_steps")

    op.drop_index("idx_mitigation_plans_status", table_name="mitigation_plans")
    op.drop_index("idx_mitigation_plans_risk_event_id", table_name="mitigation_plans")
    op.drop_index("idx_mitigation_plans_plan_type", table_name="mitigation_plans")
    op.drop_index("idx_mitigation_plans_created_by", table_name="mitigation_plans")
    op.drop_index("idx_mitigation_plans_approved_by", table_name="mitigation_plans")
    op.drop_table("mitigation_plans")

    op.drop_index("uq_risk_event_impacts_event_object", table_name="risk_event_impacts")
    op.drop_index(
        "idx_risk_event_impacts_risk_event_id", table_name="risk_event_impacts"
    )
    op.drop_index("idx_risk_event_impacts_object", table_name="risk_event_impacts")
    op.drop_index("idx_risk_event_impacts_level", table_name="risk_event_impacts")
    op.drop_table("risk_event_impacts")
    op.drop_index("idx_risk_events_supplier_id", table_name="risk_events")
    op.drop_index("idx_risk_events_status", table_name="risk_events")
    op.drop_index("idx_risk_events_severity", table_name="risk_events")
    op.drop_index("idx_risk_events_risk_type", table_name="risk_events")
    op.drop_index("idx_risk_events_part_id", table_name="risk_events")
    op.drop_index("idx_risk_events_detected_at", table_name="risk_events")
    op.drop_table("risk_events")

    op.drop_index(
        "idx_purchase_order_items_purchase_order_id", table_name="purchase_order_items"
    )
    op.drop_index("idx_purchase_order_items_part_id", table_name="purchase_order_items")
    op.drop_table("purchase_order_items")

    op.drop_index("idx_purchase_orders_supplier_id", table_name="purchase_orders")
    op.drop_index("idx_purchase_orders_status", table_name="purchase_orders")
    op.drop_index(
        "idx_purchase_orders_expected_delivery_date", table_name="purchase_orders"
    )
    op.drop_table("purchase_orders")

    op.drop_index("idx_shipments_warehouse_id", table_name="shipments")
    op.drop_index("idx_shipments_status", table_name="shipments")
    op.drop_index("idx_shipments_planned_delivery_date", table_name="shipments")
    op.drop_index("idx_shipments_order_id", table_name="shipments")
    op.drop_table("shipments")

    op.drop_index(
        "idx_customer_order_items_product_id", table_name="customer_order_items"
    )
    op.drop_index(
        "idx_customer_order_items_order_id", table_name="customer_order_items"
    )
    op.drop_table("customer_order_items")

    op.drop_index("idx_customer_orders_status", table_name="customer_orders")
    op.drop_index(
        "idx_customer_orders_requested_delivery_date", table_name="customer_orders"
    )
    op.drop_index("idx_customer_orders_priority_date", table_name="customer_orders")
    op.drop_index("idx_customer_orders_priority", table_name="customer_orders")
    op.drop_table("customer_orders")

    op.drop_index("uniq_inventory_warehouse_product", table_name="inventory")
    op.drop_index("uniq_inventory_warehouse_part", table_name="inventory")
    op.drop_index("idx_inventory_warehouse_id", table_name="inventory")
    op.drop_index("idx_inventory_product_id", table_name="inventory")
    op.drop_index("idx_inventory_part_id", table_name="inventory")
    op.drop_index("idx_inventory_item_type", table_name="inventory")
    op.drop_table("inventory")

    op.drop_index("uq_product_bom_items_product_part", table_name="product_bom_items")
    op.drop_index("idx_product_bom_items_product_id", table_name="product_bom_items")
    op.drop_index("idx_product_bom_items_part_id", table_name="product_bom_items")
    op.drop_index("idx_product_bom_items_part_critical", table_name="product_bom_items")
    op.drop_table("product_bom_items")

    op.drop_index("uq_supplier_parts_supplier_part", table_name="supplier_parts")
    op.drop_index("idx_supplier_parts_supplier_id", table_name="supplier_parts")
    op.drop_index("idx_supplier_parts_primary", table_name="supplier_parts")
    op.drop_index("idx_supplier_parts_part_id", table_name="supplier_parts")
    op.drop_table("supplier_parts")

    op.drop_index("idx_warehouses_status", table_name="warehouses")
    op.drop_index("idx_warehouses_region", table_name="warehouses")
    op.drop_table("warehouses")

    op.drop_index("idx_products_status", table_name="products")
    op.drop_index("idx_products_category", table_name="products")
    op.drop_table("products")

    op.drop_index("idx_parts_status", table_name="parts")
    op.drop_index("idx_parts_criticality", table_name="parts")
    op.drop_index("idx_parts_category", table_name="parts")
    op.drop_table("parts")

    op.drop_index("idx_suppliers_status", table_name="suppliers")
    op.drop_index("idx_suppliers_region", table_name="suppliers")
    op.drop_table("suppliers")

    op.drop_index("idx_users_role", table_name="users")
    op.drop_table("users")
