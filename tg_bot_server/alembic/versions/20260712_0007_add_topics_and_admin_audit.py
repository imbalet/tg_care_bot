"""Add Telegram topics and admin audit log.

Revision ID: 20260712_0007
Revises: 20260712_0006
Create Date: 2026-07-12 00:07:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260712_0007"
down_revision: str | None = "20260712_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "audit_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admins.id"],
            name=op.f("fk_admin_audit_logs_admin_id_admins"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_audit_logs")),
    )
    op.create_table(
        "telegram_topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("topic_kind", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_thread_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "account_type in ('customer', 'performer')",
            name=op.f("ck_telegram_topics_account_type"),
        ),
        sa.CheckConstraint(
            "topic_kind in ('notifications', 'nanny', 'caregiver', 'petsitter')",
            name=op.f("ck_telegram_topics_topic_kind"),
        ),
        sa.CheckConstraint(
            "status in ('active', 'fallback', 'unavailable')",
            name=op.f("ck_telegram_topics_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_topics")),
        sa.UniqueConstraint(
            "account_type",
            "owner_id",
            "topic_kind",
            name=op.f("uq_telegram_topics_account_type"),
        ),
    )


def downgrade() -> None:
    op.drop_table("telegram_topics")
    op.drop_table("admin_audit_logs")
