from dataclasses import dataclass

from customer_bot.application.services import UsernameSyncService
from customer_bot.infrastructure.http import BackendClient
from customer_bot.presentation.services import MenuManager, TelegramTopicSetupService


@dataclass(frozen=True)
class AppContext:
    backend_client: BackendClient
    menu_manager: MenuManager
    topic_setup_service: TelegramTopicSetupService
    username_sync_service: UsernameSyncService


@dataclass(frozen=True)
class TelegramUserContext:
    telegram_id: int
    username: str | None
    chat_id: int | None
    message_thread_id: int | None
