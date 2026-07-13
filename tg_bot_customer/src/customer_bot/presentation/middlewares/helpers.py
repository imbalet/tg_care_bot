from logging import getLogger
from typing import Any, cast

from customer_bot.presentation.contexts import AppContext, TelegramUserContext

logger = getLogger(__name__)


def get_app_context(data: dict[Any, Any]) -> AppContext:
    app_context = data.get("app_context")
    if not app_context:
        logger.warning("AppContext not found in data")
    return cast(AppContext, app_context)


def set_app_context(data: dict[Any, Any], app_context: AppContext) -> None:
    data["app_context"] = app_context


def get_telegram_user_context(data: dict[Any, Any]) -> TelegramUserContext:
    user_context = data.get("telegram_user_context")
    if not user_context:
        logger.warning("TelegramUserContext not found in data")
    return cast(TelegramUserContext, user_context)


def set_telegram_user_context(
    data: dict[Any, Any], user_context: TelegramUserContext
) -> None:
    data["telegram_user_context"] = user_context
