"""Seed MVP catalog.

Revision ID: 20260713_0009
Revises: 20260713_0008
Create Date: 2026-07-13 00:09:00
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision: str = "20260713_0009"
down_revision: str | None = "20260713_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MOSCOW_ID = UUID("11111111-1111-4111-8111-111111111111")

DISTRICT_IDS = {
    "Центр": UUID("21111111-1111-4111-8111-111111111111"),
    "Север": UUID("21111111-1111-4111-8111-111111111112"),
    "Юг": UUID("21111111-1111-4111-8111-111111111113"),
    "Запад": UUID("21111111-1111-4111-8111-111111111114"),
    "Восток": UUID("21111111-1111-4111-8111-111111111115"),
}

CATEGORY_IDS = {
    "nanny": UUID("31111111-1111-4111-8111-111111111111"),
    "caregiver": UUID("31111111-1111-4111-8111-111111111112"),
    "petsitter": UUID("31111111-1111-4111-8111-111111111113"),
}

SERVICE_IDS = {
    "nanny_care": UUID("41111111-1111-4111-8111-111111111111"),
    "caregiver_household_help": UUID("41111111-1111-4111-8111-111111111112"),
    "pet_walk": UUID("41111111-1111-4111-8111-111111111113"),
    "pet_visit_feeding": UUID("41111111-1111-4111-8111-111111111114"),
    "pet_sitting": UUID("41111111-1111-4111-8111-111111111115"),
    "pet_boarding": UUID("41111111-1111-4111-8111-111111111116"),
}

OPTION_IDS = {
    ("caregiver_household_help", "household_help"): UUID(
        "51111111-1111-4111-8111-111111111111",
    ),
    ("caregiver_household_help", "mobility_help"): UUID(
        "51111111-1111-4111-8111-111111111112",
    ),
    ("pet_visit_feeding", "feeding"): UUID("51111111-1111-4111-8111-111111111113"),
    ("pet_sitting", "feeding"): UUID("51111111-1111-4111-8111-111111111114"),
    ("pet_sitting", "walk"): UUID("51111111-1111-4111-8111-111111111115"),
    ("pet_sitting", "play"): UUID("51111111-1111-4111-8111-111111111116"),
    ("pet_sitting", "sleep"): UUID("51111111-1111-4111-8111-111111111117"),
    ("pet_boarding", "feeding"): UUID("51111111-1111-4111-8111-111111111118"),
    ("pet_boarding", "walk"): UUID("51111111-1111-4111-8111-111111111119"),
    ("pet_boarding", "play"): UUID("51111111-1111-4111-8111-111111111120"),
    ("pet_boarding", "sleep"): UUID("51111111-1111-4111-8111-111111111121"),
}

MULTIPLIER_IDS = {
    ("nanny", 1): UUID("61111111-1111-4111-8111-111111111111"),
    ("nanny", 2): UUID("61111111-1111-4111-8111-111111111112"),
    ("caregiver", 1): UUID("61111111-1111-4111-8111-111111111113"),
    ("petsitter", 1): UUID("61111111-1111-4111-8111-111111111114"),
    ("petsitter", 2): UUID("61111111-1111-4111-8111-111111111115"),
    ("petsitter", 3): UUID("61111111-1111-4111-8111-111111111116"),
}

DOCUMENT_IDS = {
    "personal_data_policy": UUID("81111111-1111-4111-8111-111111111111"),
    "personal_data_consent": UUID("81111111-1111-4111-8111-111111111112"),
    "user_agreement": UUID("81111111-1111-4111-8111-111111111113"),
    "representative_confirmation": UUID("81111111-1111-4111-8111-111111111114"),
}


def _table(name: str, *columns: str) -> sa.TableClause:
    return sa.table(
        name, *(sa.column(column, _column_type(column)) for column in columns)
    )


def _column_type(column: str) -> sa.TypeEngine[object]:
    if column == "id" or column.endswith("_id"):
        return postgresql.UUID(as_uuid=True)
    if column == "value":
        return postgresql.JSONB()
    if column in {"base_price", "multiplier"}:
        return sa.Numeric()
    if column.startswith("is_") or column.startswith("allows_"):
        return sa.Boolean()
    if column in {
        "sort_order",
        "max_objects_per_order",
        "min_duration_minutes",
        "max_duration_minutes",
        "duration_step_minutes",
        "object_count",
        "objects_count",
    }:
        return sa.Integer()
    if column in {"created_at", "updated_at", "published_at"}:
        return sa.DateTime(timezone=True)
    return sa.Text()


def _insert(table: sa.TableClause, rows: Sequence[dict[str, object]], key: str) -> None:
    if not rows:
        return
    op.execute(
        insert(table).values(list(rows)).on_conflict_do_nothing(index_elements=[key])
    )


def upgrade() -> None:
    now = datetime.now(UTC)
    _seed_city(now)
    _seed_districts(now)
    _seed_categories(now)
    _seed_services(now)
    _seed_options(now)
    _seed_multipliers(now)
    _seed_settings(now)
    _seed_legal_documents(now)


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            delete from legal_documents
            where document_type in (
                'personal_data_policy',
                'personal_data_consent',
                'user_agreement',
                'representative_confirmation'
            )
            and version = 'v1'
            """,
        ),
    )
    op.execute(
        sa.text(
            """
            delete from business_settings
            where key in (
                'minimum_order_lead_minutes',
                'matching_close_before_start_minutes',
                'direct_response_window_minutes',
                'pool_response_window_minutes',
                'payment_window_minutes',
                'payment_close_before_start_minutes',
                'start_button_before_minutes',
                'auto_waiting_report_after_end_minutes',
                'report_reminder_first_minutes',
                'report_reminder_second_minutes',
                'report_admin_escalation_minutes',
                'report_confirmation_window_minutes',
                'start_not_confirmed_escalation_minutes',
                'full_refund_before_start_minutes',
                'partial_refund_before_start_minutes',
                'refund_policy_version',
                'partial_refund_percent',
                'platform_fee_percent',
                'max_active_pool_responses',
                'notification_retention_days',
                'complaint_retention_days',
                'payment_provider_hold_limit_minutes'
            )
            """,
        ),
    )
    op.execute(
        sa.text("delete from service_options where id = any(:ids)").bindparams(
            ids=list(OPTION_IDS.values())
        )
    )
    op.execute(
        sa.text("delete from object_count_multipliers where id = any(:ids)").bindparams(
            ids=list(MULTIPLIER_IDS.values())
        )
    )
    op.execute(
        sa.text("delete from services where code = any(:codes)").bindparams(
            codes=list(SERVICE_IDS)
        )
    )
    op.execute(
        sa.text("delete from service_categories where code = any(:codes)").bindparams(
            codes=list(CATEGORY_IDS)
        )
    )
    op.execute(
        sa.text("delete from districts where id = any(:ids)").bindparams(
            ids=list(DISTRICT_IDS.values())
        )
    )
    op.execute(sa.text("delete from cities where slug = 'moscow'"))


