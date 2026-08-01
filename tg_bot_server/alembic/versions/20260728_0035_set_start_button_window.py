"""Set the start button window to thirty minutes.

Revision ID: 20260728_0035
Revises: 20260728_0034
Create Date: 2026-07-28 00:35:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260728_0035"
down_revision: str | None = "20260728_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    settings = sa.table(
        "business_settings",
        sa.column("key", sa.Text()),
        sa.column("value", sa.JSON()),
    )
    op.execute(
        settings.update()
        .where(settings.c.key == "start_button_before_minutes")
        .values(value=sa.cast(sa.literal("30"), postgresql.JSONB))
    )


def downgrade() -> None:
    settings = sa.table(
        "business_settings",
        sa.column("key", sa.Text()),
        sa.column("value", sa.JSON()),
    )
    op.execute(
        settings.update()
        .where(settings.c.key == "start_button_before_minutes")
        .values(value=sa.cast(sa.literal("15"), postgresql.JSONB))
    )
