"""Add order photo policy snapshot.

Revision ID: 20260713_0011
Revises: 20260713_0010
Create Date: 2026-07-13 03:50:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0011"
down_revision: str | None = "20260713_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("photo_policy", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_orders_photo_policy"),
        "orders",
        "photo_policy is null or photo_policy in "
        "('required', 'optional', 'requires_customer_consent', 'forbidden')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_orders_photo_policy"), "orders", type_="check")
    op.drop_column("orders", "photo_policy")
