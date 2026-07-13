from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramTopicSetupService

from .helpers import get_app_context, get_telegram_user_context


class TelegramTopicsEnsureMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        context = get_telegram_user_context(data)
        app_context = get_app_context(data)
        backend_client = app_context.backend_client
        topic_setup_service = app_context.topic_setup_service
        bot = data.get("bot")
        if isinstance(bot, Bot) and context.chat_id is not None:
            await self._ensure(
                bot=bot,
                backend_client=backend_client,
                topic_setup_service=topic_setup_service,
                context=context,
            )
        return await handler(event, data)

    async def _ensure(
        self,
        *,
        bot: Bot,
        backend_client: BackendPort,
        topic_setup_service: TelegramTopicSetupService,
        context: TelegramUserContext,
    ) -> None:
        try:
            if await backend_client.get_customer_profile(context.telegram_id) is None:
                return
            await topic_setup_service.ensure(
                bot=bot,
                backend_client=backend_client,
                telegram_id=context.telegram_id,
                chat_id=context.chat_id or context.telegram_id,
            )
        except BackendClientError:
            return
