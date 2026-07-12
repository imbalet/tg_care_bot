from typing import Any, cast

from executor_bot.infrastructure.redis import ExecutorRedisKeys, MessageRegistry


def test_ui_state_keys_use_executor_namespace() -> None:
    keys = ExecutorRedisKeys()

    assert (
        keys.ui_state(123, "draft_response")
        == "executor_bot:ui_state:123:draft_response"
    )
    assert (
        keys.viewed_available_orders(123)
        == "executor_bot:ui_state:123:viewed_available_orders"
    )
    assert keys.username_sync_cache(123) == "executor_bot:username_sync:123"


def test_message_registry_key_format() -> None:
    registry = MessageRegistry(
        redis=cast(Any, object()), prefix="executor_bot:messages"
    )

    assert registry.key_for("start") == "executor_bot:messages:start"
