"""Add administrative violation history.

Revision ID: 20260801_0036
Revises: 20260728_0035
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_0036"
down_revision: str | None = "20260728_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_violations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("performer_id", sa.Uuid(), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("case_type", sa.Text(), nullable=True),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("violation_type", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by_admin_id", sa.Uuid(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["performer_id"], ["performers.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["admins.id"]),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_violations")),
        sa.CheckConstraint(
            "account_type in ('customer', 'performer')",
            name=op.f("ck_admin_violations_account_type"),
        ),
        sa.CheckConstraint(
            "action in ('warning', 'block')",
            name=op.f("ck_admin_violations_action"),
        ),
        sa.CheckConstraint(
            "status in ('open', 'resolved')",
            name=op.f("ck_admin_violations_status"),
        ),
    )
    op.create_index(
        op.f("ix_admin_violations_customer_id"),
        "admin_violations",
        ["customer_id"],
    )
    op.create_index(
        op.f("ix_admin_violations_performer_id"),
        "admin_violations",
        ["performer_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_admin_violations_performer_id"), table_name="admin_violations")
    op.drop_index(op.f("ix_admin_violations_customer_id"), table_name="admin_violations")
    op.drop_table("admin_violations")
