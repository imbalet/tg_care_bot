from aiogram import Bot
from aiogram.types import CallbackQuery, Message

from executor_bot.application.dto import ServiceCategoryDTO
from executor_bot.application.ports import ActiveCategoryStore, BackendPort
from executor_bot.presentation.contexts import TelegramUserContext
from executor_bot.presentation.services import TelegramResponder
from executor_bot.presentation.ui import (
    category_select_keyboard,
    category_select_text,
    executor_main_menu_text,
    main_menu_keyboard,
    no_available_categories_text,
)


async def list_categories(
    backend_client: BackendPort,
    *,
    telegram_id: int | None = None,
) -> tuple[ServiceCategoryDTO, ...]:
    categories = await backend_client.list_catalog_categories()
    if telegram_id is None:
        return categories
    services = await backend_client.list_performer_services(telegram_id=telegram_id)
    approved_service_codes = {
        service.service_code for service in services if service.is_approved
    }
    return tuple(
        category
        for category in categories
        if any(service.code in approved_service_codes for service in category.services)
    )


def category_by_code(
    categories: tuple[ServiceCategoryDTO, ...],
    code: str | None,
) -> ServiceCategoryDTO | None:
    if code is None:
        return None
    for category in categories:
        if category.code == code:
            return category
    return None


async def active_category(
    *,
    backend_client: BackendPort,
    active_category_store: ActiveCategoryStore,
    telegram_id: int,
) -> ServiceCategoryDTO | None:
    categories = await list_categories(backend_client, telegram_id=telegram_id)
    code = await active_category_store.get(telegram_id)
    return category_by_code(categories, code)


async def show_category_select(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_user_context: TelegramUserContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
    force_create_new: bool = False,
) -> None:
    categories = await list_categories(
        backend_client,
        telegram_id=telegram_user_context.telegram_id,
    )
    if not categories:
        await telegram_responder.update(
            bot=bot,
            event=event,
            telegram_id=telegram_user_context.telegram_id,
            text=no_available_categories_text(),
            reply_markup=None,
            create_new=force_create_new,
        )
        return
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=category_select_text(),
        reply_markup=category_select_keyboard(categories),
        create_new=force_create_new,
    )


async def show_category_menu(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_user_context: TelegramUserContext,
    telegram_responder: TelegramResponder,
    category: ServiceCategoryDTO,
    force_create_new: bool = False,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        text=executor_main_menu_text(category),
        reply_markup=main_menu_keyboard(category),
        create_new=force_create_new,
    )
