import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from customer_bot.application.ports import BackendPort
from customer_bot.presentation.callbacks import (
    CareObjectAddCallback,
    CareObjectAgeCallback,
    CareObjectMobilityCallback,
    CareObjectSizeCallback,
    CareObjectSkipCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.care_objects.completion import (
    _create_from_draft,
)
from customer_bot.presentation.handlers.care_objects.state import (
    CareObjectManagement,
    care_object_draft,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.types import YesNoValue
from customer_bot.presentation.ui.screens import (
    CareObjectAgeStepScreen,
    CareObjectBreedStepScreen,
    CareObjectMobilityStepScreen,
    CareObjectNameStepScreen,
    CareObjectNotesStepScreen,
    CareObjectSizeStepScreen,
    CareObjectSpeciesStepScreen,
)
from customer_bot.presentation.view_models import (
    ObjectNameView,
    ObjectTypeView,
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
