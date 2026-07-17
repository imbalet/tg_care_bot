"""Drop Telegram topics.

Revision ID: 20260713_0013
Revises: 20260713_0012
Create Date: 2026-07-13 04:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0013"
down_revision: str | None = "20260713_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("telegram_topics")


def downgrade() -> None:
    op.create_table(
        "telegram_topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("topic_kind", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("message_thread_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "account_type in ('customer', 'performer')",
            name=op.f("ck_telegram_topics_account_type"),
        ),
        sa.CheckConstraint(
            "topic_kind in ('children', 'wards', 'pets', 'work', 'notifications')",
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
