"""Seed support settings.

Revision ID: 20260719_0018
Revises: 20260718_0017
Create Date: 2026-07-19 00:18:00
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision: str = "20260719_0018"
down_revision: str | None = "20260718_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    now = datetime.now(UTC)
    settings = sa.table(
        "business_settings",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.Text()),
        sa.column("value", postgresql.JSONB()),
        sa.column("value_type", sa.Text()),
        sa.column("description", sa.Text()),
        sa.column("updated_by_admin_id", sa.Uuid()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    statement = insert(settings).values(
        [
            {
                "id": UUID("71111111-1111-4111-8111-000000000101"),
                "key": "support_telegram_url",
                "value": _jsonb_literal("todo-support-url"),
                "value_type": "string",
                "description": "External Telegram support URL",
                "updated_by_admin_id": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": UUID("71111111-1111-4111-8111-000000000102"),
                "key": "support_label",
                "value": _jsonb_literal("Поддержка"),
                "value_type": "string",
                "description": "External support button label",
                "updated_by_admin_id": None,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    op.execute(statement.on_conflict_do_nothing(index_elements=["key"]))


def downgrade() -> None:
    op.execute(
        sa.text(
            "delete from business_settings "
            "where key in ('support_telegram_url', 'support_label')"
        ),
    )


def _jsonb_literal(value: object) -> sa.Cast[object]:
    return sa.cast(sa.literal(json.dumps(value)), postgresql.JSONB)
