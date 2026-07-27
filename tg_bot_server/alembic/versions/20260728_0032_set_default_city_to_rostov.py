"""Set the MVP default city to Rostov-on-Don.

Revision ID: 20260728_0032
Revises: 20260728_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260728_0032"
down_revision: str | None = "20260728_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE cities
            SET name = :name, slug = :slug
            WHERE slug = :old_slug
            """
        ).bindparams(
            name="Ростов-на-Дону",
            slug="rostov-on-don",
            old_slug="moscow",
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE cities
            SET name = :name, slug = :slug
            WHERE slug = :new_slug
            """
        ).bindparams(
            name="Москва",
            slug="moscow",
            new_slug="rostov-on-don",
        )
    )
