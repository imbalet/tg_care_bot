"""Add active state to performer calendar overrides.

Revision ID: 20260728_0031
Revises: 20260727_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260728_0031"
down_revision: str | None = "20260727_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "performer_calendar_overrides",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column(
        "performer_calendar_overrides",
        "is_active",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("performer_calendar_overrides", "is_active")
