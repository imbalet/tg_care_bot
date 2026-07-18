from typing import Any

from sqlalchemy import Select


def for_update_skip_locked(
    statement: Select[Any],
    limit: int,
) -> Select[Any]:
    return statement.with_for_update(skip_locked=True).limit(limit)
