"""Remove the standalone pet visit feeding service.

Revision ID: 20260806_0038
Revises: 20260801_0037
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "20260806_0038"
down_revision: str | None = "20260801_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SERVICE_ID = UUID("41111111-1111-4111-8111-111111111114")
OPTION_ID = UUID("51111111-1111-4111-8111-111111111113")
CATEGORY_ID = UUID("31111111-1111-4111-8111-111111111113")


def upgrade() -> None:
    connection = op.get_bind()
    service_exists = connection.scalar(
        sa.text("SELECT 1 FROM services WHERE code = 'pet_visit_feeding'")
    )
    if service_exists is None:
        return

    order_count = connection.scalar(
        sa.text("SELECT count(*) FROM orders WHERE service_id = :service_id"),
        {"service_id": SERVICE_ID},
    )
    if order_count:
        raise RuntimeError(
            "Cannot remove pet_visit_feeding: existing orders reference this service"
        )

    connection.execute(
        sa.text("DELETE FROM performer_services WHERE service_id = :service_id"),
        {"service_id": SERVICE_ID},
    )
    connection.execute(
        sa.text("DELETE FROM service_options WHERE service_id = :service_id"),
        {"service_id": SERVICE_ID},
    )
    connection.execute(
        sa.text("DELETE FROM services WHERE id = :service_id"),
        {"service_id": SERVICE_ID},
    )


def downgrade() -> None:
    connection = op.get_bind()
    now = datetime.now(UTC)
    connection.execute(
        sa.text(
            """
            INSERT INTO services (
                id, category_id, code, name, description, price_type,
                base_price, location_policy, photo_policy, schedule_policy,
                allows_multiday, min_duration_minutes, max_duration_minutes,
                duration_step_minutes, is_active, sort_order, created_at, updated_at
            ) VALUES (
                :id, :category_id, :code, :name, :description, :price_type,
                :base_price, :location_policy, :photo_policy, :schedule_policy,
                false, NULL, NULL, 60, true, 40, :created_at, :updated_at
            )
            """
        ),
        {
            "id": SERVICE_ID,
            "category_id": CATEGORY_ID,
            "code": "pet_visit_feeding",
            "name": "Визит и кормление",
            "description": "Визит и кормление",
            "price_type": "fixed",
            "base_price": "300.00",
            "location_policy": "customer_address",
            "photo_policy": "required",
            "schedule_policy": "working_hours",
            "created_at": now,
            "updated_at": now,
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO service_options (
                id, service_id, code, name, value_type, is_required,
                is_active, sort_order, created_at, updated_at
            ) VALUES (
                :id, :service_id, 'feeding', 'Кормление', 'boolean',
                false, true, 10, :created_at, :updated_at
            )
            """
        ),
        {
            "id": OPTION_ID,
            "service_id": SERVICE_ID,
            "created_at": now,
            "updated_at": now,
        },
    )
