from backend.common.domain import NotFoundError

# Temporary kill switch for the direct-order flow. Restore the flow by changing
# this value to True; the direct implementation is intentionally kept intact.
DIRECT_ORDERS_ENABLED = False


def ensure_direct_orders_enabled() -> None:
    if not DIRECT_ORDERS_ENABLED:
        raise NotFoundError("Direct orders are temporarily unavailable")


__all__ = ["DIRECT_ORDERS_ENABLED", "ensure_direct_orders_enabled"]
