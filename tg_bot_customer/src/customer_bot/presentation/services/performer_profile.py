from aiogram import Bot
from aiogram.types import CallbackQuery, Message

from customer_bot.application.dto import PerformerProfileDTO
from customer_bot.presentation.ui.screens import PerformerProfileScreen

from .telegram_responder import TelegramResponder


async def show_performer_profile(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_id: int,
    profile: PerformerProfileDTO,
    telegram_responder: TelegramResponder,
) -> None:
    screen = PerformerProfileScreen(profile).build()
    if profile.avatar_url:
        await telegram_responder.send_photo(
            bot=bot,
            event=event,
            photo=profile.avatar_url,
            caption=screen.text,
            reply_markup=screen.reply_markup,
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )
