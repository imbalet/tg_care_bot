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
    care_object_by_id,
    care_object_state,
)
from customer_bot.presentation.navigation import (
    active_category,
    category_by_code,
    list_categories,
)
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui.screens import (
    CareObjectCardScreen,
    CareObjectListScreen,
    RetryLaterScreen,
)
from customer_bot.presentation.view_models import (
    CareObjectCardView,
    CareObjectListItemView,
    CareObjectListView,
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
            text=(screen := RetryLaterScreen().build()).text,
            reply_markup=screen.reply_markup,
            create_new=True,
        )

        return
    await state.update_data(care_objects=[care_object_state(item) for item in items])
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := CareObjectListScreen(
                CareObjectListView(
                    category=category.name if category is not None else "Объекты ухода",
                    object_type=object_type or "",
                    count=len(items),
                    items=tuple(
                        CareObjectListItemView(
                            id=item.id,
                            display_name=item.display_name,
                        )
                        for item in items
                    ),
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
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
    item = await care_object_by_id(state, callback_data.care_object_id)
    if item is None:
        logger.warning(
            "Stale care object select callback",
            extra={
                "telegram_id": telegram_user_context.telegram_id,
                "care_object_id": str(callback_data.care_object_id),
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
    await telegram_responder.update(
        bot=bot,
        event=callback,
        telegram_id=telegram_user_context.telegram_id,
        text=(
            screen := CareObjectCardScreen(
                CareObjectCardView(
                    id=str(item["id"]),
                    object_type=str(item["object_type"]),
                    display_name=str(item["display_name"]),
                    age_group=str(item["age_group"]),
                    species=str(item.get("species") or ""),
                    breed=str(item.get("breed") or ""),
                    pet_size=str(item.get("pet_size") or ""),
                    mobility_assistance_required=item.get(
                        "mobility_assistance_required"
                    )
                    is True,
                )
            ).build()
        ).text,
        reply_markup=screen.reply_markup,
        create_new=True,
    )
