"""Add customer disputes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0027"
down_revision: str | None = "20260723_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "disputes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_disputes")),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_disputes_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_disputes_order_id_orders"),
        ),
        sa.CheckConstraint(
            "status in ('open', 'closed')",
            name=op.f("ck_disputes_status"),
        ),
    )
    op.create_index(op.f("ix_disputes_customer_id"), "disputes", ["customer_id"])
    op.create_index(op.f("ix_disputes_order_id"), "disputes", ["order_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_disputes_order_id"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_customer_id"), table_name="disputes")
    op.drop_table("disputes")
