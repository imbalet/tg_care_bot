from aiogram import Bot

from customer_bot.application.dto import TelegramTopicDTO
from customer_bot.application.services import TelegramTopicSetupService as TopicService
from customer_bot.presentation.adapters import AiogramBotAdapter


class TelegramTopicSetupService:
    def __init__(self, service: TopicService) -> None:
        self._service = service

    async def ensure(
        self,
        *,
        bot: Bot,
        backend_client: object,
        telegram_id: int,
        chat_id: int,
    ) -> tuple[TelegramTopicDTO, ...]:
        _ = backend_client
        return await self._service.ensure(
            bot=AiogramBotAdapter(bot),
            telegram_id=telegram_id,
            chat_id=chat_id,
        )
