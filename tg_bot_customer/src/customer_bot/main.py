import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.strategy import FSMStrategy
from aiogram.methods.delete_webhook import DeleteWebhook
from aiogram.types import BotCommand
from redis.asyncio import Redis

from customer_bot.infrastructure.http import BackendClient
from customer_bot.infrastructure.logger import setup_logger
from customer_bot.infrastructure.redis import create_fsm_storage
from customer_bot.infrastructure.settings import get_settings
from customer_bot.presentation.contexts import AppContext
from customer_bot.presentation.handlers import (
    addresses_router,
    care_objects_router,
    fallback_router,
    orders_router,
    registration_router,
    start_router,
)
from customer_bot.presentation.middlewares import (
    TelegramTopicsEnsureMiddleware,
    TelegramUserContextMiddleware,
    TelegramUsernameSyncMiddleware,
)
from customer_bot.presentation.services import MenuManager, TelegramTopicSetupService


async def main() -> None:
    settings = get_settings()

    setup_logger(level=settings.log_level)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    storage = create_fsm_storage(settings.redis_url)
    dispatcher = Dispatcher(
        storage=storage,
        fsm_strategy=FSMStrategy.USER_IN_TOPIC,
    )
    dispatcher.update.middleware(TelegramUserContextMiddleware())
    dispatcher.update.middleware(TelegramUsernameSyncMiddleware(redis))
    dispatcher.update.middleware(TelegramTopicsEnsureMiddleware())
    dispatcher.include_router(start_router)
    dispatcher.include_router(registration_router)
    dispatcher.include_router(care_objects_router)
    dispatcher.include_router(addresses_router)
    dispatcher.include_router(orders_router)
    dispatcher.include_router(fallback_router)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    backend_client = BackendClient(
        base_url=settings.backend_url,
        service_key=settings.service_key,
        timeout_seconds=settings.request_timeout_seconds,
    )

    menu_manager = MenuManager(redis)
    topic_setup_service = TelegramTopicSetupService(redis)
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Открыть главное меню"),
                BotCommand(command="menu", description="Вернуться в главное меню"),
                BotCommand(command="help", description="Помощь"),
            ],
        )
        await bot(DeleteWebhook(drop_pending_updates=True))
        await dispatcher.start_polling(
            bot,
            app_context=AppContext(
                backend_client=backend_client,
                menu_manager=menu_manager,
                topic_setup_service=topic_setup_service,
            ),
        )
    finally:
        await backend_client.close()
        await redis.aclose()
        await bot.session.close()
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
