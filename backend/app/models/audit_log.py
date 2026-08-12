# ruff: noqa: E501
"""Audit log operational model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.supply_chain import User


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "object_type IN ('supplier', 'part', 'product', 'warehouse', 'inventory', 'customer_order', 'shipment', 'purchase_order', 'risk_event', 'risk_event_impact', 'mitigation_plan', 'mitigation_plan_step')",
            name="audit_logs_object_type_allowed",
        ),
        Index("idx_audit_logs_actor_user_id", "actor_user_id"),
        Index("idx_audit_logs_action_type", "action_type"),
        Index("idx_audit_logs_object", "object_type", "object_id"),
        Index("idx_audit_logs_created_at", "created_at"),
    )

    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    execution_id: Mapped[str | None] = mapped_column(Text)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str] = mapped_column(Text, nullable=False)
    object_id: Mapped[UUID] = mapped_column(nullable=False)
    previous_value: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=text("now()")
    )

    actor_user: Mapped["User | None"] = relationship(back_populates="audit_logs")
