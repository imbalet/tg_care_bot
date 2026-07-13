"""Update Telegram topic kinds.

Revision ID: 20260713_0012
Revises: 20260713_0011
Create Date: 2026-07-13 17:40:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260713_0012"
down_revision: str | None = "20260713_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_CONSTRAINT = "ck_telegram_topics_topic_kind"


def upgrade() -> None:
    op.execute(
        """
        update telegram_topics
        set topic_kind = case topic_kind
            when 'nanny' then 'children'
            when 'caregiver' then 'wards'
            when 'petsitter' then 'pets'
            else topic_kind
        end
        where topic_kind in ('nanny', 'caregiver', 'petsitter')
        """,
    )
    op.drop_constraint(OLD_CONSTRAINT, "telegram_topics", type_="check")
    op.create_check_constraint(
        OLD_CONSTRAINT,
        "telegram_topics",
        "topic_kind in ('children', 'wards', 'pets', 'work', 'notifications')",
    )


def downgrade() -> None:
    op.execute(
        """
        delete from telegram_topics
        where topic_kind = 'work'
        """,
    )
    op.execute(
        """
        update telegram_topics
        set topic_kind = case topic_kind
            when 'children' then 'nanny'
            when 'wards' then 'caregiver'
            when 'pets' then 'petsitter'
            else topic_kind
        end
        where topic_kind in ('children', 'wards', 'pets')
        """,
    )
    op.drop_constraint(OLD_CONSTRAINT, "telegram_topics", type_="check")
    op.create_check_constraint(
        OLD_CONSTRAINT,
        "telegram_topics",
        "topic_kind in ('notifications', 'nanny', 'caregiver', 'petsitter')",
    )
