import logging
from uuid import UUID

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

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
from customer_bot.presentation.handlers.responses import send_step
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    care_object_delete_confirm_keyboard,
    care_object_delete_confirm_text,
    care_object_deleted_text,
    care_object_name_step_text,
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
    object_type = str(item["object_type"])
    await state.update_data(
        draft={
            "edit_id": str(item["id"]),
            "object_type": object_type,
            "display_name": str(item["display_name"]),
            "age_group": str(item["age_group"]),
            "species": item.get("species"),
            "breed": item.get("breed"),
            "pet_size": item.get("pet_size"),
            "mobility_assistance_required": item.get("mobility_assistance_required"),
            "routine_notes": item.get("routine_notes"),
            "behavior_notes": item.get("behavior_notes"),
        }
    )
    await state.set_state(CareObjectManagement.name)
    await send_step(
        bot=bot,
        event=callback,
        telegram_responder=telegram_responder,
        telegram_user_context=telegram_user_context,
        text=care_object_name_step_text(object_type),
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
