"""Add purchase order expedite fields.

Revision ID: 20260801_0001
Revises: 20260715_0001
Create Date: 2026-08-01 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0001"
down_revision: str | None = "20260715_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column(
            "expedited",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "purchase_orders",
        sa.Column("expedite_cost", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("purchase_orders", "expedite_cost")
    op.drop_column("purchase_orders", "expedited")
