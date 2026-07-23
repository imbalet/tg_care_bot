"""Add contact requests between order participants."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0028"
down_revision: str | None = "20260723_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contact_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("performer_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("requested_method", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_requests")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["performer_id"], ["performers.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.CheckConstraint(
            "status in ('requested', 'sent', 'failed')",
            name=op.f("ck_contact_requests_status"),
        ),
    )
    op.create_index(
        op.f("ix_contact_requests_order_id"), "contact_requests", ["order_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_contact_requests_order_id"), table_name="contact_requests")
    op.drop_table("contact_requests")
