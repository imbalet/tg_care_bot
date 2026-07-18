from dataclasses import dataclass

from executor_bot.application.ports import (
    ActiveCategoryStore,
    BackendPort,
    ViewedAvailableOrdersStore,
)
from executor_bot.application.services import UsernameSyncService
from executor_bot.presentation.services import TelegramResponder


@dataclass(frozen=True)
class AppContext:
    backend_client: BackendPort
    telegram_responder: TelegramResponder
    active_category_store: ActiveCategoryStore
    viewed_available_orders_store: ViewedAvailableOrdersStore
    username_sync_service: UsernameSyncService


@dataclass(frozen=True)
class TelegramUserContext:
    telegram_id: int
    username: str | None
    chat_id: int | None
