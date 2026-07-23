"""Allow worker claim state for refunds."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260723_0025"
down_revision: str | None = "20260723_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_refunds_status", "refunds", type_="check")
    op.create_check_constraint(
        "ck_refunds_status",
        "refunds",
        "status in ('pending', 'processing', 'succeeded', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_refunds_status", "refunds", type_="check")
    op.create_check_constraint(
        "ck_refunds_status",
        "refunds",
        "status in ('pending', 'succeeded', 'failed')",
    )
