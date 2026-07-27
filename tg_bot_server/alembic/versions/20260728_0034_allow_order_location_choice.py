"""Allow customers to choose the location for boarding orders.

Revision ID: 20260728_0034
Revises: 20260728_0033
Create Date: 2026-07-28 00:34:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260728_0034"
down_revision: str | None = "20260728_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    services = sa.table(
        "services",
        sa.column("code", sa.Text()),
        sa.column("location_policy", sa.Text()),
    )
    op.execute(
        services.update()
        .where(services.c.code == "pet_boarding")
        .values(location_policy="customer_or_performer_address")
    )


def downgrade() -> None:
    services = sa.table(
        "services",
        sa.column("code", sa.Text()),
        sa.column("location_policy", sa.Text()),
    )
    op.execute(
        services.update()
        .where(services.c.code == "pet_boarding")
        .values(location_policy="performer_address")
    )
