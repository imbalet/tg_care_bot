"""Add refunds.

Revision ID: 20260718_0016
Revises: 20260718_0015
Create Date: 2026-07-18 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260718_0016"
down_revision: str | None = "20260718_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refunds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("refund_type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("provider_refund_id", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name=op.f("ck_refunds_amount")),
        sa.CheckConstraint(
            "refund_type in ('full', 'partial')",
            name=op.f("ck_refunds_refund_type"),
        ),
        sa.CheckConstraint(
            "status in ('pending', 'succeeded', 'failed')",
            name=op.f("ck_refunds_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_refunds_created_by_admin_id_admins"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_refunds_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_refunds_payment_id_payments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refunds")),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_refunds_idempotency_key"),
        ),
    )
    op.create_index(op.f("ix_refunds_order_id"), "refunds", ["order_id", "status"])
    op.create_index(
        "uq_provider_refund",
        "refunds",
        ["provider_refund_id"],
        unique=True,
        postgresql_where=sa.text("provider_refund_id is not null"),
    )


def downgrade() -> None:
    op.drop_index("uq_provider_refund", table_name="refunds")
    op.drop_index(op.f("ix_refunds_order_id"), table_name="refunds")
    op.drop_table("refunds")
