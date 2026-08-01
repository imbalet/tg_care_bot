"""Add bounded manual retry count for admin notifications.

Revision ID: 20260801_0037
Revises: 20260801_0036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260801_0037"
down_revision: str | None = "20260801_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("admin_retry_count", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.alter_column("notifications", "admin_retry_count", server_default=None)


def downgrade() -> None:
    op.drop_column("notifications", "admin_retry_count")
