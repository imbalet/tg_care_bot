import logging
from types import SimpleNamespace
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
    care_object_by_id,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    CareObjectDeleteBlockedScreen,
    CareObjectDeleteConfirmScreen,
    CareObjectDeletedScreen,
    CareObjectNameStepScreen,
    RetryLaterScreen,
)

router = Router(name="care_objects_edit")
logger = logging.getLogger(__name__)

CARE_OBJECT_TYPE_LABELS = {
    "child": "Ребенок",
    "ward": "Подопечный",
    "pet": "Питомец",
}


@router.callback_query(CareObjectEditCallback.filter())
async def edit_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectEditCallback,
) -> None:
    item = await care_object_by_id(state, callback_data.care_object_id)
    if item is None:
        logger.warning(
            "Stale care object edit callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_id": str(callback_data.care_object_id),
            },
        )
        await telegram_responder.acknowledge(callback)
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
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := CareObjectNameStepScreen(
                SimpleNamespace(
                    object_type_label=CARE_OBJECT_TYPE_LABELS.get(
                        object_type, object_type
                    )
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
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
    item = await care_object_by_id(state, callback_data.care_object_id)
    if item is None:
        logger.warning(
            "Stale care object delete callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_id": str(callback_data.care_object_id),
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := CareObjectDeleteConfirmScreen(
                SimpleNamespace(id=str(callback_data.care_object_id))
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
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
    item = await care_object_by_id(state, callback_data.care_object_id)
    if item is None:
        logger.warning(
            "Stale care object delete confirm callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_id": str(callback_data.care_object_id),
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    try:
        await backend_client.delete_care_object(
            telegram_id=telegram_user_context.telegram_id,
            care_object_id=UUID(str(item["id"])),
        )
    except BackendValidationError:
        logger.warning(
            "Backend rejected care object delete",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_id": str(item["id"]),
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                screen := CareObjectDeleteBlockedScreen(
                    SimpleNamespace(id=str(callback_data.care_object_id))
                ).build()
            ).text,
            reply_markup=screen.reply_markup,
            create_new=True,
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
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    logger.info(
        "Care object deleted",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "care_object_id": str(item["id"]),
        },
    )
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := CareObjectDeletedScreen().build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )
