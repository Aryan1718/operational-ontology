"""Add execution_id to audit logs.

Revision ID: 20260812_0001
Revises: 20260801_0001
Create Date: 2026-08-12 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0001"
down_revision: str | None = "20260801_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("execution_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_logs", "execution_id")
