import logging

from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from customer_bot.application.errors import BackendClientError
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.callbacks import (
    CareObjectSelectCallback,
    CareObjectsOpenCallback,
)
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.handlers.care_objects.state import (
    care_object_by_index,
    care_object_state,
)
from customer_bot.presentation.navigation import (
    active_category,
    category_by_code,
    list_categories,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    care_object_card_keyboard,
    care_object_card_text,
    care_objects_keyboard,
    care_objects_list_text,
    retry_later_text,
    use_buttons_text,
)

router = Router(name="care_objects_list")
logger = logging.getLogger(__name__)


@router.callback_query(CareObjectsOpenCallback.filter())
async def open_care_objects(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectsOpenCallback,
) -> None:
    try:
        if callback_data.category_code is not None:
            categories = await list_categories(backend_client)
            category = category_by_code(categories, callback_data.category_code)
        else:
            category = await active_category(
                backend_client=backend_client,
                active_category_store=active_category_store,
                telegram_id=telegram_user_context.telegram_id,
            )
        object_type = category.care_object_type if category is not None else None
        items = await backend_client.list_care_objects(
            telegram_id=telegram_user_context.telegram_id,
            object_type=object_type,
        )
    except BackendClientError as exc:
        logger.warning(
            "Failed to load care objects",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "category_code": callback_data.category_code,
                "exception_type": type(exc).__name__,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=retry_later_text(),
            create_new=True,
        )

        return
    await state.update_data(care_objects=[care_object_state(item) for item in items])
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=care_objects_list_text(len(items), category),
        reply_markup=care_objects_keyboard(items, object_type=object_type),
        create_new=True,
    )


@router.callback_query(CareObjectSelectCallback.filter())
async def select_care_object(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    telegram_responder: TelegramResponder,
    telegram_user_context: TelegramUserContext,
    callback_data: CareObjectSelectCallback,
) -> None:
    item = await care_object_by_index(state, callback_data.index)
    if item is None:
        logger.warning(
            "Stale care object select callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "index": callback_data.index,
            },
        )
        await telegram_responder.update(
            bot=bot,
            event=callback,
            telegram_id=telegram_user_context.telegram_id,
            text=use_buttons_text(),
            create_new=True,
        )
        return
    index = item["index"]
    if not isinstance(index, int):
        logger.warning(
            "Invalid care object index in state",
            extra={"telegram_id": telegram_user_context.telegram_id},
        )
        await telegram_responder.acknowledge(callback, use_buttons_text())
        return
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=care_object_card_text(item),
        reply_markup=care_object_card_keyboard(index),
        create_new=True,
    )
