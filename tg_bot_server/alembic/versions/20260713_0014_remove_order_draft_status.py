"""Remove order draft status.

Revision ID: 20260713_0014
Revises: 20260713_0013
Create Date: 2026-07-13 04:45:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260713_0014"
down_revision: str | None = "20260713_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORDER_STATUSES = (
    "'searching', 'waiting_payment', 'confirmed', 'in_progress', "
    "'waiting_report', 'report_submitted', 'completed', 'cancelled', 'expired'"
)
ORDER_STATUSES_WITH_DRAFT = (
    "'draft', 'searching', 'waiting_payment', 'confirmed', 'in_progress', "
    "'waiting_report', 'report_submitted', 'completed', 'cancelled', 'expired'"
)


def upgrade() -> None:
    op.execute("update orders set status = 'searching' where status = 'draft'")
    op.execute(
        "update order_status_history set from_status = null "
        "where from_status = 'draft'",
    )
    op.execute(
        "update order_status_history set to_status = 'searching' "
        "where to_status = 'draft'",
    )
    op.drop_constraint(op.f("ck_orders_status"), "orders", type_="check")
    op.create_check_constraint(
        op.f("ck_orders_status"),
        "orders",
        f"status in ({ORDER_STATUSES})",
    )
    op.drop_constraint(
        op.f("ck_order_status_history_from_status"),
        "order_status_history",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_order_status_history_from_status"),
        "order_status_history",
        f"from_status is null or from_status in ({ORDER_STATUSES})",
    )
    op.drop_constraint(
        op.f("ck_order_status_history_to_status"),
        "order_status_history",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_order_status_history_to_status"),
        "order_status_history",
        f"to_status in ({ORDER_STATUSES})",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_orders_status"), "orders", type_="check")
    op.create_check_constraint(
        op.f("ck_orders_status"),
        "orders",
        f"status in ({ORDER_STATUSES_WITH_DRAFT})",
    )
    op.drop_constraint(
        op.f("ck_order_status_history_from_status"),
        "order_status_history",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_order_status_history_from_status"),
        "order_status_history",
        f"from_status is null or from_status in ({ORDER_STATUSES_WITH_DRAFT})",
    )
    op.drop_constraint(
        op.f("ck_order_status_history_to_status"),
        "order_status_history",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_order_status_history_to_status"),
        "order_status_history",
        f"to_status in ({ORDER_STATUSES_WITH_DRAFT})",
    )
