# ruff: noqa: E501
"""Supply-chain operational models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.mitigation import MitigationPlan, MitigationPlanStep
    from app.models.risk import RiskEvent


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('viewer', 'planner', 'admin')", name="users_role_allowed"
        ),
        Index("idx_users_role", "role"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)

    created_mitigation_plans: Mapped[list["MitigationPlan"]] = relationship(
        back_populates="created_by_user",
        foreign_keys="MitigationPlan.created_by",
    )
    approved_mitigation_plans: Mapped[list["MitigationPlan"]] = relationship(
        back_populates="approved_by_user",
        foreign_keys="MitigationPlan.approved_by",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="actor_user")


class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'blocked', 'delayed')",
            name="suppliers_status_allowed",
        ),
        CheckConstraint(
            "reliability_score IS NULL OR (reliability_score >= 0 AND reliability_score <= 100)",
            name="suppliers_reliability_score_range",
        ),
        CheckConstraint(
            "default_lead_time_days IS NULL OR default_lead_time_days >= 0",
            name="suppliers_default_lead_time_days_nonnegative",
        ),
        Index("idx_suppliers_status", "status"),
        Index("idx_suppliers_region", "region"),
    )

    supplier_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    reliability_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    default_lead_time_days: Mapped[int | None] = mapped_column(Integer)

    supplier_parts: Mapped[list["SupplierPart"]] = relationship(
        back_populates="supplier"
    )
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        back_populates="supplier"
    )
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="supplier")
    mitigation_plan_steps: Mapped[list["MitigationPlanStep"]] = relationship(
        back_populates="supplier"
    )


class Part(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "parts"
    __table_args__ = (
        CheckConstraint(
            "criticality IN ('low', 'medium', 'high', 'critical')",
            name="parts_criticality_allowed",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'discontinued')",
            name="parts_status_allowed",
        ),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0", name="parts_unit_cost_nonnegative"
        ),
        Index("idx_parts_category", "category"),
        Index("idx_parts_criticality", "criticality"),
        Index("idx_parts_status", "status"),
    )

    part_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    criticality: Mapped[str] = mapped_column(Text, nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(Text, nullable=False)

    supplier_parts: Mapped[list["SupplierPart"]] = relationship(back_populates="part")
    product_bom_items: Mapped[list["ProductBomItem"]] = relationship(
        back_populates="part"
    )
    inventory_items: Mapped[list["Inventory"]] = relationship(back_populates="part")
    purchase_order_items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="part"
    )
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="part")
    mitigation_plan_steps: Mapped[list["MitigationPlanStep"]] = relationship(
        back_populates="part"
    )


class SupplierPart(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "supplier_parts"
    __table_args__ = (
        UniqueConstraint("supplier_id", "part_id", name="uq_supplier_parts_supplier_part"),
        CheckConstraint(
            "status IN ('active', 'inactive', 'blocked')",
            name="supplier_parts_status_allowed",
        ),
        CheckConstraint(
            "lead_time_days IS NULL OR lead_time_days >= 0",
            name="supplier_parts_lead_time_days_nonnegative",
        ),
        CheckConstraint(
            "minimum_order_quantity IS NULL OR minimum_order_quantity >= 0",
            name="supplier_parts_minimum_order_quantity_nonnegative",
        ),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="supplier_parts_unit_cost_nonnegative",
        ),
        Index("idx_supplier_parts_supplier_id", "supplier_id"),
        Index("idx_supplier_parts_part_id", "part_id"),
        Index("idx_supplier_parts_primary", "part_id", "is_primary_supplier"),
    )

    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False
    )
    part_id: Mapped[UUID] = mapped_column(ForeignKey("parts.id"), nullable=False)
    supplier_part_code: Mapped[str | None] = mapped_column(Text)
    is_primary_supplier: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    minimum_order_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(Text, nullable=False)

    supplier: Mapped[Supplier] = relationship(back_populates="supplier_parts")
    part: Mapped[Part] = relationship(back_populates="supplier_parts")



class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'discontinued')",
            name="products_status_allowed",
        ),
        Index("idx_products_category", "category"),
        Index("idx_products_status", "status"),
    )

    product_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)

    product_bom_items: Mapped[list["ProductBomItem"]] = relationship(
        back_populates="product"
    )
    inventory_items: Mapped[list["Inventory"]] = relationship(back_populates="product")
    customer_order_items: Mapped[list["CustomerOrderItem"]] = relationship(
        back_populates="product"
    )
    mitigation_plan_steps: Mapped[list["MitigationPlanStep"]] = relationship(
        back_populates="product"
    )


class ProductBomItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_bom_items"
    __table_args__ = (
        UniqueConstraint("product_id", "part_id", name="uq_product_bom_items_product_part"),
        CheckConstraint(
            "quantity_required > 0", name="product_bom_items_quantity_required_positive"
        ),
        Index("idx_product_bom_items_product_id", "product_id"),
        Index("idx_product_bom_items_part_id", "part_id"),
        Index("idx_product_bom_items_part_critical", "part_id", "is_critical"),
    )

    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    part_id: Mapped[UUID] = mapped_column(ForeignKey("parts.id"), nullable=False)
    quantity_required: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    product: Mapped[Product] = relationship(back_populates="product_bom_items")
    part: Mapped[Part] = relationship(back_populates="product_bom_items")



class Warehouse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'blocked')",
            name="warehouses_status_allowed",
        ),
        Index("idx_warehouses_region", "region"),
        Index("idx_warehouses_status", "status"),
    )

    warehouse_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)

    inventory_items: Mapped[list["Inventory"]] = relationship(
        back_populates="warehouse"
    )
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="warehouse")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="warehouse")
    source_mitigation_steps: Mapped[list["MitigationPlanStep"]] = relationship(
        back_populates="source_warehouse",
        foreign_keys="MitigationPlanStep.source_warehouse_id",
    )
    target_mitigation_steps: Mapped[list["MitigationPlanStep"]] = relationship(
        back_populates="target_warehouse",
        foreign_keys="MitigationPlanStep.target_warehouse_id",
    )


class Inventory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('part', 'product')", name="inventory_item_type_allowed"
        ),
        CheckConstraint(
            "on_hand_quantity >= 0", name="inventory_on_hand_quantity_nonnegative"
        ),
        CheckConstraint(
            "reserved_quantity >= 0", name="inventory_reserved_quantity_nonnegative"
        ),
        CheckConstraint(
            "safety_stock_quantity >= 0",
            name="inventory_safety_stock_quantity_nonnegative",
        ),
        CheckConstraint(
            "((item_type = 'part' AND part_id IS NOT NULL AND product_id IS NULL) OR (item_type = 'product' AND product_id IS NOT NULL AND part_id IS NULL))",
            name="inventory_single_item_reference",
        ),
        Index("idx_inventory_warehouse_id", "warehouse_id"),
        Index(
            "idx_inventory_part_id",
            "part_id",
            postgresql_where=text("item_type = 'part'"),
        ),
        Index(
            "idx_inventory_product_id",
            "product_id",
            postgresql_where=text("item_type = 'product'"),
        ),
        Index("idx_inventory_item_type", "item_type"),
    )

    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouses.id"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    part_id: Mapped[UUID | None] = mapped_column(ForeignKey("parts.id"))
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"))
    on_hand_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    safety_stock_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("now()"), onupdate=text("now()")
    )

    warehouse: Mapped[Warehouse] = relationship(back_populates="inventory_items")
    part: Mapped[Part | None] = relationship(back_populates="inventory_items")
    product: Mapped[Product | None] = relationship(back_populates="inventory_items")


Index(
    "uniq_inventory_warehouse_part",
    Inventory.warehouse_id,
    Inventory.part_id,
    unique=True,
    postgresql_where=text("item_type = 'part'"),
)
Index(
    "uniq_inventory_warehouse_product",
    Inventory.warehouse_id,
    Inventory.product_id,
    unique=True,
    postgresql_where=text("item_type = 'product'"),
)


class CustomerOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_orders"
    __table_args__ = (
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'critical')",
            name="customer_orders_priority_allowed",
        ),
        CheckConstraint(
            "status IN ('open', 'allocated', 'partially_allocated', 'shipped', 'delivered', 'delayed', 'cancelled')",
            name="customer_orders_status_allowed",
        ),
        Index("idx_customer_orders_status", "status"),
        Index("idx_customer_orders_priority", "priority"),
        Index("idx_customer_orders_requested_delivery_date", "requested_delivery_date"),
        Index(
            "idx_customer_orders_priority_date", "priority", "requested_delivery_date"
        ),
    )

    order_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    requested_delivery_date: Mapped[date] = mapped_column(Date, nullable=False)

    items: Mapped[list["CustomerOrderItem"]] = relationship(back_populates="order")
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="order")


class CustomerOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_order_items"
    __table_args__ = (
        CheckConstraint(
            "quantity_ordered > 0",
            name="customer_order_items_quantity_ordered_positive",
        ),
        CheckConstraint(
            "quantity_allocated >= 0",
            name="customer_order_items_quantity_allocated_nonnegative",
        ),
        CheckConstraint(
            "quantity_allocated <= quantity_ordered",
            name="customer_order_items_quantity_allocated_lte_ordered",
        ),
        Index("idx_customer_order_items_order_id", "order_id"),
        Index("idx_customer_order_items_product_id", "product_id"),
    )

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_orders.id"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity_allocated: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )

    order: Mapped[CustomerOrder] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="customer_order_items")


class Shipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'allocated', 'in_transit', 'delivered', 'delayed', 'cancelled')",
            name="shipments_status_allowed",
        ),
        Index("idx_shipments_order_id", "order_id"),
        Index("idx_shipments_warehouse_id", "warehouse_id"),
        Index("idx_shipments_status", "status"),
        Index("idx_shipments_planned_delivery_date", "planned_delivery_date"),
    )

    shipment_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_orders.id"), nullable=False
    )
    warehouse_id: Mapped[UUID | None] = mapped_column(ForeignKey("warehouses.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    carrier: Mapped[str | None] = mapped_column(Text)
    tracking_number: Mapped[str | None] = mapped_column(Text)
    planned_ship_date: Mapped[date | None] = mapped_column(Date)
    actual_ship_date: Mapped[date | None] = mapped_column(Date)
    planned_delivery_date: Mapped[date | None] = mapped_column(Date)
    actual_delivery_date: Mapped[date | None] = mapped_column(Date)

    order: Mapped[CustomerOrder] = relationship(back_populates="shipments")
    warehouse: Mapped[Warehouse | None] = relationship(back_populates="shipments")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="shipment")
    mitigation_plan_steps: Mapped[list["MitigationPlanStep"]] = relationship(
        back_populates="shipment"
    )


class PurchaseOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'open', 'confirmed', 'partially_received', 'received', 'delayed', 'cancelled')",
            name="purchase_orders_status_allowed",
        ),
        Index("idx_purchase_orders_supplier_id", "supplier_id"),
        Index("idx_purchase_orders_status", "status"),
        Index("idx_purchase_orders_expected_delivery_date", "expected_delivery_date"),
    )

    purchase_order_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    actual_delivery_date: Mapped[date | None] = mapped_column(Date)
    expedited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    expedite_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    supplier: Mapped[Supplier] = relationship(back_populates="purchase_orders")
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order"
    )
    mitigation_plan_steps: Mapped[list["MitigationPlanStep"]] = relationship(
        back_populates="purchase_order"
    )


class PurchaseOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        CheckConstraint(
            "quantity_ordered > 0",
            name="purchase_order_items_quantity_ordered_positive",
        ),
        CheckConstraint(
            "quantity_received >= 0",
            name="purchase_order_items_quantity_received_nonnegative",
        ),
        CheckConstraint(
            "quantity_received <= quantity_ordered",
            name="purchase_order_items_quantity_received_lte_ordered",
        ),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0",
            name="purchase_order_items_unit_cost_nonnegative",
        ),
        Index("idx_purchase_order_items_purchase_order_id", "purchase_order_id"),
        Index("idx_purchase_order_items_part_id", "part_id"),
    )

    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False
    )
    part_id: Mapped[UUID] = mapped_column(ForeignKey("parts.id"), nullable=False)
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
    part: Mapped[Part] = relationship(back_populates="purchase_order_items")
