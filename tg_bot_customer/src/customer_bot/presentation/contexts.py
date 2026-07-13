from dataclasses import dataclass

from customer_bot.application.ports import ActiveCategoryStore, BackendPort
from customer_bot.application.services import UsernameSyncService
from customer_bot.presentation.services import MenuManager


@dataclass(frozen=True)
class AppContext:
    backend_client: BackendPort
    menu_manager: MenuManager
    active_category_store: ActiveCategoryStore
    username_sync_service: UsernameSyncService


@dataclass(frozen=True)
class TelegramUserContext:
    telegram_id: int
    username: str | None
    chat_id: int | None
