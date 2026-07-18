"""Add payment and notification skeleton.

Revision ID: 20260718_0015
Revises: 20260713_0014
Create Date: 2026-07-18 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260718_0015"
down_revision: str | None = "20260713_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("performer_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.SmallInteger(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_payment_id", sa.Text(), nullable=True),
        sa.Column("provider_deal_id", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("confirmation_url", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unapplied_reason", sa.Text(), nullable=True),
        sa.Column("failure_code", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("attempt_number >= 1", name=op.f("ck_payments_attempt")),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_payments_amount")),
        sa.CheckConstraint(
            "status in ('created', 'pending', 'succeeded', 'succeeded_unapplied', "
            "'failed', 'expired', 'cancelled')",
            name=op.f("ck_payments_status"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_payments_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_id"],
            ["performers.id"],
            name=op.f("fk_payments_performer_id_performers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_payments_idempotency_key")
        ),
        sa.UniqueConstraint(
            "order_id",
            "attempt_number",
            name=op.f("uq_payments_order_id"),
        ),
    )
    op.create_index(op.f("ix_payments_order_id"), "payments", ["order_id", "status"])
    op.create_index(
        op.f("ix_payments_performer_id"),
        "payments",
        ["performer_id", "status"],
    )
    op.create_index(
        "uq_provider_payment",
        "payments",
        ["provider", "provider_payment_id"],
        unique=True,
        postgresql_where=sa.text("provider_payment_id is not null"),
    )
    op.create_index(
        "uq_active_payment_per_order",
        "payments",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("status in ('created', 'pending')"),
    )
    op.create_foreign_key(
        op.f("fk_orders_active_payment_id_payments"),
        "orders",
        "payments",
        ["active_payment_id"],
        ["id"],
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipient_type", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("performer_id", sa.Uuid(), nullable=True),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("deduplication_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delete_after", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "recipient_type in ('customer', 'performer', 'admin')",
            name=op.f("ck_notifications_recipient_type"),
        ),
        sa.CheckConstraint(
            "channel in ('telegram')",
            name=op.f("ck_notifications_channel"),
        ),
        sa.CheckConstraint(
            "status in ('pending', 'sent', 'failed', 'cancelled')",
            name=op.f("ck_notifications_status"),
        ),
        sa.CheckConstraint("attempts >= 0", name=op.f("ck_notifications_attempts")),
        sa.CheckConstraint(
            "("
            "recipient_type = 'customer' and customer_id is not null and "
            "performer_id is null and admin_id is null"
            ") or ("
            "recipient_type = 'performer' and performer_id is not null and "
            "customer_id is null and admin_id is null"
            ") or ("
            "recipient_type = 'admin' and admin_id is not null and "
            "customer_id is null and performer_id is null"
            ")",
            name=op.f("ck_notifications_recipient"),
        ),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admins.id"],
            name=op.f("fk_notifications_admin_id_admins"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_notifications_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_id"],
            ["performers.id"],
            name=op.f("fk_notifications_performer_id_performers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint(
            "deduplication_key",
            name=op.f("uq_notifications_deduplication_key"),
        ),
    )
    op.create_index(
        op.f("ix_notifications_status"),
        "notifications",
        ["status", "scheduled_at"],
    )
    op.create_index(
        op.f("ix_notifications_delete_after"),
        "notifications",
        ["delete_after"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_delete_after"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_status"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_constraint(
        op.f("fk_orders_active_payment_id_payments"),
        "orders",
        type_="foreignkey",
    )
    op.drop_index("uq_active_payment_per_order", table_name="payments")
    op.drop_index("uq_provider_payment", table_name="payments")
    op.drop_index(op.f("ix_payments_performer_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_order_id"), table_name="payments")
    op.drop_table("payments")
