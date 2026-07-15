"""Model metadata tests."""

from typing import Any, cast

from sqlalchemy import Index
from sqlalchemy.dialects import postgresql

from app.db.base import Base
from app.models.supply_chain import (
    CustomerOrder,
    CustomerOrderItem,
    Supplier,
    SupplierPart,
)

EXPECTED_TABLES = {
    "users",
    "suppliers",
    "parts",
    "supplier_parts",
    "products",
    "product_bom_items",
    "warehouses",
    "inventory",
    "customer_orders",
    "customer_order_items",
    "shipments",
    "purchase_orders",
    "purchase_order_items",
    "risk_events",
    "risk_event_impacts",
    "mitigation_plans",
    "mitigation_plan_steps",
    "audit_logs",
}


def test_all_expected_tables_are_registered() -> None:
    """Metadata should include every documented operational table."""
    assert EXPECTED_TABLES.issubset(Base.metadata.tables.keys())


def test_inventory_partial_unique_indexes_are_registered() -> None:
    """Inventory should use partial unique indexes for part and product rows."""
    inventory_table = Base.metadata.tables["inventory"]
    dialect = cast(Any, postgresql.dialect())  # type: ignore[no-untyped-call]

    warehouse_part_index = next(
        index
        for index in inventory_table.indexes
        if index.name == "uniq_inventory_warehouse_part"
    )
    warehouse_product_index = next(
        index
        for index in inventory_table.indexes
        if index.name == "uniq_inventory_warehouse_product"
    )

    assert isinstance(warehouse_part_index, Index)
    assert isinstance(warehouse_product_index, Index)
    assert "item_type = 'part'" in str(
        warehouse_part_index.dialect_options["postgresql"]["where"].compile(
            dialect=dialect
        )
    )
    assert "item_type = 'product'" in str(
        warehouse_product_index.dialect_options["postgresql"]["where"].compile(
            dialect=dialect
        )
    )


def test_supplier_and_customer_order_relationships_are_mapped() -> None:
    """Key ORM relationships should point to the documented association models."""
    supplier_parts_relationship = Supplier.__mapper__.relationships["supplier_parts"]
    customer_order_items_relationship = CustomerOrder.__mapper__.relationships["items"]

    assert supplier_parts_relationship.mapper.class_ is SupplierPart
    assert customer_order_items_relationship.mapper.class_ is CustomerOrderItem
