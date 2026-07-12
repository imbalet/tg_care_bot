from sqlalchemy import Select


def for_update_skip_locked[StatementT: Select[tuple[object, ...]]](
    statement: StatementT,
    limit: int,
) -> StatementT:
    return statement.with_for_update(skip_locked=True).limit(limit)


__all__ = ["for_update_skip_locked"]
