from aiogram import Bot
from aiogram.types import CallbackQuery, Message, ReplyMarkupUnion

from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramResponder


async def send_step(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    text: str,
    reply_markup: ReplyMarkupUnion | None = None,
) -> Message | None:
    return await telegram_responder.send_step(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=reply_markup,
    )


async def send_screen(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    text: str,
    reply_markup: ReplyMarkupUnion | None = None,
) -> Message | None:
    return await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=reply_markup,
    )
