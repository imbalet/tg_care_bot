"""Add availability and order schema.

Revision ID: 20260713_0010
Revises: 20260713_0009
Create Date: 2026-07-13 03:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260713_0010"
down_revision: str | None = "20260713_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _created_at() -> sa.Column[sa.DateTime]:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "performer_services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("performer_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("admin_max_objects", sa.SmallInteger(), nullable=False),
        sa.Column("performer_max_objects", sa.SmallInteger(), nullable=False),
        sa.Column(
            "constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("approved_by_admin_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "admin_max_objects >= 1",
            name=op.f("ck_performer_services_admin_max_objects"),
        ),
        sa.CheckConstraint(
            "performer_max_objects >= 1 and performer_max_objects <= admin_max_objects",
            name=op.f("ck_performer_services_performer_max_objects"),
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_performer_services_approved_by_admin_id_admins"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_id"],
            ["performers.id"],
            name=op.f("fk_performer_services_performer_id_performers"),
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_performer_services_service_id_services"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performer_services")),
        sa.UniqueConstraint(
            "performer_id",
            "service_id",
            name=op.f("uq_performer_services_performer_id"),
        ),
    )
    op.create_index(
        op.f("ix_performer_services_service_id"),
        "performer_services",
        ["service_id"],
    )

    op.create_table(
        "performer_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("performer_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_type", sa.Text(), nullable=False),
        sa.Column("work_days", postgresql.ARRAY(sa.SmallInteger()), nullable=True),
        sa.Column("work_start_time", sa.Time(), nullable=False),
        sa.Column("work_end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "schedule_type in ('every_day', 'weekdays', 'weekends', 'custom')",
            name=op.f("ck_performer_schedules_schedule_type"),
        ),
        sa.CheckConstraint(
            "work_start_time < work_end_time",
            name=op.f("ck_performer_schedules_work_time"),
        ),
        sa.CheckConstraint(
            "("
            "schedule_type in ('every_day', 'weekdays', 'weekends') "
            "and work_days is null"
            ") or ("
            "schedule_type = 'custom' and work_days is not null "
            "and cardinality(work_days) > 0"
            ")",
            name=op.f("ck_performer_schedules_work_days"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_id"],
            ["performers.id"],
            name=op.f("fk_performer_schedules_performer_id_performers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performer_schedules")),
    )
    op.create_index(
        "uq_active_performer_schedule",
        "performer_schedules",
        ["performer_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "performer_calendar_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("performer_id", sa.Uuid(), nullable=False),
        sa.Column("override_type", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "override_type in ('available', 'unavailable')",
            name=op.f("ck_performer_calendar_overrides_override_type"),
        ),
        sa.CheckConstraint(
            "starts_at < ends_at",
            name=op.f("ck_performer_calendar_overrides_interval"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_id"],
            ["performers.id"],
            name=op.f("fk_performer_calendar_overrides_performer_id_performers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performer_calendar_overrides")),
    )
    op.create_index(
        op.f("ix_performer_calendar_overrides_performer_id"),
        "performer_calendar_overrides",
        ["performer_id", "starts_at", "ends_at"],
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("service_code", sa.Text(), nullable=False),
        sa.Column("service_name", sa.Text(), nullable=False),
        sa.Column("schedule_policy", sa.Text(), nullable=False),
        sa.Column("matching_mode", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("selected_performer_id", sa.Uuid(), nullable=True),
        sa.Column("selected_match_id", sa.Uuid(), nullable=True),
        sa.Column("active_payment_id", sa.Uuid(), nullable=True),
        sa.Column("address_id", sa.Uuid(), nullable=True),
        sa.Column("location_source", sa.Text(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("objects_count", sa.SmallInteger(), nullable=False),
        sa.Column("customer_comment", sa.Text(), nullable=True),
        sa.Column("report_photo_consent", sa.Boolean(), nullable=True),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("price_type", sa.Text(), nullable=False),
        sa.Column("object_multiplier", sa.Numeric(8, 4), nullable=False),
        sa.Column("service_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("platform_fee_percent_at_order", sa.Numeric(8, 4), nullable=False),
        sa.Column("platform_fee_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("performer_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payout_status", sa.Text(), nullable=True),
        sa.Column("payout_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("provider_payout_id", sa.Text(), nullable=True),
        sa.Column("payout_idempotency_key", sa.Text(), nullable=True),
        sa.Column("payout_block_reason", sa.Text(), nullable=True),
        sa.Column("payout_last_error", sa.Text(), nullable=True),
        sa.Column("payout_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_receipt_id", sa.Text(), nullable=True),
        sa.Column("receipt_url", sa.Text(), nullable=True),
        sa.Column("refund_policy_version_at_payment", sa.Text(), nullable=True),
        sa.Column("partial_refund_percent_at_payment", sa.Numeric(8, 4), nullable=True),
        sa.Column("matching_deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "confirmation_deadline_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("cancelled_by", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("cancellation_comment", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_reason", sa.Text(), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requires_admin_attention", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "schedule_policy in ('working_hours', 'calendar_only')",
            name=op.f("ck_orders_schedule_policy"),
        ),
        sa.CheckConstraint(
            "matching_mode is null or matching_mode in ('direct', 'pool')",
            name=op.f("ck_orders_matching_mode"),
        ),
        sa.CheckConstraint(
            "status in ('draft', 'searching', 'waiting_payment', 'confirmed', "
            "'in_progress', 'waiting_report', 'report_submitted', 'completed', "
            "'cancelled', 'expired')",
            name=op.f("ck_orders_status"),
        ),
        sa.CheckConstraint(
            "location_source in ('customer_address', 'performer_address')",
            name=op.f("ck_orders_location_source"),
        ),
        sa.CheckConstraint(
            "price_type in ('hourly', 'fixed', 'started_24h')",
            name=op.f("ck_orders_price_type"),
        ),
        sa.CheckConstraint(
            "end_at > start_at",
            name=op.f("ck_orders_interval"),
        ),
        sa.CheckConstraint(
            "objects_count >= 1",
            name=op.f("ck_orders_objects_count"),
        ),
        sa.CheckConstraint(
            "cancelled_by is null or cancelled_by in "
            "('customer', 'performer', 'admin', 'system')",
            name=op.f("ck_orders_cancelled_by"),
        ),
        sa.CheckConstraint(
            "cancellation_reason is null or cancellation_reason in ("
            "'customer_changed_plans', 'customer_created_new_order', "
            "'performer_refused_after_confirmation', 'performer_unavailable', "
            "'conditions_mismatch', 'safety_issue', 'admin_decision', "
            "'payment_problem', 'other')",
            name=op.f("ck_orders_cancellation_reason"),
        ),
        sa.CheckConstraint(
            "expired_reason is null or expired_reason in ("
            "'matching_deadline_reached', 'no_performer_selected', "
            "'payment_deadline_reached', 'no_direct_response', 'system_error')",
            name=op.f("ck_orders_expired_reason"),
        ),
        sa.CheckConstraint(
            "payout_status is null or payout_status in "
            "('blocked', 'ready', 'processing', 'succeeded', 'failed', 'cancelled')",
            name=op.f("ck_orders_payout_status"),
        ),
        sa.ForeignKeyConstraint(
            ["address_id"],
            ["addresses.id"],
            name=op.f("fk_orders_address_id_addresses"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_orders_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["selected_performer_id"],
            ["performers.id"],
            name=op.f("fk_orders_selected_performer_id_performers"),
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_orders_service_id_services"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint(
            "payout_idempotency_key",
            name=op.f("uq_orders_payout_idempotency_key"),
        ),
    )
    op.create_index(op.f("ix_orders_customer_id"), "orders", ["customer_id", "status"])
    op.create_index(
        op.f("ix_orders_selected_performer_id"),
        "orders",
        ["selected_performer_id", "status", "start_at", "end_at"],
    )
    op.create_index(op.f("ix_orders_status"), "orders", ["status", "start_at"])

    op.create_table(
        "order_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("performer_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "source in ('direct', 'pool')",
            name=op.f("ck_order_matches_source"),
        ),
        sa.CheckConstraint(
            "status in ('pending', 'active', 'selected', 'confirmed', "
            "'rejected', 'expired', 'cancelled')",
            name=op.f("ck_order_matches_status"),
        ),
        sa.CheckConstraint(
            "starts_at < ends_at",
            name=op.f("ck_order_matches_interval"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_matches_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_id"],
            ["performers.id"],
            name=op.f("fk_order_matches_performer_id_performers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_matches")),
    )
    op.create_index(
        "uq_open_match_performer_order",
        "order_matches",
        ["order_id", "performer_id"],
        unique=True,
        postgresql_where=sa.text(
            "status in ('pending', 'active', 'selected', 'confirmed')"
        ),
    )
    op.create_index(
        "uq_selected_or_confirmed_match_per_order",
        "order_matches",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("status in ('selected', 'confirmed')"),
    )
    op.create_index(
        op.f("ix_order_matches_performer_id"),
        "order_matches",
        ["performer_id", "status", "starts_at", "ends_at"],
    )
    op.create_foreign_key(
        op.f("fk_orders_selected_match_id_order_matches"),
        "orders",
        "order_matches",
        ["selected_match_id"],
        ["id"],
    )

    op.create_table(
        "order_care_objects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("care_object_id", sa.Uuid(), nullable=True),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("display_name_at_order", sa.Text(), nullable=True),
        sa.Column("summary_at_order", sa.Text(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "object_type in ('child', 'ward', 'pet')",
            name=op.f("ck_order_care_objects_object_type"),
        ),
        sa.ForeignKeyConstraint(
            ["care_object_id"],
            ["care_objects.id"],
            name=op.f("fk_order_care_objects_care_object_id_care_objects"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_care_objects_order_id_orders"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_care_objects")),
        sa.UniqueConstraint(
            "order_id",
            "care_object_id",
            name=op.f("uq_order_care_objects_order_id"),
        ),
    )

    op.create_table(
        "order_option_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("service_option_id", sa.Uuid(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_option_values_order_id_orders"),
        ),
        sa.ForeignKeyConstraint(
            ["service_option_id"],
            ["service_options.id"],
            name=op.f("fk_order_option_values_service_option_id_service_options"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_option_values")),
        sa.UniqueConstraint(
            "order_id",
            "service_option_id",
            name=op.f("uq_order_option_values_order_id"),
        ),
    )

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "from_status is null or from_status in ('draft', 'searching', "
            "'waiting_payment', 'confirmed', 'in_progress', 'waiting_report', "
            "'report_submitted', 'completed', 'cancelled', 'expired')",
            name=op.f("ck_order_status_history_from_status"),
        ),
        sa.CheckConstraint(
            "to_status in ('draft', 'searching', 'waiting_payment', 'confirmed', "
            "'in_progress', 'waiting_report', 'report_submitted', 'completed', "
            "'cancelled', 'expired')",
            name=op.f("ck_order_status_history_to_status"),
        ),
        sa.CheckConstraint(
            "actor_type in ('customer', 'performer', 'admin', 'system')",
            name=op.f("ck_order_status_history_actor_type"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_status_history_order_id_orders"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_status_history")),
    )
    op.create_index(
        op.f("ix_order_status_history_order_id"),
        "order_status_history",
        ["order_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_order_status_history_order_id"), table_name="order_status_history"
    )
    op.drop_table("order_status_history")
    op.drop_table("order_option_values")
    op.drop_table("order_care_objects")
    op.drop_constraint(
        op.f("fk_orders_selected_match_id_order_matches"),
        "orders",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_order_matches_performer_id"), table_name="order_matches")
    op.drop_index(
        "uq_selected_or_confirmed_match_per_order", table_name="order_matches"
    )
    op.drop_index("uq_open_match_performer_order", table_name="order_matches")
    op.drop_table("order_matches")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_selected_performer_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_table("orders")
    op.drop_index(
        op.f("ix_performer_calendar_overrides_performer_id"),
        table_name="performer_calendar_overrides",
    )
    op.drop_table("performer_calendar_overrides")
    op.drop_index("uq_active_performer_schedule", table_name="performer_schedules")
    op.drop_table("performer_schedules")
    op.drop_index(
        op.f("ix_performer_services_service_id"), table_name="performer_services"
    )
    op.drop_table("performer_services")
