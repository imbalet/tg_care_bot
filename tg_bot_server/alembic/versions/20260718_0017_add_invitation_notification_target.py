"""Add invitation notification target.

Revision ID: 20260718_0017
Revises: 20260718_0016
Create Date: 2026-07-18 23:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260718_0017"
down_revision: str | None = "20260718_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_pending_performer_invitation_telegram_id",
        "performer_invitations",
        ["telegram_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.add_column(
        "notifications",
        sa.Column("recipient_telegram_id", sa.BigInteger(), nullable=True),
    )
    op.drop_constraint(
        op.f("ck_notifications_recipient_type"),
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_notifications_recipient_type"),
        "notifications",
        "recipient_type in ('customer', 'performer', 'admin', 'performer_invitation')",
    )
    op.drop_constraint(
        op.f("ck_notifications_recipient"),
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_notifications_recipient"),
        "notifications",
        "("
        "recipient_type = 'customer' and customer_id is not null and "
        "performer_id is null and admin_id is null and recipient_telegram_id is null"
        ") or ("
        "recipient_type = 'performer' and performer_id is not null and "
        "customer_id is null and admin_id is null and recipient_telegram_id is null"
        ") or ("
        "recipient_type = 'admin' and admin_id is not null and "
        "customer_id is null and performer_id is null and recipient_telegram_id is null"
        ") or ("
        "recipient_type = 'performer_invitation' and recipient_telegram_id is not null "
        "and customer_id is null and performer_id is null and admin_id is null"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_notifications_recipient"),
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_notifications_recipient"),
        "notifications",
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
    )
    op.drop_constraint(
        op.f("ck_notifications_recipient_type"),
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_notifications_recipient_type"),
        "notifications",
        "recipient_type in ('customer', 'performer', 'admin')",
    )
    op.drop_column("notifications", "recipient_telegram_id")
    op.drop_index(
        "uq_pending_performer_invitation_telegram_id",
        table_name="performer_invitations",
    )
