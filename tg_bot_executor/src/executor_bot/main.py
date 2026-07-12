import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.strategy import FSMStrategy

from executor_bot.bootstrap import get_settings
from executor_bot.infrastructure.http import BackendClient
from executor_bot.infrastructure.redis import create_fsm_storage
from executor_bot.presentation.handlers import (
    fallback_router,
    registration_router,
    start_router,
)
from executor_bot.presentation.middlewares import TelegramUserContextMiddleware


async def amain() -> None:
    settings = get_settings()
    storage = create_fsm_storage(settings.redis_url)
    dispatcher = Dispatcher(
        storage=storage,
        fsm_strategy=FSMStrategy.USER_IN_TOPIC,
    )
    dispatcher.update.middleware(TelegramUserContextMiddleware())
    dispatcher.include_router(start_router)
    dispatcher.include_router(registration_router)
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
    try:
        await dispatcher.start_polling(bot, backend_client=backend_client)
    finally:
        await backend_client.close()
        await bot.session.close()
        await storage.close()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
