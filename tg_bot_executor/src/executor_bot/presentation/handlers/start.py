from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from executor_bot.infrastructure.http import BackendClient, BackendClientError

router = Router(name="start")


@router.message(CommandStart())
async def start(message: Message, backend_client: BackendClient) -> None:
    try:
        await backend_client.ping()
    except BackendClientError:
        await message.answer("Сервис временно недоступен. Попробуйте позже.")
        return
    await message.answer("Бот исполнителя запущен.")


__all__ = ["router", "start"]
