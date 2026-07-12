from typing import Any, cast

from sqlalchemy import column, select, table
from sqlalchemy.dialects import postgresql

from backend.common.infrastructure import RedisKeyNamespace, backend_redis_keys
from backend.common.infrastructure.database import for_update_skip_locked


def test_backend_redis_keys_use_explicit_namespaces() -> None:
    keys = RedisKeyNamespace(prefix="backend")

    assert keys.admin_session("session-1") == "backend:admin:sessions:session-1"
    assert keys.technical_cache("cities") == "backend:cache:technical:cities"
    assert keys.rate_limit("internal", "user-1") == "backend:rate_limit:internal:user-1"
    assert backend_redis_keys.admin_session("session-1").startswith("backend:")


def test_for_update_skip_locked_adds_locking_and_limit() -> None:
    records = table("records", column("id"))
    statement = for_update_skip_locked(select(records), limit=10)
    postgresql_dialect = cast(Any, postgresql.dialect)()
    compiled = str(
        statement.compile(
            dialect=postgresql_dialect,
            compile_kwargs={"literal_binds": True},
        ),
    )

    assert "FOR UPDATE" in compiled
    assert "SKIP LOCKED" in compiled
    assert "LIMIT 10" in compiled
