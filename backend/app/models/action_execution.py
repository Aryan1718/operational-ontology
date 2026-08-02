"""Persisted action execution records."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.action_execution import ActionExecution


class ActionExecutionStatus(StrEnum):
    """Persisted action execution lifecycle states."""

    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ActionExecutionInvocationMode(StrEnum):
    """Persisted action execution invocation modes."""

    DIRECT = "direct"
    CHILD_ACTION = "child_action"


class ActionExecution(UUIDPrimaryKeyMixin, Base):
    """One persisted governed action execution."""

    __tablename__ = "action_executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'succeeded', 'failed')",
            name="action_executions_status_allowed",
        ),
        CheckConstraint(
            "invocation_mode IN ('direct', 'child_action')",
            name="action_executions_invocation_mode_allowed",
        ),
        CheckConstraint(
            "completed_at IS NOT NULL OR status = 'started'",
            name="action_executions_completion_consistency",
        ),
        Index("idx_action_executions_execution_id", "execution_id", unique=True),
        Index("idx_action_executions_parent_execution_id", "parent_execution_id"),
        Index("idx_action_executions_status", "status"),
        Index("idx_action_executions_started_at", "started_at"),
    )

    execution_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    action_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    invocation_mode: Mapped[str] = mapped_column(Text, nullable=False)
    parent_execution_id: Mapped[str | None] = mapped_column(
        ForeignKey("action_executions.execution_id"),
    )
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor_role: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column()
    result_payload: Mapped[Any | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    affected_objects: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)

    parent_execution: Mapped[ActionExecution | None] = relationship(
        "ActionExecution",
        remote_side="ActionExecution.execution_id",
        foreign_keys=[parent_execution_id],
    )
