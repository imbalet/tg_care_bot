import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.strategy import FSMStrategy
from aiogram.methods.delete_webhook import DeleteWebhook
from aiogram.types import BotCommand
from redis.asyncio import Redis

from customer_bot.application.services import UsernameSyncService
from customer_bot.infrastructure.http import BackendClient
from customer_bot.infrastructure.logger import setup_logger
from customer_bot.infrastructure.redis import (
    RedisActiveCategoryStore,
    RedisCurrentMessageStore,
    RedisUsernameSyncCache,
    create_fsm_storage,
)
from customer_bot.infrastructure.settings import get_settings
from customer_bot.presentation.contexts import AppContext
from customer_bot.presentation.error_handler import handle_unexpected_error
from customer_bot.presentation.handlers import (
    addresses_router,
    care_objects_router,
    category_router,
    customer_orders_router,
    fallback_router,
    orders_router,
    profile_router,
    registration_router,
    start_router,
    support_router,
)
from customer_bot.presentation.middlewares import (
    AppContextMiddleware,
    CallbackMessageMiddleware,
    TelegramUserContextMiddleware,
    TelegramUsernameSyncMiddleware,
)
from customer_bot.presentation.services import TelegramResponder

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()

    setup_logger(level=settings.log_level)
    logger.info("Customer bot starting")

    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    storage = create_fsm_storage(settings.redis_url)
    dispatcher = Dispatcher(
        storage=storage,
        fsm_strategy=FSMStrategy.USER_IN_CHAT,
    )
    dispatcher.update.middleware(TelegramUserContextMiddleware())
    dispatcher.update.middleware(AppContextMiddleware())
    dispatcher.update.middleware(TelegramUsernameSyncMiddleware())
    dispatcher.callback_query.middleware(CallbackMessageMiddleware())
    dispatcher.errors.register(handle_unexpected_error)
    dispatcher.include_router(start_router)
    dispatcher.include_router(registration_router)
    dispatcher.include_router(care_objects_router)
    dispatcher.include_router(addresses_router)
    dispatcher.include_router(orders_router)
    dispatcher.include_router(profile_router)
    dispatcher.include_router(category_router)
    dispatcher.include_router(customer_orders_router)
    dispatcher.include_router(support_router)
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
                username_sync_service=username_sync_service,
            ),
        )
    except Exception:
        logger.exception("Customer bot polling stopped with unexpected error")
        raise
    finally:
        logger.info("Customer bot shutting down")
        await backend_client.close()
        await redis.aclose()
        await bot.session.close()
        await storage.close()
        logger.info("Customer bot shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
