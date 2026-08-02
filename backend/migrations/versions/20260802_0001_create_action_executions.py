"""Create action execution persistence table.

Revision ID: 20260802_0001
Revises: 20260801_0001
Create Date: 2026-08-02 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0001"
down_revision: str | None = "20260801_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = postgresql.TIMESTAMP(timezone=True)


def upgrade() -> None:
    op.create_table(
        "action_executions",
        sa.Column(
            "id", UUID, nullable=False, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("execution_id", sa.Text(), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("action_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("invocation_mode", sa.Text(), nullable=False),
        sa.Column("parent_execution_id", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("started_at", TIMESTAMPTZ, nullable=False),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("result_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "affected_objects",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('started', 'succeeded', 'failed')",
            name="ck_action_executions_action_executions_status_allowed",
        ),
        sa.CheckConstraint(
            "invocation_mode IN ('direct', 'child_action')",
            name="ck_action_executions_action_executions_invocation_mode_allowed",
        ),
        sa.CheckConstraint(
            "completed_at IS NOT NULL OR status = 'started'",
            name="ck_action_executions_action_executions_completion_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["parent_execution_id"],
            ["action_executions.execution_id"],
            name="fk_action_executions_parent_execution_id_action_executions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_action_executions"),
        sa.UniqueConstraint("execution_id", name="uq_action_executions_execution_id"),
    )
    op.create_index(
        "idx_action_executions_execution_id",
        "action_executions",
        ["execution_id"],
        unique=True,
    )
    op.create_index(
        "idx_action_executions_parent_execution_id",
        "action_executions",
        ["parent_execution_id"],
    )
    op.create_index(
        "idx_action_executions_status",
        "action_executions",
        ["status"],
    )
    op.create_index(
        "idx_action_executions_started_at",
        "action_executions",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_action_executions_started_at", table_name="action_executions")
    op.drop_index("idx_action_executions_status", table_name="action_executions")
    op.drop_index(
        "idx_action_executions_parent_execution_id",
        table_name="action_executions",
    )
    op.drop_index("idx_action_executions_execution_id", table_name="action_executions")
    op.drop_table("action_executions")
