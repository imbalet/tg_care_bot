"""Add profile data.

Revision ID: 20260713_0008
Revises: 20260712_0007
Create Date: 2026-07-13 00:08:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0008"
down_revision: str | None = "20260712_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "care_objects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("object_type", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("age_group", sa.Text(), nullable=False),
        sa.Column("species", sa.Text(), nullable=True),
        sa.Column("breed", sa.Text(), nullable=True),
        sa.Column("pet_size", sa.Text(), nullable=True),
        sa.Column("mobility_assistance_required", sa.Boolean(), nullable=True),
        sa.Column("routine_notes", sa.Text(), nullable=True),
        sa.Column("behavior_notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "object_type in ('child', 'ward', 'pet')",
            name=op.f("ck_care_objects_object_type"),
        ),
        sa.CheckConstraint(
            "age_group in ('infant', 'preschool', 'school_age', 'teenager', "
            "'adult', 'senior', 'unknown')",
            name=op.f("ck_care_objects_age_group"),
        ),
        sa.CheckConstraint(
            "pet_size is null or pet_size in ('small', 'medium', 'large', 'unknown')",
            name=op.f("ck_care_objects_pet_size"),
        ),
        sa.CheckConstraint(
            "("
            "object_type = 'pet' and species is not null and pet_size is not null"
            ") or ("
            "object_type <> 'pet' and species is null and breed is null "
            "and pet_size is null"
            ")",
            name=op.f("ck_care_objects_pet_fields"),
        ),
        sa.CheckConstraint(
            "("
            "object_type = 'ward' and mobility_assistance_required is not null"
            ") or ("
            "object_type <> 'ward' and mobility_assistance_required is null"
            ")",
            name=op.f("ck_care_objects_ward_fields"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_care_objects_customer_id_customers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_care_objects")),
    )
    op.create_index(
        op.f("ix_care_objects_customer_id"),
        "care_objects",
        ["customer_id", "object_type", "deleted_at"],
    )

    op.create_table(
        "addresses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_type", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("performer_id", sa.Uuid(), nullable=True),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("district_id", sa.Uuid(), nullable=True),
        sa.Column("address_text", sa.Text(), nullable=False),
        sa.Column("fias_id", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("geocoding_provider", sa.Text(), nullable=True),
        sa.Column("geocoding_quality", sa.Text(), nullable=True),
        sa.Column("entrance", sa.Text(), nullable=True),
        sa.Column("floor", sa.Text(), nullable=True),
        sa.Column("apartment", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "owner_type in ('customer', 'performer')",
            name=op.f("ck_addresses_owner_type"),
        ),
        sa.CheckConstraint(
            "("
            "owner_type = 'customer' and customer_id is not null "
            "and performer_id is null"
            ") or ("
            "owner_type = 'performer' and customer_id is null "
            "and performer_id is not null"
            ")",
            name=op.f("ck_addresses_owner"),
        ),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
            name=op.f("fk_addresses_city_id_cities"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_addresses_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["districts.id"],
            name=op.f("fk_addresses_district_id_districts"),
        ),
        sa.ForeignKeyConstraint(
            ["performer_id"],
            ["performers.id"],
            name=op.f("fk_addresses_performer_id_performers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_addresses")),
    )
    op.create_index(
        op.f("ix_addresses_customer_id"),
        "addresses",
        ["customer_id", "deleted_at"],
    )
    op.create_index(
        op.f("ix_addresses_performer_id"),
        "addresses",
        ["performer_id", "deleted_at"],
    )
    op.create_index(op.f("ix_addresses_fias_id"), "addresses", ["fias_id"])
    op.create_foreign_key(
        op.f("fk_performers_current_address_id_addresses"),
        "performers",
        "addresses",
        ["current_address_id"],
        ["id"],
    )

    op.create_table(
        "files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_file_id", sa.Text(), nullable=True),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("original_name", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("checksum", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('uploaded', 'deleted', 'failed')",
            name=op.f("ck_files_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_files")),
        sa.UniqueConstraint(
            "bucket",
            "storage_key",
            name=op.f("uq_files_bucket"),
        ),
    )
    op.create_table(
        "file_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "entity_type in ('customer', 'performer', 'order_report', "
            "'dispute', 'complaint')",
            name=op.f("ck_file_links_entity_type"),
        ),
        sa.CheckConstraint(
            "purpose in ('avatar', 'report_photo', 'dispute_attachment', "
            "'complaint_attachment', 'admin_attachment', 'other')",
            name=op.f("ck_file_links_purpose"),
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
            name=op.f("fk_file_links_file_id_files"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_links")),
        sa.UniqueConstraint(
            "file_id",
            "entity_type",
            "entity_id",
            "purpose",
            name=op.f("uq_file_links_file_id"),
        ),
    )
    op.create_index(
        "uq_avatar_per_entity",
        "file_links",
        ["entity_type", "entity_id"],
        unique=True,
        postgresql_where=sa.text("purpose = 'avatar'"),
    )


def downgrade() -> None:
    op.drop_index("uq_avatar_per_entity", table_name="file_links")
    op.drop_table("file_links")
    op.drop_table("files")
    op.drop_constraint(
        op.f("fk_performers_current_address_id_addresses"),
        "performers",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_addresses_fias_id"), table_name="addresses")
    op.drop_index(op.f("ix_addresses_performer_id"), table_name="addresses")
    op.drop_index(op.f("ix_addresses_customer_id"), table_name="addresses")
    op.drop_table("addresses")
    op.drop_index(op.f("ix_care_objects_customer_id"), table_name="care_objects")
    op.drop_table("care_objects")