def _seed_city(now: datetime) -> None:
    cities = _table(
        "cities",
        "id",
        "name",
        "slug",
        "timezone",
        "is_active",
        "created_at",
        "updated_at",
    )
    _insert(
        cities,
        [
            {
                "id": MOSCOW_ID,
                "name": "Москва",
                "slug": "moscow",
                "timezone": "Europe/Moscow",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
        "slug",
    )


def _seed_districts(now: datetime) -> None:
    districts = _table(
        "districts",
        "id",
        "city_id",
        "name",
        "is_active",
        "created_at",
        "updated_at",
    )
    op.execute(
        insert(districts)
        .values(
            [
                {
                    "id": district_id,
                    "city_id": MOSCOW_ID,
                    "name": name,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
                for name, district_id in DISTRICT_IDS.items()
            ],
        )
        .on_conflict_do_nothing(index_elements=["id"]),
    )


def _seed_categories(now: datetime) -> None:
    categories = _table(
        "service_categories",
        "id",
        "code",
        "name",
        "care_object_type",
        "max_objects_per_order",
        "is_active",
        "sort_order",
        "created_at",
        "updated_at",
    )
    rows = (
        ("nanny", "Няня", "child", 2, 10),
        ("caregiver", "Сиделка", "ward", 1, 20),
        ("petsitter", "Петситтер", "pet", 3, 30),
    )
    _insert(
        categories,
        [
            {
                "id": CATEGORY_IDS[code],
                "code": code,
                "name": name,
                "care_object_type": care_object_type,
                "max_objects_per_order": max_objects_per_order,
                "is_active": True,
                "sort_order": sort_order,
                "created_at": now,
                "updated_at": now,
            }
            for code, name, care_object_type, max_objects_per_order, sort_order in rows
        ],
        "code",
    )


def _seed_services(now: datetime) -> None:
    services = _table(
        "services",
        "id",
        "category_id",
        "code",
        "name",
        "description",
        "price_type",
        "base_price",
        "location_policy",
        "photo_policy",
        "schedule_policy",
        "allows_multiday",
        "min_duration_minutes",
        "max_duration_minutes",
        "duration_step_minutes",
        "is_active",
        "sort_order",
        "created_at",
        "updated_at",
    )
    rows = (
        (
            "nanny",
            "nanny_care",
            "Присмотр за ребенком",
            "hourly",
            "customer_address",
            "requires_customer_consent",
            "working_hours",
            False,
            10,
        ),
        (
            "caregiver",
            "caregiver_household_help",
            "Присмотр и бытовая помощь",
            "hourly",
            "customer_address",
            "requires_customer_consent",
            "working_hours",
            False,
            20,
        ),
        (
            "petsitter",
            "pet_walk",
            "Выгул",
            "hourly",
            "customer_address",
            "required",
            "working_hours",
            False,
            30,
        ),
        (
            "petsitter",
            "pet_visit_feeding",
            "Визит и кормление",
            "fixed",
            "customer_address",
            "required",
            "working_hours",
            False,
            40,
        ),
        (
            "petsitter",
            "pet_sitting",
            "Зооняня",
            "hourly",
            "customer_address",
            "required",
            "working_hours",
            False,
            50,
        ),
        (
            "petsitter",
            "pet_boarding",
            "Передержка",
            "started_24h",
            "performer_address",
            "required",
            "calendar_only",
            True,
            60,
        ),
    )
    _insert(
        services,
        [
            {
                "id": SERVICE_IDS[code],
                "category_id": CATEGORY_IDS[category_code],
                "code": code,
                "name": name,
                "description": name,
                "price_type": price_type,
                "base_price": Decimal("0.00"),
                "location_policy": location_policy,
                "photo_policy": photo_policy,
                "schedule_policy": schedule_policy,
                "allows_multiday": allows_multiday,
                "min_duration_minutes": None,
                "max_duration_minutes": None,
                "duration_step_minutes": 60,
                "is_active": True,
                "sort_order": sort_order,
                "created_at": now,
                "updated_at": now,
            }
            for (
                category_code,
                code,
                name,
                price_type,
                location_policy,
                photo_policy,
                schedule_policy,
                allows_multiday,
                sort_order,
            ) in rows
        ],
        "code",
    )


def _seed_options(now: datetime) -> None:
    service_options = _table(
        "service_options",
        "id",
        "service_id",
        "code",
        "name",
        "value_type",
        "is_required",
        "is_active",
        "sort_order",
        "created_at",
        "updated_at",
    )
    options = {
        "caregiver_household_help": (
            ("household_help", "Помощь по дому"),
            ("mobility_help", "Помощь при передвижении"),
        ),
        "pet_visit_feeding": (("feeding", "Кормление"),),
        "pet_sitting": (
            ("feeding", "Кормление"),
            ("walk", "Прогулка"),
            ("play", "Игры"),
            ("sleep", "Сон"),
        ),
        "pet_boarding": (
            ("feeding", "Кормление"),
            ("walk", "Прогулка"),
            ("play", "Игры"),
            ("sleep", "Сон"),
        ),
    }
    op.execute(
        insert(service_options)
        .values(
            [
                {
                    "id": OPTION_IDS[(service_code, code)],
                    "service_id": SERVICE_IDS[service_code],
                    "code": code,
                    "name": name,
                    "value_type": "boolean",
                    "is_required": False,
                    "is_active": True,
                    "sort_order": index * 10,
                    "created_at": now,
                    "updated_at": now,
                }
                for service_code, rows in options.items()
                for index, (code, name) in enumerate(rows, start=1)
            ],
        )
        .on_conflict_do_nothing(index_elements=["service_id", "code"]),
    )


def _seed_multipliers(now: datetime) -> None:
    multipliers = _table(
        "object_count_multipliers",
        "id",
        "category_id",
        "objects_count",
        "multiplier",
        "is_active",
        "created_at",
        "updated_at",
    )
    rows = (
        ("nanny", 1, "1.00"),
        ("nanny", 2, "1.40"),
        ("caregiver", 1, "1.00"),
        ("petsitter", 1, "1.00"),
        ("petsitter", 2, "1.30"),
        ("petsitter", 3, "1.50"),
    )
    op.execute(
        insert(multipliers)
        .values(
            [
                {
                    "id": MULTIPLIER_IDS[(category_code, count)],
                    "category_id": CATEGORY_IDS[category_code],
                    "objects_count": count,
                    "multiplier": Decimal(multiplier),
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
                for category_code, count, multiplier in rows
            ],
        )
        .on_conflict_do_nothing(index_elements=["category_id", "objects_count"]),
    )


def _seed_settings(now: datetime) -> None:
    settings = _table(
        "business_settings",
        "id",
        "key",
        "value",
        "value_type",
        "description",
        "updated_by_admin_id",
        "created_at",
        "updated_at",
    )
    rows: tuple[tuple[str, object, str], ...] = (
        ("minimum_order_lead_minutes", 360, "number"),
        ("matching_close_before_start_minutes", 210, "number"),
        ("direct_response_window_minutes", 180, "number"),
        ("pool_response_window_minutes", 180, "number"),
        ("payment_window_minutes", 30, "number"),
        ("payment_close_before_start_minutes", 180, "number"),
        ("start_button_before_minutes", 15, "number"),
        ("auto_waiting_report_after_end_minutes", 15, "number"),
        ("report_reminder_first_minutes", 30, "number"),
        ("report_reminder_second_minutes", 60, "number"),
        ("report_admin_escalation_minutes", 120, "number"),
        ("report_confirmation_window_minutes", 1440, "number"),
        ("start_not_confirmed_escalation_minutes", 15, "number"),
        ("full_refund_before_start_minutes", 720, "number"),
        ("partial_refund_before_start_minutes", 360, "number"),
        ("refund_policy_version", "v1", "string"),
        ("partial_refund_percent", None, "number"),
        ("platform_fee_percent", 5, "number"),
        ("max_active_pool_responses", 5, "number"),
        ("notification_retention_days", 30, "number"),
        ("complaint_retention_days", 30, "number"),
        ("payment_provider_hold_limit_minutes", None, "number"),
    )
    _insert(
        settings,
        [
            {
                "id": UUID(f"71111111-1111-4111-8111-{index:012d}"),
                "key": key,
                "value": _jsonb_literal(value),
                "value_type": value_type,
                "description": f"MVP setting {key}",
                "updated_by_admin_id": None,
                "created_at": now,
                "updated_at": now,
            }
            for index, (key, value, value_type) in enumerate(rows, start=1)
        ],
        "key",
    )


def _jsonb_literal(value: object) -> sa.Cast[object]:
    return sa.cast(sa.literal(json.dumps(value)), postgresql.JSONB)


def _seed_legal_documents(now: datetime) -> None:
    legal_documents = _table(
        "legal_documents",
        "id",
        "document_type",
        "version",
        "content_url",
        "is_active",
        "published_at",
        "created_at",
    )
    op.execute(
        insert(legal_documents)
        .values(
            [
                {
                    "id": document_id,
                    "document_type": document_type,
                    "version": "v1",
                    "content_url": f"https://example.invalid/legal/{document_type}/v1",
                    "is_active": True,
                    "published_at": now,
                    "created_at": now,
                }
                for document_type, document_id in DOCUMENT_IDS.items()
            ],
        )
        .on_conflict_do_nothing(index_elements=["document_type", "version"]),
    )
