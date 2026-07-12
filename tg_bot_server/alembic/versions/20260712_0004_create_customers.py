"""Create customers.

Revision ID: 20260712_0004
Revises: 20260712_0003
Create Date: 2026-07-12 00:04:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260712_0004"
down_revision: str | None = "20260712_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("telegram_username", sa.Text(), nullable=True),
        sa.Column("contact_method", sa.Text(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "contact_method in ('telegram', 'phone', 'both')",
            name=op.f("ck_customers_contact_method"),
        ),
        sa.CheckConstraint(
            "status in ('active', 'blocked', 'deletion_pending', 'anonymized')",
            name=op.f("ck_customers_status"),
        ),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
            name=op.f("fk_customers_city_id_cities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint("telegram_id", name=op.f("uq_customers_telegram_id")),
    )
    op.create_table(
        "legal_acceptances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("performer_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "account_type in ('customer', 'performer')",
            name=op.f("ck_legal_acceptances_account_type"),
        ),
        sa.CheckConstraint(
            "("
            "account_type = 'customer' "
            "and customer_id is not null "
            "and performer_id is null"
            ") or ("
            "account_type = 'performer' "
            "and customer_id is null "
            "and performer_id is not null"
            ")",
            name=op.f("ck_legal_acceptances_owner"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_legal_acceptances_customer_id_customers"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["legal_documents.id"],
            name=op.f("fk_legal_acceptances_document_id_legal_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legal_acceptances")),
        sa.UniqueConstraint(
            "customer_id",
            "document_id",
            name=op.f("uq_legal_acceptances_customer_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("legal_acceptances")
    op.drop_table("customers")
