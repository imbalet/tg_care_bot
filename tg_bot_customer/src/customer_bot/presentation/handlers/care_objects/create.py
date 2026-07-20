import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.application.errors import BackendClientError, BackendValidationError
from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    CareObjectAddCallback,
    CareObjectAgeCallback,
    CareObjectMobilityCallback,
    CareObjectSizeCallback,
    CareObjectSkipCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.care_objects.state import (
    CareObjectDraftSnapshot,
    CareObjectManagement,
    care_object_draft,
)
from customer_bot.presentation.handlers.orders.state import OrderCreation
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import YesNoValue
from customer_bot.presentation.ui.screens import (
    CareObjectAgeStepScreen,
    CareObjectBreedStepScreen,
    CareObjectCreatedScreen,
    CareObjectMobilityStepScreen,
    CareObjectNameStepScreen,
    CareObjectNotesStepScreen,
    CareObjectSizeStepScreen,
    CareObjectSpeciesStepScreen,
    CareObjectUpdatedScreen,
    OrderObjectsStepScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.view_models import (
    ObjectNameView,
    ObjectsStepView,
    ObjectTypeView,
    SelectableObjectView,
)

CARE_OBJECT_TYPE_LABELS = {
    "child": "Ребенок",
    "ward": "Подопечный",
    "pet": "Питомец",
}

router = Router(name="care_objects_create")
logger = logging.getLogger(__name__)


@router.callback_query(CareObjectAddCallback.filter())
async def add_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectAddCallback,
) -> None:
    object_type = callback_data.object_type
    if object_type not in CARE_OBJECT_TYPE_LABELS:
        logger.warning(
            "Invalid care object type callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "object_type": object_type,
            },
        )
        await telegram_responder.acknowledge(callback)
        return
    await state.set_state(CareObjectManagement.name)
    await state.update_data(draft={"object_type": object_type})
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := CareObjectNameStepScreen(
                ObjectNameView(object_type_label=CARE_OBJECT_TYPE_LABELS[object_type])
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.message(CareObjectManagement.name)
async def enter_name(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(
                screen := CareObjectNameStepScreen(
                    ObjectNameView(
                        object_type_label=CARE_OBJECT_TYPE_LABELS.get(
                            str(
                                care_object_draft(await state.get_data()).get(
                                    "object_type"
                                )
                            ),
                            "Объект ухода",
                        )
                    )
                ).build()
            ).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    data = await state.get_data()
    draft = care_object_draft(data)
    draft["display_name"] = message.text.strip()
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.age)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := CareObjectAgeStepScreen(
                ObjectTypeView(object_type=str(draft["object_type"]))
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(
    CareObjectManagement.age,
    CareObjectAgeCallback.filter(),
)
async def enter_age(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectAgeCallback,
) -> None:
    age_group = callback_data.age_group
    data = await state.get_data()
    draft = care_object_draft(data)
    draft["age_group"] = age_group
    await state.update_data(draft=draft)
    object_type = str(draft["object_type"])
    if object_type == "pet":
        await state.set_state(CareObjectManagement.species)
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := CareObjectSpeciesStepScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    if object_type == "ward":
        await state.set_state(CareObjectManagement.mobility)
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := CareObjectMobilityStepScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    await state.set_state(CareObjectManagement.notes)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := CareObjectNotesStepScreen().build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.message(CareObjectManagement.species)
async def enter_species(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    if not message.text or not message.text.strip():
        await telegram_responder.update(
            bot=bot,
            event=message,
            telegram_id=telegram_user_context.telegram_id,
            text=(screen := CareObjectSpeciesStepScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )
        return
    data = await state.get_data()
    draft = care_object_draft(data)
    draft["species"] = message.text.strip()
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.breed)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := CareObjectBreedStepScreen().build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.message(CareObjectManagement.breed)
async def enter_breed(
    message: Message,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = care_object_draft(data)
    if message.text and message.text.strip():
        draft["breed"] = message.text.strip()
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.size)
    await telegram_responder.update(
        bot=bot,
        event=message,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := CareObjectSizeStepScreen().build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(CareObjectManagement.breed, CareObjectSkipCallback.filter())
async def skip_breed(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    await state.set_state(CareObjectManagement.size)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := CareObjectSizeStepScreen().build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(
    CareObjectManagement.size,
    CareObjectSizeCallback.filter(),
)
async def enter_size(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectSizeCallback,
) -> None:
    size = callback_data.size
    data = await state.get_data()
    draft = care_object_draft(data)
    draft["pet_size"] = size
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.notes)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := CareObjectNotesStepScreen().build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.callback_query(
    CareObjectManagement.mobility,
    CareObjectMobilityCallback.filter(),
)
async def enter_mobility(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectMobilityCallback,
) -> None:
    value = callback_data.value
    data = await state.get_data()
    draft = care_object_draft(data)
    draft["mobility_assistance_required"] = value == YesNoValue.YES
    await state.update_data(draft=draft)
    await state.set_state(CareObjectManagement.notes)
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(screen := CareObjectNotesStepScreen().build()).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )


@router.message(CareObjectManagement.notes)
async def enter_notes(
    message: Message,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    draft = care_object_draft(data)
    if message.text and message.text.strip():
        draft["routine_notes"] = message.text.strip()
    await _create_from_draft(
        message,
        bot,
        state,
        backend_client,
        telegram_responder,
        telegram_user_context,
        draft,
    )


@router.callback_query(CareObjectManagement.notes, CareObjectSkipCallback.filter())
async def skip_notes(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
) -> None:
    data = await state.get_data()
    await _create_from_draft(
        callback,
        bot,
        state,
        backend_client,
        telegram_responder,
        telegram_user_context,
        care_object_draft(data),
    )


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
