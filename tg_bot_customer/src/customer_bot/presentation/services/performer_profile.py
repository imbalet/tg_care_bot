from uuid import UUID

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
    back_order_id: UUID | None = None,
    back_group: str = "active",
    back_page: int = 1,
) -> None:
    screen = PerformerProfileScreen(
        profile,
        back_order_id=back_order_id,
        back_group=back_group,
        back_page=back_page,
    ).build()
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_id,
        text=screen.text,
        reply_markup=screen.reply_markup,
    )
