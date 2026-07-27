"""Add per-performer nearby order notification preference.

Revision ID: 20260728_0033
Revises: 20260728_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260728_0033"
down_revision: str | None = "20260728_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "performers",
        sa.Column(
            "is_nearby_order_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column(
        "performers",
        "is_nearby_order_notifications_enabled",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("performers", "is_nearby_order_notifications_enabled")
