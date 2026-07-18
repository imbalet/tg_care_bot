import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.strategy import FSMStrategy
from aiogram.methods.delete_webhook import DeleteWebhook
from aiogram.types import BotCommand
from redis.asyncio import Redis

from executor_bot.application.services import UsernameSyncService
from executor_bot.bootstrap import get_settings
from executor_bot.infrastructure.http import BackendClient
from executor_bot.infrastructure.redis import (
    RedisActiveCategoryStore,
    RedisUsernameSyncCache,
    create_fsm_storage,
)
from executor_bot.presentation.contexts import AppContext
from executor_bot.presentation.handlers import (
    addresses_router,
    avatar_router,
    fallback_router,
    registration_router,
    services_calendar_router,
    start_router,
)
from executor_bot.presentation.middlewares import (
    AppContextMiddleware,
    TelegramTopicsEnsureMiddleware,
    TelegramUserContextMiddleware,
    TelegramUsernameSyncMiddleware,
)
from executor_bot.presentation.services import MenuManager, TelegramTopicSetupService


async def amain() -> None:
    settings = get_settings()
    storage = create_fsm_storage(settings.redis_url)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    dispatcher = Dispatcher(
        storage=storage,
        fsm_strategy=FSMStrategy.USER_IN_TOPIC,
    )
    dispatcher.update.middleware(TelegramUserContextMiddleware())
    dispatcher.update.middleware(AppContextMiddleware())
    dispatcher.update.middleware(TelegramUsernameSyncMiddleware())
    dispatcher.update.middleware(TelegramTopicsEnsureMiddleware())
    dispatcher.include_router(start_router)
    dispatcher.include_router(registration_router)
    dispatcher.include_router(addresses_router)
    dispatcher.include_router(avatar_router)
    dispatcher.include_router(services_calendar_router)
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
    active_category_store = RedisActiveCategoryStore(redis)
    username_sync_cache = RedisUsernameSyncCache(redis)
    username_sync_service = UsernameSyncService(
        backend=backend_client,
        cache=username_sync_cache,
    )
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
                active_category_store=active_category_store,
                username_sync_service=username_sync_service,
            ),
            menu_manager=menu_manager,
            topic_setup_service=topic_setup_service,
        )
    finally:
        await backend_client.close()
        await redis.aclose()
        await bot.session.close()
        await storage.close()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
