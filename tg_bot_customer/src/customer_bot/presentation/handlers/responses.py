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
    create_new: bool = False,
    delete_event_message: bool = False,
) -> Message | None:
    return await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=text,
        reply_markup=reply_markup,
        create_new=create_new,
        delete_event_message=delete_event_message,
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
    return await send_step(
        bot=bot,
        event=event,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=text,
        reply_markup=reply_markup,
    )
