"""Pydantic schemas for persisted audit log responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.common import ApiBaseModel


class AuditLogSummary(ApiBaseModel):
    """Compact persisted audit log entry."""

    audit_log_id: UUID = Field(alias="auditLogId")
    action_type_id: str = Field(alias="actionTypeId")
    actor_id: UUID | None = Field(alias="actorId", default=None)
    object_type: str = Field(alias="objectType")
    object_id: UUID = Field(alias="objectId")
    previous_value: dict[str, Any] | None = Field(alias="previousValue", default=None)
    new_value: dict[str, Any] | None = Field(alias="newValue", default=None)
    reason: str | None = None
    timestamp: datetime


class AuditLogListResponse(ApiBaseModel):
    """Paginated persisted audit log response payload."""

    audit_logs: list[AuditLogSummary] = Field(alias="auditLogs", default_factory=list)
