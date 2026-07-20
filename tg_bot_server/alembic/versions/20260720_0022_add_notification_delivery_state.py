"""Add notification delivery and admin inbox state.

Revision ID: 20260720_0022
Revises: 20260720_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_0022"
down_revision: str | None = "20260720_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notifications",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint(op.f("ck_notifications_channel"), "notifications", type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_channel"),
        "notifications",
        "channel in ('telegram', 'admin_panel')",
    )
    op.drop_constraint(op.f("ck_notifications_status"), "notifications", type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_status"),
        "notifications",
        "status in ('pending', 'processing', 'sent', 'failed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_notifications_status"), "notifications", type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_status"),
        "notifications",
        "status in ('pending', 'sent', 'failed', 'cancelled')",
    )
    op.drop_constraint(op.f("ck_notifications_channel"), "notifications", type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_channel"),
        "notifications",
        "channel in ('telegram')",
    )
    op.drop_column("notifications", "read_at")
    op.drop_column("notifications", "claimed_at")
