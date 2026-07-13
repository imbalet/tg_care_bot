from aiogram import Bot, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from executor_bot.infrastructure.http import BackendClient, BackendClientError
from executor_bot.presentation.handlers.registration import start_registration
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.services import MenuManager, TelegramTopicSetupService
from executor_bot.presentation.ui import (
    executor_main_menu_text,
    main_menu_keyboard,
    no_invitation_text,
    retry_later_text,
)

router = Router(name="start")


@router.message(CommandStart())
async def start(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendClient,
    menu_manager: MenuManager,
    topic_setup_service: TelegramTopicSetupService,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        registration_state = await backend_client.get_registration_state(
            telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await message.answer(retry_later_text())
        return
    if registration_state.state == "registered":
        await state.clear()
        if telegram_user_context.chat_id is not None:
            await topic_setup_service.ensure(
                bot=bot,
                backend_client=backend_client,
                telegram_id=telegram_user_context.telegram_id,
                chat_id=telegram_user_context.chat_id,
            )
        topic_key = await menu_manager.topic_key(
            telegram_id=telegram_user_context.telegram_id,
            message_thread_id=telegram_user_context.message_thread_id,
        )
        await menu_manager.send_or_replace(
            bot=bot,
            message=message,
            telegram_id=telegram_user_context.telegram_id,
            topic_key=topic_key,
            text=executor_main_menu_text(topic_key),
            reply_markup=main_menu_keyboard(topic_key),
            message_thread_id=telegram_user_context.message_thread_id,
        )
        return
    if registration_state.state == "no_invitation":
        await state.clear()
        await message.answer(no_invitation_text())
        return
    await start_registration(message, state, backend_client)


__all__ = ["router", "start"]
