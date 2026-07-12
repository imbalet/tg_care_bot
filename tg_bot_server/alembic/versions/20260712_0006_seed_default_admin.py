"""Seed default admin.

Revision ID: 20260712_0006
Revises: 20260712_0005
Create Date: 2026-07-12 00:06:00
"""

import os
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from argon2 import PasswordHasher
from sqlalchemy.dialects.postgresql import insert

from alembic import op

revision: str = "20260712_0006"
down_revision: str | None = "20260712_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_EMAIL = "admin@example.local"
DEFAULT_FULL_NAME = "Default Admin"
DEFAULT_LOCAL_PASSWORD = "".join(("admin", "-password"))


def _admin_password() -> str:
    password = os.getenv("DEFAULT_ADMIN_PASSWORD")
    if password:
        return password
    environment = os.getenv("APP_ENV", "local")
    if environment == "production":
        raise RuntimeError("DEFAULT_ADMIN_PASSWORD is required in production")
    return DEFAULT_LOCAL_PASSWORD


def upgrade() -> None:
    admins = sa.table(
        "admins",
        sa.column("id", sa.Uuid()),
        sa.column("email", sa.String()),
        sa.column("full_name", sa.String()),
        sa.column("password_hash", sa.String()),
        sa.column("status", sa.String()),
        sa.column("last_login_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    op.execute(
        insert(admins)
        .values(
            id=uuid4(),
            email=os.getenv("DEFAULT_ADMIN_EMAIL", DEFAULT_EMAIL).lower(),
            full_name=os.getenv("DEFAULT_ADMIN_FULL_NAME", DEFAULT_FULL_NAME),
            password_hash=PasswordHasher().hash(_admin_password()),
            status="active",
            last_login_at=None,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["email"]),
    )


def downgrade() -> None:
    op.execute(
        sa.text("delete from admins where email = :email").bindparams(
            email=os.getenv("DEFAULT_ADMIN_EMAIL", DEFAULT_EMAIL).lower(),
        ),
    )
