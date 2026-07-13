from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot
from aiogram.types import TelegramObject

from executor_bot.infrastructure.http import BackendClient, BackendClientError
from executor_bot.presentation.middlewares.user_context import TelegramUserContext
from executor_bot.presentation.services import TelegramTopicSetupService


class TelegramTopicsEnsureMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        context = data.get("telegram_user_context")
        backend_client = data.get("backend_client")
        topic_setup_service = data.get("topic_setup_service")
        bot = data.get("bot")
        if (
            isinstance(context, TelegramUserContext)
            and isinstance(backend_client, BackendClient)
            and isinstance(topic_setup_service, TelegramTopicSetupService)
            and isinstance(bot, Bot)
            and context.chat_id is not None
        ):
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
        backend_client: BackendClient,
        topic_setup_service: TelegramTopicSetupService,
        context: TelegramUserContext,
    ) -> None:
        try:
            state = await backend_client.get_registration_state(context.telegram_id)
            if state.state != "registered":
                return
            await topic_setup_service.ensure(
                bot=bot,
                backend_client=backend_client,
                telegram_id=context.telegram_id,
                chat_id=context.chat_id or context.telegram_id,
            )
        except BackendClientError:
            return


__all__ = ["TelegramTopicsEnsureMiddleware"]
