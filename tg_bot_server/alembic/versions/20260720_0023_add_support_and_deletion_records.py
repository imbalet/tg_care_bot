"""Add support, complaint and account deletion records.

Revision ID: 20260720_0023
Revises: 20260720_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260720_0023"
down_revision: str | None = "20260720_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUS = "'open', 'in_progress', 'resolved', 'rejected'"
ACTOR = (
    "(customer_id is not null and performer_id is null) or "
    "(customer_id is null and performer_id is not null)"
)
COMPLAINT_CATEGORY = (
    "category in ('order_problem', 'conditions_mismatch', "
    "'no_contact', 'post_completion')"
)
FILE_ENTITY_TYPES = (
    "entity_type in ('customer', 'performer', 'order_report', 'dispute', "
    "'complaint', 'support_request')"
)
FILE_PURPOSES = (
    "purpose in ('avatar', 'report_photo', 'dispute_attachment', "
    "'complaint_attachment', 'support_attachment', 'admin_attachment', 'other')"
)
NOTIFICATION_RECIPIENT = (
    "(recipient_type = 'customer' and customer_id is not null and "
    "performer_id is null and admin_id is null and recipient_telegram_id is null) or "
    "(recipient_type = 'performer' and performer_id is not null and "
    "customer_id is null and admin_id is null and recipient_telegram_id is null) or "
    "(recipient_type = 'admin' and customer_id is null and performer_id is null and "
    "recipient_telegram_id is null) or "
    "(recipient_type = 'performer_invitation' and recipient_telegram_id is not null "
    "and customer_id is null and performer_id is null and admin_id is null)"
)
NOTIFICATION_RECIPIENT_TARGETED_ADMIN = (
    "(recipient_type = 'customer' and customer_id is not null and "
    "performer_id is null and admin_id is null and recipient_telegram_id is null) or "
    "(recipient_type = 'performer' and performer_id is not null and "
    "customer_id is null and admin_id is null and recipient_telegram_id is null) or "
    "(recipient_type = 'admin' and admin_id is not null and customer_id is null and "
    "performer_id is null and recipient_telegram_id is null) or "
    "(recipient_type = 'performer_invitation' and recipient_telegram_id is not null "
    "and customer_id is null and performer_id is null and admin_id is null)"
)


def _actor_constraint() -> str:
    return ACTOR


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("performer_id", sa.Uuid(), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    for table_name, extra, category_constraint in (
        (
            "support_requests",
            [sa.Column("type", sa.Text(), nullable=False)],
            None,
        ),
        (
            "complaints",
            [sa.Column("category", sa.Text(), nullable=False)],
            COMPLAINT_CATEGORY,
        ),
    ):
        constraints = [
            sa.CheckConstraint(
                _actor_constraint(), name=op.f(f"ck_{table_name}_actor")
            ),
            sa.CheckConstraint(
                "direction in ('customer', 'performer')",
                name=op.f(f"ck_{table_name}_direction"),
            ),
            sa.CheckConstraint(
                f"status in ({STATUS})", name=op.f(f"ck_{table_name}_status")
            ),
            sa.ForeignKeyConstraint(
                ["customer_id"],
                ["customers.id"],
                name=op.f(f"fk_{table_name}_customer_id_customers"),
            ),
            sa.ForeignKeyConstraint(
                ["performer_id"],
                ["performers.id"],
                name=op.f(f"fk_{table_name}_performer_id_performers"),
            ),
            sa.ForeignKeyConstraint(
                ["order_id"],
                ["orders.id"],
                name=op.f(f"fk_{table_name}_order_id_orders"),
            ),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
        ]
        if category_constraint is not None:
            constraints.append(
                sa.CheckConstraint(
                    category_constraint, name=op.f(f"ck_{table_name}_category")
                )
            )
        else:
            constraints.append(
                sa.CheckConstraint(
                    "type in ('technical', 'payment', 'order', 'account', 'other')",
                    name=op.f(f"ck_{table_name}_type"),
                )
            )
        op.create_table(table_name, *_common_columns(), *extra, *constraints)
        op.create_index(
            op.f(f"ix_{table_name}_status"), table_name, ["status", "created_at"]
        )
        op.create_index(
            op.f(f"ix_{table_name}_customer_id"),
            table_name,
            ["customer_id", "created_at"],
        )
        op.create_index(
            op.f(f"ix_{table_name}_performer_id"),
            table_name,
            ["performer_id", "created_at"],
        )

    op.create_table(
        "account_deletion_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("performer_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("blockers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _actor_constraint(), name=op.f("ck_account_deletion_requests_actor")
        ),
        sa.CheckConstraint(
            f"status in ({STATUS})", name=op.f("ck_account_deletion_requests_status")
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_account_deletion_requests_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_id"],
            ["performers.id"],
            name=op.f("fk_account_deletion_requests_performer_id_performers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_deletion_requests")),
    )
    op.create_index(
        op.f("ix_account_deletion_requests_status"),
        "account_deletion_requests",
        ["status", "created_at"],
    )
    op.create_index(
        "uq_active_customer_deletion_request",
        "account_deletion_requests",
        ["customer_id"],
        unique=True,
        postgresql_where=sa.text(
            "customer_id is not null and status in ('open', 'in_progress')"
        ),
    )
    op.create_index(
        "uq_active_performer_deletion_request",
        "account_deletion_requests",
        ["performer_id"],
        unique=True,
        postgresql_where=sa.text(
            "performer_id is not null and status in ('open', 'in_progress')"
        ),
    )
    op.drop_constraint(op.f("ck_file_links_entity_type"), "file_links", type_="check")
    op.create_check_constraint(
        op.f("ck_file_links_entity_type"),
        "file_links",
        FILE_ENTITY_TYPES,
    )
    op.drop_constraint(op.f("ck_file_links_purpose"), "file_links", type_="check")
    op.create_check_constraint(
        op.f("ck_file_links_purpose"),
        "file_links",
        FILE_PURPOSES,
    )
    op.drop_constraint(
        op.f("ck_notifications_recipient"), "notifications", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_notifications_recipient"),
        "notifications",
        NOTIFICATION_RECIPIENT,
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_notifications_recipient"), "notifications", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_notifications_recipient"),
        "notifications",
        NOTIFICATION_RECIPIENT_TARGETED_ADMIN,
    )
    op.drop_constraint(op.f("ck_file_links_purpose"), "file_links", type_="check")
    op.create_check_constraint(
        op.f("ck_file_links_purpose"),
        "file_links",
        "purpose in ('avatar', 'report_photo', 'dispute_attachment', "
        "'complaint_attachment', 'admin_attachment', 'other')",
    )
    op.drop_constraint(op.f("ck_file_links_entity_type"), "file_links", type_="check")
    op.create_check_constraint(
        op.f("ck_file_links_entity_type"),
        "file_links",
        "entity_type in ('customer', 'performer', 'order_report', "
        "'dispute', 'complaint')",
    )
    op.drop_index(
        "uq_active_performer_deletion_request", table_name="account_deletion_requests"
    )
    op.drop_index(
        "uq_active_customer_deletion_request", table_name="account_deletion_requests"
    )
    op.drop_index(
        op.f("ix_account_deletion_requests_status"),
        table_name="account_deletion_requests",
    )
    op.drop_table("account_deletion_requests")
    for table_name in ("complaints", "support_requests"):
        op.drop_index(op.f(f"ix_{table_name}_performer_id"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_customer_id"), table_name=table_name)
        op.drop_index(op.f(f"ix_{table_name}_status"), table_name=table_name)
        op.drop_table(table_name)
