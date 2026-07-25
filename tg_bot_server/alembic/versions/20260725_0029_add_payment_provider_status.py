"""Add provider payment status for two-stage acquiring.

Revision ID: 20260725_0029
Revises: 20260723_0028
Create Date: 2026-07-25 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260725_0029"
down_revision: str | None = "20260723_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "provider_status",
            sa.Text(),
            nullable=False,
            server_default="NEW",
        ),
    )
    op.alter_column("payments", "provider_status", server_default=None)


def downgrade() -> None:
    op.drop_column("payments", "provider_status")
