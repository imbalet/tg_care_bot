"""Create performers.

Revision ID: 20260712_0005
Revises: 20260712_0004
Create Date: 2026-07-12 00:05:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260712_0005"
down_revision: str | None = "20260712_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "performers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("telegram_username", sa.Text(), nullable=True),
        sa.Column("contact_method", sa.Text(), nullable=False),
        sa.Column("city_id", sa.Uuid(), nullable=False),
        sa.Column("about_text", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("is_accepting_orders", sa.Boolean(), nullable=False),
        sa.Column("current_address_id", sa.Uuid(), nullable=True),
        sa.Column("payment_recipient_id", sa.Text(), nullable=True),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "contact_method in ('telegram', 'phone', 'both')",
            name=op.f("ck_performers_contact_method"),
        ),
        sa.CheckConstraint(
            "status in ('invited', 'profile_pending', 'active', 'blocked', "
            "'deletion_pending', 'anonymized')",
            name=op.f("ck_performers_status"),
        ),
        sa.ForeignKeyConstraint(
            ["city_id"],
            ["cities.id"],
            name=op.f("fk_performers_city_id_cities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performers")),
        sa.UniqueConstraint("telegram_id", name=op.f("uq_performers_telegram_id")),
        sa.UniqueConstraint(
            "payment_recipient_id",
            name=op.f("uq_performers_payment_recipient_id"),
        ),
    )
    op.create_table(
        "performer_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_by_admin_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_performer_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status in ('pending', 'accepted', 'expired', 'cancelled')",
            name=op.f("ck_performer_invitations_status"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["admins.id"],
            name=op.f("fk_performer_invitations_created_by_admin_id_admins"),
        ),
        sa.ForeignKeyConstraint(
            ["accepted_performer_id"],
            ["performers.id"],
            name=op.f("fk_performer_invitations_accepted_performer_id_performers"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performer_invitations")),
    )
    op.create_foreign_key(
        op.f("fk_legal_acceptances_performer_id_performers"),
        "legal_acceptances",
        "performers",
        ["performer_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_legal_acceptances_performer_id_performers"),
        "legal_acceptances",
        type_="foreignkey",
    )
    op.drop_table("performer_invitations")
    op.drop_table("performers")
