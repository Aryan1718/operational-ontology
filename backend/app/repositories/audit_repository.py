"""Repository helpers for persisted audit log history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.object_repository import SearchResultPage


@dataclass(frozen=True, slots=True)
class AuditLogListFilters:
    """Optional public list filters bound to persisted audit log columns."""

    object_type: str | None = None
    object_id: UUID | None = None
    actor_id: UUID | None = None
    action_type_id: str | None = None


class AuditRepository:
    """Retrieve and persist audit log rows inside the caller transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_audit_log(
        self,
        *,
        actor_user_id: UUID | None,
        execution_id: str | None,
        action_type: str,
        object_type: str,
        object_id: UUID,
        previous_value: dict[str, Any] | None,
        new_value: dict[str, Any] | None,
        reason: str | None,
    ) -> AuditLog:
        audit_log = AuditLog(
            actor_user_id=actor_user_id,
            execution_id=execution_id,
            action_type=action_type,
            object_type=object_type,
            object_id=object_id,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
        )
        self._session.add(audit_log)
        self._session.flush()
        return audit_log

    def get_by_execution_id(self, execution_id: str) -> list[AuditLog]:
        statement = (
            select(AuditLog)
            .where(AuditLog.execution_id == execution_id)
            .order_by(
                AuditLog.created_at.asc(),
                AuditLog.id.asc(),
            )
        )
        return list(self._session.execute(statement).scalars().all())

    def list_audit_logs(
        self,
        *,
        filters: AuditLogListFilters,
        limit: int,
        offset: int,
    ) -> SearchResultPage:
        statement = select(AuditLog)
        statement = self._apply_list_filters(statement, filters)
        statement = statement.order_by(
            AuditLog.created_at.desc(),
            AuditLog.id.desc(),
        )
        statement = statement.offset(offset).limit(limit + 1)

        records = list(self._session.execute(statement).scalars().all())
        has_more = len(records) > limit
        page_records = records[:limit]

        return SearchResultPage(
            records=page_records,
            next_cursor=None,
            has_more=has_more,
        )

    @staticmethod
    def _apply_list_filters(
        statement: Select[tuple[AuditLog]],
        filters: AuditLogListFilters,
    ) -> Select[tuple[AuditLog]]:
        if filters.object_type is not None:
            statement = statement.where(AuditLog.object_type == filters.object_type)
        if filters.object_id is not None:
            statement = statement.where(AuditLog.object_id == filters.object_id)
        if filters.actor_id is not None:
            statement = statement.where(AuditLog.actor_user_id == filters.actor_id)
        if filters.action_type_id is not None:
            statement = statement.where(AuditLog.action_type == filters.action_type_id)
        return statement
