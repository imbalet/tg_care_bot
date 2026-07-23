"""Set the agreed partial cancellation refund percentage."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0026"
down_revision: str | None = "20260723_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "update business_settings "
            "set value = cast(:value as jsonb), value_type = 'number', "
            "updated_at = now() where key = 'partial_refund_percent'",
        ).bindparams(value="50"),
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "update business_settings "
            "set value = cast(:value as jsonb), updated_at = now() "
            "where key = 'partial_refund_percent'",
        ).bindparams(value="null"),
    )
