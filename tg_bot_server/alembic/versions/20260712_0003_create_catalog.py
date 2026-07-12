"""Create catalog.

Revision ID: 20260712_0003
Revises: 20260712_0002
Create Date: 2026-07-12 00:03:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260712_0003"
down_revision: str | None = "20260712_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "cities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cities")),
        sa.UniqueConstraint("slug", name=op.f("uq_cities_slug")),
    )
    op.create_table(
        "service_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("care_object_type", sa.Text(), nullable=False),
        sa.Column("max_objects_per_order", sa.SmallInteger(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_categories")),
        sa.UniqueConstraint("code", name=op.f("uq_service_categories_code")),
    )
    op.create_table(
        "business_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("value_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("updated_by_admin_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["updated_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_business_settings_updated_by_admin_id_admins"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_business_settings")),
        sa.UniqueConstraint("key", name=op.f("uq_business_settings_key")),
    )
    op.create_table(
        "legal_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("content_url", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_documents")),
        sa.UniqueConstraint(
            "document_type",
            "version",
            name=op.f("uq_legal_documents_document_type"),
        ),
    )
    op.create_table(
        "districts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
            name=op.f("fk_districts_city_id_cities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_districts")),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_type", sa.Text(), nullable=False),
        sa.Column("base_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("location_policy", sa.Text(), nullable=False),
        sa.Column("photo_policy", sa.Text(), nullable=False),
        sa.Column("schedule_policy", sa.Text(), nullable=False),
        sa.Column("allows_multiday", sa.Boolean(), nullable=False),
        sa.Column("min_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("max_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("duration_step_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["service_categories.id"],
            name=op.f("fk_services_category_id_service_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
        sa.UniqueConstraint("code", name=op.f("uq_services_code")),
    )
    op.create_table(
        "object_count_multipliers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("objects_count", sa.SmallInteger(), nullable=False),
        sa.Column("multiplier", sa.Numeric(8, 4), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["service_categories.id"],
            name=op.f("fk_object_count_multipliers_category_id_service_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_object_count_multipliers")),
        sa.UniqueConstraint(
            "category_id",
            "objects_count",
            name=op.f("uq_object_count_multipliers_category_id"),
        ),
    )
    op.create_table(
        "service_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("value_type", sa.Text(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_service_options_service_id_services"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_options")),
        sa.UniqueConstraint(
            "service_id",
            "code",
            name=op.f("uq_service_options_service_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("service_options")
    op.drop_table("object_count_multipliers")
    op.drop_table("services")
    op.drop_table("districts")
    op.drop_table("legal_documents")
    op.drop_table("business_settings")
    op.drop_table("service_categories")
    op.drop_table("cities")
