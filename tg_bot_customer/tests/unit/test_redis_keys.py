from typing import Any, cast

from customer_bot.infrastructure.redis import CustomerRedisKeys, MessageRegistry


def test_ui_state_keys_use_customer_namespace() -> None:
    keys = CustomerRedisKeys()

    assert keys.ui_state(123, "draft_order") == "customer_bot:ui_state:123:draft_order"
    assert (
        keys.viewed_available_orders(123)
        == "customer_bot:ui_state:123:viewed_available_orders"
    )
    assert keys.username_sync_cache(123) == "customer_bot:username_sync:123"
    assert keys.active_category(123) == "tg:customer:123:active_category"
    assert keys.current_message(123) == "customer_bot:screen:123:current"


def test_message_registry_key_format() -> None:
    registry = MessageRegistry(
        redis=cast(Any, object()), prefix="customer_bot:messages"
    )

    assert registry.key_for("start") == "customer_bot:messages:start"
