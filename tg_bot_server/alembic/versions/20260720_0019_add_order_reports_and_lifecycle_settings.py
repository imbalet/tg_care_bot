"""Add order reports and lifecycle settings.

Revision ID: 20260720_0019
Revises: 20260719_0018
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision: str = "20260720_0019"
down_revision: str | None = "20260719_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "order_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("performer_id", sa.Uuid(), nullable=False),
        sa.Column("completed_work", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("problem_flag", sa.Boolean(), nullable=False),
        sa.Column("problem_description", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_reports")),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_reports_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_id"],
            ["performers.id"],
            name=op.f("fk_order_reports_performer_id_performers"),
        ),
        sa.UniqueConstraint("order_id", name=op.f("uq_order_reports_order_id")),
        sa.CheckConstraint(
            "not problem_flag or problem_description is not null",
            name=op.f("ck_order_reports_problem_description"),
        ),
    )
    op.create_index(
        op.f("ix_order_reports_order_id"),
        "order_reports",
        ["order_id"],
    )

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
    values = [
        ("report_deadline_minutes", 120, "Report submission grace period"),
        ("customer_cancel_before_start_minutes", 0, "Customer cancellation window"),
        ("performer_cancel_before_start_minutes", 60, "Performer cancellation window"),
        ("order_approaching_minutes", 60, "Order approaching notification window"),
        ("report_reminder_minutes", 60, "Report reminder delay"),
    ]
    rows = []
    for index, (key, value, description) in enumerate(values, start=1):
        rows.append(
            {
                "id": UUID(f"71111111-1111-4111-8111-0000000002{index:02d}"),
                "key": key,
                "value": sa.cast(sa.literal(json.dumps(value)), postgresql.JSONB),
                "value_type": "number",
                "description": description,
                "updated_by_admin_id": None,
                "created_at": now,
                "updated_at": now,
            },
        )
    op.execute(
        insert(settings).values(rows).on_conflict_do_nothing(index_elements=["key"])
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "delete from business_settings where key in "
            "('report_deadline_minutes', 'customer_cancel_before_start_minutes', "
            "'performer_cancel_before_start_minutes', 'order_approaching_minutes', "
            "'report_reminder_minutes')",
        ),
    )
    op.drop_index(op.f("ix_order_reports_order_id"), table_name="order_reports")
    op.drop_table("order_reports")
