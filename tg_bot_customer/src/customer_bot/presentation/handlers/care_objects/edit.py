import logging
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    CareObjectDeleteCallback,
    CareObjectDeleteConfirmCallback,
    CareObjectEditCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.care_objects.state import (
    CareObjectManagement,
)
from customer_bot.presentation.handlers.care_objects.state import (
    care_object_by_index as _care_object_by_index,
)
from customer_bot.presentation.handlers.care_objects.state import (
    optional_bool as _optional_bool,
)
from customer_bot.presentation.handlers.care_objects.state import (
    optional_str as _optional_str,
)
from customer_bot.presentation.handlers.care_objects.state import (
    state_item as _state_item,
)
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    care_object_created_text,
    care_object_delete_confirm_keyboard,
    care_object_delete_confirm_text,
    care_object_deleted_text,
    delete_blocked_text,
    retry_later_text,
    use_buttons_text,
)

router = Router(name="care_objects_edit")
logger = logging.getLogger(__name__)


@router.callback_query(CareObjectEditCallback.filter())
async def edit_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectEditCallback,
) -> None:
    item = await _care_object_by_index(state, callback_data.index)
    if item is None:
        logger.warning(
            "Stale care object edit callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    await state.update_data(edit_item=item)
    await state.set_state(CareObjectManagement.edit_name)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text="Введите новое имя карточки.",
    )


@router.message(CareObjectManagement.edit_name)
async def enter_edit_name(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text="Введите имя текстом.",
        )
        return
    data = await state.get_data()
    item = _state_item(data["edit_item"])
    try:
        await backend_client.update_care_object(
            telegram_id=telegram_user_context.telegram_id,
            care_object_id=UUID(str(item["id"])),
            display_name=message.text.strip(),
            age_group=str(item["age_group"]),
            species=_optional_str(item.get("species")),
            breed=_optional_str(item.get("breed")),
            pet_size=_optional_str(item.get("pet_size")),
            mobility_assistance_required=_optional_bool(
                item.get("mobility_assistance_required"),
            ),
            routine_notes=_optional_str(item.get("routine_notes")),
            behavior_notes=_optional_str(item.get("behavior_notes")),
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to update care object",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_id": str(item["id"]),
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=message,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    await state.clear()
    logger.info(
        "Care object updated",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "care_object_id": str(item["id"]),
        },
    )
    await send_step(
        bot=bot,
        event=message,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=care_object_created_text(),
    )


@router.callback_query(CareObjectDeleteCallback.filter())
async def delete_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectDeleteCallback,
) -> None:
    item = await _care_object_by_index(state, callback_data.index)
    if item is None:
        logger.warning(
            "Stale care object delete callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=care_object_delete_confirm_text(),
        reply_markup=care_object_delete_confirm_keyboard(callback_data.index),
    )


@router.callback_query(CareObjectDeleteConfirmCallback.filter())
async def confirm_delete_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectDeleteConfirmCallback,
) -> None:
    item = await _care_object_by_index(state, callback_data.index)
    if item is None:
        logger.warning(
            "Stale care object delete confirm callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    try:
        await backend_client.delete_care_object(
            telegram_id=telegram_user_context.telegram_id,
            care_object_id=UUID(str(item["id"])),
        )
    except BackendValidationError as exc:
        logger.warning(
            "Backend rejected care object delete",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_id": str(item["id"]),
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=delete_blocked_text(str(exc)),
        )
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to delete care object",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_id": str(item["id"]),
                "exception_type": type(exc).__name__,
            },
        )
        await send_step(
            bot=bot,
            event=callback,
            telegram_responder=telegram_responder,
            telegram_user_context=telegram_user_context,
            text=retry_later_text(),
        )
        return
    logger.info(
        "Care object deleted",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "care_object_id": str(item["id"]),
        },
    )
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=care_object_deleted_text(),
    )
