import logging
from io import BytesIO
from uuid import UUID

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    OrderDisputeOpenCallback,
    SupportRequestOpenCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import RetryLaterScreen

router = Router(name="support_requests")
logger = logging.getLogger(__name__)


class SupportForm(StatesGroup):
    request_type = State()
    request_text = State()
    complaint_category = State()
    complaint_text = State()
    dispute_text = State()
    dispute_attachment = State()


async def _prompt(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_responder: TelegramResponder,
    telegram_id: int,
    text: str,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_id,
        text=text,
        reply_markup=None,
        create_new=True,
    )


async def start_support_request(
    *,
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    order_id: UUID | None,
) -> None:
    await state.set_state(SupportForm.request_type)
    await state.update_data(support_order_id=str(order_id) if order_id else None)
    await _prompt(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            "<b>Обращение в поддержку</b>\n\n"
            "Укажите тип обращения одним коротким словом."
        ),
    )


async def start_complaint(
    *,
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    order_id: UUID,
) -> None:
    await state.set_state(SupportForm.complaint_category)
    await state.update_data(complaint_order_id=str(order_id))
    await _prompt(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        text="<b>Жалоба</b>\n\nУкажите категорию жалобы.",
    )


@router.callback_query(SupportRequestOpenCallback.filter())
async def support_request_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: SupportRequestOpenCallback,
) -> None:
    await start_support_request(
        callback=callback,
        bot=bot,
        state=state,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        order_id=callback_data.order_id,
    )


@router.callback_query(OrderDisputeOpenCallback.filter())
async def dispute_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: OrderDisputeOpenCallback,
) -> None:
    await state.set_state(SupportForm.dispute_text)
    await state.update_data(dispute_order_id=str(callback_data.order_id))
    await _prompt(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        text="<b>Спор по заказу</b>\n\nОпишите проблему одним сообщением.",
    )


@router.message(SupportForm.dispute_text)
async def dispute_text(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await _prompt(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_id=telegram_user_context.telegram_id,
            text="Опишите проблему текстом.",
        )
        return
    await state.update_data(dispute_text=message.text.strip(), dispute_file_ids=[])
    await state.set_state(SupportForm.dispute_attachment)
    await _prompt(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        text="Прикрепите фото или документ либо отправьте /skip.",
    )


@router.message(SupportForm.dispute_attachment, F.photo | F.document)
async def dispute_attachment(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    attachment = message.photo[-1] if message.photo else message.document
    if attachment is None:
        await message.answer("Прикрепите фото или документ либо отправьте /skip.")
        return
    content_type = (
        "image/jpeg"
        if message.photo
        else (message.document.mime_type or "application/octet-stream")
    )
    original_name = None if message.photo else message.document.file_name
    buffer = BytesIO()
    try:
        await bot.download(attachment.file_id, destination=buffer)
        file_id = await backend_client.upload_file(
            telegram_id=telegram_user_context.telegram_id,
            content=buffer.getvalue(),
            content_type=content_type,
            original_name=original_name,
        )
    except BackendClientError:
        await message.answer(
            "Не удалось загрузить вложение. Попробуйте ещё раз или /skip."
        )
        return
    data = await state.get_data()
    file_ids = [str(item) for item in data.get("dispute_file_ids", [])]
    file_ids.append(str(file_id))
    await state.update_data(dispute_file_ids=file_ids)
    await _submit_dispute(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
    )


@router.message(SupportForm.dispute_attachment, F.text == "/skip")
async def skip_dispute_attachment(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await _submit_dispute(
        message=message,
        bot=bot,
        state=state,
        backend_client=backend_client,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
    )


async def _submit_dispute(
    *,
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    try:
        record = await backend_client.create_dispute(
            telegram_id=telegram_user_context.telegram_id,
            order_id=UUID(str(data["dispute_order_id"])),
            text=str(data["dispute_text"]),
            file_ids=tuple(
                UUID(str(item)) for item in data.get("dispute_file_ids", [])
            ),
        )
    except BackendClientError:
        await state.clear()
        screen = RetryLaterScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.clear()
    await _show_submitted(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        kind="Спор",
        status=record.status,
    )


@router.message(SupportForm.request_type)
async def support_type(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await _prompt(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_id=telegram_user_context.telegram_id,
            text="Введите тип обращения текстом.",
        )
        return
    await state.update_data(support_type=message.text.strip())
    await state.set_state(SupportForm.request_text)
    await _prompt(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        text="Опишите вопрос одним сообщением.",
    )


@router.message(SupportForm.request_text)
async def support_text(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await _prompt(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_id=telegram_user_context.telegram_id,
            text="Опишите вопрос текстом.",
        )
        return
    data = await state.get_data()
    try:
        record = await backend_client.create_support_request(
            telegram_id=telegram_user_context.telegram_id,
            order_id=_uuid_or_none(data.get("support_order_id")),
            request_type=str(data["support_type"]),
            text=message.text.strip(),
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to create support request",
            extra={"exception_type": type(exc).__name__},
        )
        await state.clear()
        screen = RetryLaterScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.clear()
    await _show_submitted(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        kind="Обращение",
        status=record.status,
    )


@router.message(SupportForm.complaint_category)
async def complaint_category(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await _prompt(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_id=telegram_user_context.telegram_id,
            text="Введите категорию жалобы текстом.",
        )
        return
    await state.update_data(complaint_category=message.text.strip())
    await state.set_state(SupportForm.complaint_text)
    await _prompt(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        text="Опишите жалобу одним сообщением.",
    )


@router.message(SupportForm.complaint_text)
async def complaint_text(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await _prompt(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_id=telegram_user_context.telegram_id,
            text="Опишите жалобу текстом.",
        )
        return
    data = await state.get_data()
    try:
        record = await backend_client.create_complaint(
            telegram_id=telegram_user_context.telegram_id,
            order_id=_uuid_or_none(data.get("complaint_order_id")),
            category=str(data["complaint_category"]),
            text=message.text.strip(),
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to create complaint", extra={"exception_type": type(exc).__name__}
        )
        await state.clear()
        screen = RetryLaterScreen().build()
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=screen.text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.clear()
    await _show_submitted(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_id=telegram_user_context.telegram_id,
        kind="Жалоба",
        status=record.status,
    )


async def _show_submitted(
    *,
    bot: Bot,
    event: Message,
    telegram_responder: TelegramResponder,
    telegram_id: int,
    kind: str,
    status: str,
) -> None:
    await _prompt(
        bot=bot,
        event=event,
        telegram_responder=telegram_responder,
        telegram_id=telegram_id,
        text=f"<b>{kind} отправлена</b>\n\nСтатус: {status}.",
    )


def _uuid_or_none(value: object) -> UUID | None:
    if value is None:
        return None
    return UUID(str(value))


__all__ = ["router", "start_complaint", "start_support_request"]
