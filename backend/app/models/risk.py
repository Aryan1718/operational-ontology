# ruff: noqa: E501
"""Risk-event operational models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
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
    from app.models.mitigation import MitigationPlan
    from app.models.supply_chain import Part, Shipment, Supplier, Warehouse


class RiskEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        CheckConstraint(
            "risk_type IN ('supplier_delay', 'part_shortage', 'warehouse_outage', 'shipment_delay', 'quality_issue', 'demand_spike')",
            name="risk_events_risk_type_allowed",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="risk_events_severity_allowed",
        ),
        CheckConstraint(
            "status IN ('open', 'investigating', 'mitigating', 'resolved', 'cancelled')",
            name="risk_events_status_allowed",
        ),
        CheckConstraint(
            "delay_days IS NULL OR delay_days >= 0",
            name="risk_events_delay_days_nonnegative",
        ),
        Index("idx_risk_events_risk_type", "risk_type"),
        Index("idx_risk_events_status", "status"),
        Index("idx_risk_events_severity", "severity"),
        Index("idx_risk_events_supplier_id", "supplier_id"),
        Index("idx_risk_events_part_id", "part_id"),
        Index("idx_risk_events_detected_at", "detected_at"),
    )

    risk_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    risk_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    supplier_id: Mapped[UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    part_id: Mapped[UUID | None] = mapped_column(ForeignKey("parts.id"))
    warehouse_id: Mapped[UUID | None] = mapped_column(ForeignKey("warehouses.id"))
    shipment_id: Mapped[UUID | None] = mapped_column(ForeignKey("shipments.id"))
    delay_days: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("now()")
    )
    resolved_at: Mapped[datetime | None] = mapped_column()

    supplier: Mapped["Supplier | None"] = relationship(back_populates="risk_events")
    part: Mapped["Part | None"] = relationship(back_populates="risk_events")
    warehouse: Mapped["Warehouse | None"] = relationship(back_populates="risk_events")
    shipment: Mapped["Shipment | None"] = relationship(back_populates="risk_events")
    impacts: Mapped[list["RiskEventImpact"]] = relationship(back_populates="risk_event")
    mitigation_plans: Mapped[list["MitigationPlan"]] = relationship(
        back_populates="risk_event"
    )


class RiskEventImpact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risk_event_impacts"
    __table_args__ = (
        UniqueConstraint(
            "risk_event_id",
            "impacted_object_type",
            "impacted_object_id",
            name="uq_risk_event_impacts_event_object",
        ),
        CheckConstraint(
            "impacted_object_type IN ('supplier', 'part', 'product', 'warehouse', 'customer_order', 'shipment', 'purchase_order')",
            name="risk_event_impacts_object_type_allowed",
        ),
        CheckConstraint(
            "impact_level IN ('low', 'medium', 'high', 'critical')",
            name="risk_event_impacts_impact_level_allowed",
        ),
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="risk_event_impacts_risk_score_range",
        ),
        CheckConstraint(
            "estimated_delay_days IS NULL OR estimated_delay_days >= 0",
            name="risk_event_impacts_estimated_delay_days_nonnegative",
        ),
        Index("idx_risk_event_impacts_risk_event_id", "risk_event_id"),
        Index(
            "idx_risk_event_impacts_object",
            "impacted_object_type",
            "impacted_object_id",
        ),
        Index("idx_risk_event_impacts_level", "impact_level"),
    )

    risk_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("risk_events.id"), nullable=False
    )
    impacted_object_type: Mapped[str] = mapped_column(Text, nullable=False)
    impacted_object_id: Mapped[UUID] = mapped_column(nullable=False)
    impact_level: Mapped[str] = mapped_column(Text, nullable=False)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    estimated_delay_days: Mapped[int | None] = mapped_column(Integer)
    impact_reason: Mapped[str | None] = mapped_column(Text)

    risk_event: Mapped[RiskEvent] = relationship(back_populates="impacts")

