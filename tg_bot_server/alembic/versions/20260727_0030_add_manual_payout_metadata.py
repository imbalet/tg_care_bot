"""Add metadata for manually recorded payouts.

Revision ID: 20260727_0030
Revises: 20260725_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260727_0030"
down_revision: str | None = "20260725_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("payout_reference", sa.Text(), nullable=True))
    op.add_column(
        "orders",
        sa.Column(
            "payout_admin_id",
            sa.Uuid(),
            sa.ForeignKey("admins.id"),
            nullable=True,
        ),
    )
    op.add_column("orders", sa.Column("payout_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "payout_comment")
    op.drop_column("orders", "payout_admin_id")
    op.drop_column("orders", "payout_reference")
