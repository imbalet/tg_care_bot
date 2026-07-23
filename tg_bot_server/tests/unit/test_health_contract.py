import pytest

from backend.common.infrastructure import RedisKeyNamespace


@pytest.mark.unit
def test_redis_namespace_is_stable() -> None:
    keys = RedisKeyNamespace(prefix="backend")

    assert keys.admin_session("session-1") == "backend:admin:sessions:session-1"
