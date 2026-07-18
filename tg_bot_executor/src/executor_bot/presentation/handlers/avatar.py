from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from executor_bot.infrastructure.http import BackendClient, BackendClientError
from executor_bot.presentation.callbacks import (
    AvatarDeleteCallback,
    AvatarOpenCallback,
    AvatarUploadCallback,
)
from executor_bot.presentation.handlers.responses import send_step
from executor_bot.presentation.middlewares import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    avatar_deleted_text,
    avatar_keyboard,
    avatar_menu_text,
    avatar_upload_step_text,
    avatar_uploaded_text,
    retry_later_text,
)

router = Router(name="avatar")


class AvatarManagement(StatesGroup):
    waiting_file = State()


@router.callback_query(AvatarOpenCallback.filter())
async def open_avatar(
    callback: CallbackQuery,
    bot: Bot,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=avatar_menu_text(),
        reply_markup=avatar_keyboard(),
    )


@router.callback_query(AvatarUploadCallback.filter())
async def start_upload(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.set_state(AvatarManagement.waiting_file)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=avatar_upload_step_text(),
    )


@router.callback_query(AvatarDeleteCallback.filter())
async def delete_avatar(
    callback: CallbackQuery,
    bot: Bot,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    try:
        await backend_client.delete_avatar(
            telegram_id=telegram_user_context.telegram_id,
        )
    except BackendClientError:
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=avatar_deleted_text(),
    )


@router.message(AvatarManagement.waiting_file, F.photo)
async def upload_photo(
    message: Message,
    state: FSMContext,
    bot: Bot,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.photo:
        return
    photo = message.photo[-1]
    content = await _download_telegram_file(bot, photo.file_id)
    await _upload(
        message,
        state,
        bot,
        backend_client,
        telegram_responder,
        telegram_user_context,
        filename="telegram-photo.jpg",
        content=content,
        content_type="image/jpeg",
    )


@router.message(AvatarManagement.waiting_file, F.document)
async def upload_document(
    message: Message,
    state: FSMContext,
    bot: Bot,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    document = message.document
    if document is None:
        return
    content = await _download_telegram_file(bot, document.file_id)
    await _upload(
        message,
        state,
        bot,
        backend_client,
        telegram_responder,
        telegram_user_context,
        filename=document.file_name or "avatar",
        content=content,
        content_type=document.mime_type or "",
    )


async def _upload(
    message: Message,
    state: FSMContext,
    bot: Bot,
    backend_client: BackendClient,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    *,
    filename: str,
    content: bytes,
    content_type: str,
) -> None:
    try:
        await backend_client.upload_avatar(
            telegram_id=telegram_user_context.telegram_id,
            filename=filename,
            content=content,
            content_type=content_type,
        )
    except BackendClientError:
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.clear()
    await send_step(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=avatar_uploaded_text(),
    )


async def _download_telegram_file(bot: Bot, file_id: str) -> bytes:
    telegram_file = await bot.get_file(file_id)
    if telegram_file.file_path is None:
        return b""
    buffer = BytesIO()
    await bot.download_file(telegram_file.file_path, destination=buffer)
    return buffer.getvalue()


__all__ = ["AvatarManagement", "router"]
