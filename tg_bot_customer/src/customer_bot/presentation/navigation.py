from aiogram import Bot
from aiogram.types import CallbackQuery, Message

from customer_bot.application.dto import ServiceCategoryDTO
from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.presentation.contexts import TelegramUserContext
from customer_bot.presentation.services import TelegramResponder
from customer_bot.presentation.ui import (
    category_select_keyboard,
    category_select_text,
    customer_main_menu_text,
    main_menu_keyboard,
)

MAIN_MENU_KEY = "main"


async def list_categories(
    backend_client: BackendPort,
) -> tuple[ServiceCategoryDTO, ...]:
    return await backend_client.list_catalog_categories()


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
    categories = await list_categories(backend_client)
    code = await active_category_store.get(telegram_id)
    return category_by_code(categories, code)


async def show_category_select(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_user_context: TelegramUserContext,
    backend_client: BackendPort,
    telegram_responder: TelegramResponder,
) -> None:
    categories = await list_categories(backend_client)
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=MAIN_MENU_KEY,
        text=category_select_text(),
        reply_markup=category_select_keyboard(categories),
    )


async def show_category_menu(
    *,
    bot: Bot,
    event: Message | CallbackQuery,
    telegram_user_context: TelegramUserContext,
    telegram_responder: TelegramResponder,
    category: ServiceCategoryDTO,
) -> None:
    await telegram_responder.update(
        bot=bot,
        event=event,
        telegram_id=telegram_user_context.telegram_id,
        topic_key=MAIN_MENU_KEY,
        text=customer_main_menu_text(category),
        reply_markup=main_menu_keyboard(category),
    )
