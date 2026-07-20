"""Prevent concurrent active refunds for one payment.

Revision ID: 20260720_0020
Revises: 20260720_0019
Create Date: 2026-07-20 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0020"
down_revision: str | None = "20260720_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_refunds_active_payment",
        "refunds",
        ["payment_id"],
        unique=True,
        postgresql_where=sa.text("status in ('pending', 'succeeded')"),
    )


def downgrade() -> None:
    op.drop_index("uq_refunds_active_payment", table_name="refunds")
