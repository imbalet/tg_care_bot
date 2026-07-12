from aiogram import Router
from aiogram.types import Message

router = Router(name="fallback")


@router.message()
async def unknown_message(message: Message) -> None:
    await message.answer("Команда пока не поддерживается.")


__all__ = ["router", "unknown_message"]
