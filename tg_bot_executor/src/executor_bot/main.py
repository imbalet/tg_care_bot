import asyncio
import logging

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
from executor_bot.infrastructure.logger import LogLevel, setup_logger
from executor_bot.infrastructure.redis import (
    RedisActiveCategoryStore,
    RedisCurrentMessageStore,
    RedisUsernameSyncCache,
    RedisViewedAvailableOrdersStore,
    create_fsm_storage,
)
from executor_bot.presentation.contexts import AppContext
from executor_bot.presentation.error_handler import handle_unexpected_error
from executor_bot.presentation.handlers import (
    addresses_router,
    avatar_router,
    category_router,
    fallback_router,
    orders_router,
    registration_router,
    services_calendar_router,
    start_router,
)
from executor_bot.presentation.middlewares import (
    AppContextMiddleware,
    TelegramUserContextMiddleware,
    TelegramUsernameSyncMiddleware,
)
from executor_bot.presentation.services import TelegramResponder

logger = logging.getLogger(__name__)


async def amain() -> None:
    settings = get_settings()

    setup_logger(level=LogLevel(settings.log_level))
    logger.info("Executor bot starting")

    storage = create_fsm_storage(settings.redis_url)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    dispatcher = Dispatcher(
        storage=storage,
        fsm_strategy=FSMStrategy.USER_IN_CHAT,
    )
    dispatcher.update.middleware(TelegramUserContextMiddleware())
    dispatcher.update.middleware(AppContextMiddleware())
    dispatcher.update.middleware(TelegramUsernameSyncMiddleware())
    dispatcher.errors.register(handle_unexpected_error)
    dispatcher.include_router(start_router)
    dispatcher.include_router(registration_router)
    dispatcher.include_router(addresses_router)
    dispatcher.include_router(avatar_router)
    dispatcher.include_router(services_calendar_router)
    dispatcher.include_router(category_router)
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
    current_message_store = RedisCurrentMessageStore(redis)
    active_category_store = RedisActiveCategoryStore(redis)
    viewed_available_orders_store = RedisViewedAvailableOrdersStore(redis)
    username_sync_cache = RedisUsernameSyncCache(redis)
    username_sync_service = UsernameSyncService(
        backend=backend_client,
        cache=username_sync_cache,
    )
    telegram_responder = TelegramResponder(
        message_store=current_message_store,
    )
    try:
        logger.info("Configuring Telegram bot commands")
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Открыть главное меню"),
                BotCommand(command="menu", description="Вернуться в главное меню"),
                BotCommand(command="help", description="Помощь"),
            ],
        )
        await bot(DeleteWebhook(drop_pending_updates=True))
        logger.info("Starting Telegram polling")
        await dispatcher.start_polling(
            bot,
            app_context=AppContext(
                backend_client=backend_client,
                telegram_responder=telegram_responder,
                active_category_store=active_category_store,
                viewed_available_orders_store=viewed_available_orders_store,
                username_sync_service=username_sync_service,
            ),
        )
    except Exception:
        logger.exception("Executor bot polling stopped with unexpected error")
        raise
    finally:
        logger.info("Executor bot shutting down")
        await backend_client.close()
        await redis.aclose()
        await bot.session.close()
        await storage.close()
        logger.info("Executor bot shutdown complete")


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
