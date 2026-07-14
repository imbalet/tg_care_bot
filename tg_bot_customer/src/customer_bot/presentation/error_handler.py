import logging
from typing import Any

from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def handle_unexpected_error(event: ErrorEvent) -> bool:
    """Log unexpected aiogram errors without leaking user payloads."""
    update = event.update
    telegram_id = _telegram_id(update)
    logger.exception(
        "Unhandled Telegram update error",
        extra={
            "telegram_id": telegram_id,
            "update_id": getattr(update, "update_id", None),
            "event_type": type(update).__name__,
        },
        exc_info=event.exception,
    )
    return True


def _telegram_id(update: Any) -> int | None:
    event_from_user = getattr(update, "event_from_user", None)
    if event_from_user is not None:
        user_id = getattr(event_from_user, "id", None)
        return user_id if isinstance(user_id, int) else None

    message = getattr(update, "message", None)
    from_user = getattr(message, "from_user", None)
    user_id = getattr(from_user, "id", None)
    if isinstance(user_id, int):
        return user_id

    callback_query = getattr(update, "callback_query", None)
    from_user = getattr(callback_query, "from_user", None)
    user_id = getattr(from_user, "id", None)
    return user_id if isinstance(user_id, int) else None
