import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.care_objects.state import (
    CareObjectDraftSnapshot,
)
from customer_bot.presentation.handlers.orders.state import OrderCreation
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    CareObjectCreatedScreen,
    CareObjectUpdatedScreen,
    OrderObjectsStepScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.view_models import (
    ObjectsStepView,
    ObjectTypeView,
    SelectableObjectView,
)

router = Router(name="care_objects_completion")
logger = logging.getLogger(__name__)


async def _create_from_draft(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    draft: dict[str, object],
) -> None:
    snapshot = CareObjectDraftSnapshot.from_data(draft)
    try:
        if snapshot.edit_id is None:
            await backend_client.create_care_object(
                telegram_id=telegram_user_context.telegram_id,
                object_type=snapshot.object_type,
                display_name=snapshot.display_name,
                age_group=snapshot.age_group,
                species=snapshot.species,
                breed=snapshot.breed,
                pet_size=snapshot.pet_size,
                mobility_assistance_required=snapshot.mobility_assistance_required,
                routine_notes=snapshot.routine_notes,
                behavior_notes=snapshot.behavior_notes,
            )
        else:
            await backend_client.update_care_object(
                telegram_id=telegram_user_context.telegram_id,
                care_object_id=snapshot.edit_id,
                display_name=snapshot.display_name,
                age_group=snapshot.age_group,
                species=snapshot.species,
                breed=snapshot.breed,
                pet_size=snapshot.pet_size,
                mobility_assistance_required=snapshot.mobility_assistance_required,
                routine_notes=snapshot.routine_notes,
                behavior_notes=snapshot.behavior_notes,
            )
    except BackendValidationError:
        logger.warning(
            "Backend rejected care object creation",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "object_type": snapshot.object_type,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        await state.clear()
        return
    except BackendClientError as exc:
        logger.warning(
            "Failed to create care object",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "object_type": snapshot.object_type,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    data = await state.get_data()
    if data.get("return_to_order_after_care_object") is True:
        await _return_to_order_objects(
            event,
            bot,
            state,
            backend_client,
            telegram_responder,
            telegram_user_context,
        )
        return
    await state.clear()
    logger.info(
        "Care object saved",
        extra={
            "telegram_id": telegram_user_context.telegram_id,
            "object_type": snapshot.object_type,
            "is_edit": snapshot.edit_id is not None,
        },
    )
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := (
                CareObjectUpdatedScreen(
                    ObjectTypeView(object_type=snapshot.object_type)
                )
                if snapshot.edit_id is not None
                else CareObjectCreatedScreen(
                    ObjectTypeView(object_type=snapshot.object_type)
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


async def _return_to_order_objects(
    event: Message | CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    order_draft = data.get("order_draft")
    if not isinstance(order_draft, dict):
        await state.clear()
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    try:
        objects = await backend_client.list_care_objects(
            telegram_id=telegram_user_context.telegram_id,
            object_type=str(order_draft["care_object_type"]),
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to reload care objects after order inline creation",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.set_state(OrderCreation.object)
    await state.update_data(
        draft={},
        return_to_order_after_care_object=False,
        order_draft=order_draft,
        order_objects=[
            {"id": str(item.id), "display_name": item.display_name} for item in objects
        ],
    )
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := OrderObjectsStepScreen(
                ObjectsStepView(
                    max_count=int(str(order_draft.get("max_objects_per_order", 1))),
                    selected_count=0,
                    selected_ids=(),
                    items=tuple(
                        SelectableObjectView(
                            id=str(item.id), display_name=item.display_name
                        )
                        for item in objects
                    ),
                    can_finish=False,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )
