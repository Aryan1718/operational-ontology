# ruff: noqa: E501
"""Mitigation operational models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.risk import RiskEvent
    from app.models.supply_chain import (
        Part,
        Product,
        PurchaseOrder,
        Shipment,
        Supplier,
        User,
        Warehouse,
    )


class MitigationPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mitigation_plans"
    __table_args__ = (
        CheckConstraint(
            "plan_type IN ('reallocate_inventory', 'expedite_purchase_order', 'use_alternate_supplier', 'split_shipment', 'delay_order')",
            name="mitigation_plans_plan_type_allowed",
        ),
        CheckConstraint(
            "status IN ('draft', 'proposed', 'approved', 'rejected', 'executing', 'executed', 'cancelled')",
            name="mitigation_plans_status_allowed",
        ),
        CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="mitigation_plans_estimated_cost_nonnegative",
        ),
        CheckConstraint(
            "estimated_delay_reduction_days IS NULL OR estimated_delay_reduction_days >= 0",
            name="mitigation_plans_estimated_delay_reduction_nonnegative",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)",
            name="mitigation_plans_confidence_score_range",
        ),
        Index("idx_mitigation_plans_risk_event_id", "risk_event_id"),
        Index("idx_mitigation_plans_status", "status"),
        Index("idx_mitigation_plans_plan_type", "plan_type"),
        Index("idx_mitigation_plans_created_by", "created_by"),
        Index("idx_mitigation_plans_approved_by", "approved_by"),
    )

    mitigation_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    risk_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("risk_events.id"), nullable=False
    )
    plan_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estimated_delay_reduction_days: Mapped[int | None] = mapped_column(Integer)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column()

    risk_event: Mapped["RiskEvent"] = relationship(back_populates="mitigation_plans")
    created_by_user: Mapped["User | None"] = relationship(
        back_populates="created_mitigation_plans",
        foreign_keys=[created_by],
    )
    approved_by_user: Mapped["User | None"] = relationship(
        back_populates="approved_mitigation_plans",
        foreign_keys=[approved_by],
    )
    steps: Mapped[list["MitigationPlanStep"]] = relationship(
        back_populates="mitigation_plan"
    )


class MitigationPlanStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mitigation_plan_steps"
    __table_args__ = (
        CheckConstraint(
            "step_order > 0", name="mitigation_plan_steps_step_order_positive"
        ),
        CheckConstraint(
            "action_type IN ('reallocate_inventory', 'expedite_purchase_order', 'use_alternate_supplier', 'split_shipment', 'update_shipment_date', 'delay_order')",
            name="mitigation_plan_steps_action_type_allowed",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'executing', 'executed', 'failed', 'cancelled')",
            name="mitigation_plan_steps_status_allowed",
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity > 0",
            name="mitigation_plan_steps_quantity_positive",
        ),
        Index("idx_mitigation_plan_steps_plan_id", "mitigation_plan_id"),
        Index("idx_mitigation_plan_steps_status", "status"),
        Index("idx_mitigation_plan_steps_action_type", "action_type"),
        Index("idx_mitigation_plan_steps_source_warehouse_id", "source_warehouse_id"),
        Index("idx_mitigation_plan_steps_target_warehouse_id", "target_warehouse_id"),
    )

    mitigation_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("mitigation_plans.id"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source_warehouse_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warehouses.id")
    )
    target_warehouse_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warehouses.id")
    )
    supplier_id: Mapped[UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    purchase_order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("purchase_orders.id")
    )
    shipment_id: Mapped[UUID | None] = mapped_column(ForeignKey("shipments.id"))
    part_id: Mapped[UUID | None] = mapped_column(ForeignKey("parts.id"))
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column()

    mitigation_plan: Mapped[MitigationPlan] = relationship(back_populates="steps")
    source_warehouse: Mapped["Warehouse | None"] = relationship(
        back_populates="source_mitigation_steps",
        foreign_keys=[source_warehouse_id],
    )
    target_warehouse: Mapped["Warehouse | None"] = relationship(
        back_populates="target_mitigation_steps",
        foreign_keys=[target_warehouse_id],
    )
    supplier: Mapped["Supplier | None"] = relationship(
        back_populates="mitigation_plan_steps"
    )
    purchase_order: Mapped["PurchaseOrder | None"] = relationship(
        back_populates="mitigation_plan_steps"
    )
    shipment: Mapped["Shipment | None"] = relationship(
        back_populates="mitigation_plan_steps"
    )
    part: Mapped["Part | None"] = relationship(back_populates="mitigation_plan_steps")
    product: Mapped["Product | None"] = relationship(
        back_populates="mitigation_plan_steps"
    )


Index(
    "uq_mitigation_plan_steps_plan_step_order",
    MitigationPlanStep.mitigation_plan_id,
    MitigationPlanStep.step_order,
    unique=True,
)
