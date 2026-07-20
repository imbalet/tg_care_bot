"""Add immutable order address snapshots and boarding duration limit.

Revision ID: 20260720_0021
Revises: 20260720_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0021"
down_revision: str | None = "20260720_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_address_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("source_address_id", sa.Uuid(), nullable=False),
        sa.Column("city_name", sa.Text(), nullable=False),
        sa.Column("district_name", sa.Text(), nullable=True),
        sa.Column("address_text", sa.Text(), nullable=False),
        sa.Column("fias_id", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("geocoding_provider", sa.Text(), nullable=True),
        sa.Column("geocoding_quality", sa.Text(), nullable=True),
        sa.Column("entrance", sa.Text(), nullable=True),
        sa.Column("floor", sa.Text(), nullable=True),
        sa.Column("apartment", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_address_snapshots_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["source_address_id"],
            ["addresses.id"],
            name=op.f("fk_order_address_snapshots_source_address_id_addresses"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_address_snapshots")),
        sa.UniqueConstraint(
            "order_id", name=op.f("uq_order_address_snapshots_order_id")
        ),
    )
    op.execute(
        sa.text(
            "update services set max_duration_minutes = 20160 "
            "where code = 'pet_boarding'",
        ),
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "update services set max_duration_minutes = null "
            "where code = 'pet_boarding'",
        ),
    )
    op.drop_table("order_address_snapshots")
