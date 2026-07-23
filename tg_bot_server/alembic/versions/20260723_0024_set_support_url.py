"""Set temporary support URL seed value.

Revision ID: 20260723_0024
Revises: 20260720_0023
Create Date: 2026-07-23 00:24:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0024"
down_revision: str | None = "20260720_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE business_settings "
            "SET value = CAST(:value AS JSONB), updated_at = CURRENT_TIMESTAMP "
            "WHERE key = 'support_telegram_url'",
        ).bindparams(value='"https://t.me/we_are_close_support"'),
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE business_settings "
            "SET value = CAST(:value AS JSONB), updated_at = CURRENT_TIMESTAMP "
            "WHERE key = 'support_telegram_url'",
        ).bindparams(value='"todo-support-url"'),
    )
