from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import ScreenKey


async def send_step(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    key: ScreenKey = ScreenKey.FLOW,
) -> Message | None:
    return await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        screen_key=key,
        text=text,
        reply_markup=reply_markup,
        create_new=True,
        delete_event_message=False,
    )


async def send_screen(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    key: ScreenKey = ScreenKey.MAIN,
) -> Message | None:
    return await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        screen_key=key,
        text=text,
        reply_markup=reply_markup,
    )
