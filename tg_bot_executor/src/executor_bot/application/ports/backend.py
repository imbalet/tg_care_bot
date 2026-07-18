from datetime import time
from typing import Protocol
from uuid import UUID

from executor_bot.application.dto import (
    AddressDTO,
    AddressSuggestionDTO,
    CityDTO,
    FileDTO,
    LegalDocumentDTO,
    PerformerProfileDTO,
    PerformerScheduleDTO,
    PerformerServiceDTO,
    RegistrationStateDTO,
    ServiceCategoryDTO,
    TelegramTopicDTO,
)


class BackendPort(Protocol):
    async def ping(self) -> None: ...

    async def get_registration_state(
        self, telegram_id: int
    ) -> RegistrationStateDTO: ...

    async def list_active_cities(self) -> tuple[CityDTO, ...]: ...

    async def list_active_legal_documents(self) -> tuple[LegalDocumentDTO, ...]: ...

    async def list_catalog_categories(self) -> tuple[ServiceCategoryDTO, ...]: ...

    async def register_performer(
        self,
        *,
        telegram_id: int,
        full_name: str,
        phone: str,
        city_id: UUID,
        contact_method: str,
        about_text: str,
        telegram_username: str | None,
        accepted_legal_document_ids: tuple[UUID, ...],
    ) -> PerformerProfileDTO: ...

    async def update_performer_username(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
    ) -> PerformerProfileDTO: ...

    async def ensure_telegram_topics(
        self,
        *,
        telegram_id: int,
        chat_id: int,
    ) -> tuple[TelegramTopicDTO, ...]: ...

    async def update_telegram_topic_mapping(
        self,
        *,
        topic_id: UUID,
        chat_id: int,
        message_thread_id: int | None,
        status: str,
    ) -> TelegramTopicDTO: ...

    async def suggest_addresses(
        self,
        *,
        city_id: UUID,
        query: str,
    ) -> tuple[AddressSuggestionDTO, ...]: ...

    async def list_work_addresses(
        self, *, telegram_id: int
    ) -> tuple[AddressDTO, ...]: ...

    async def create_work_address(
        self,
        *,
        telegram_id: int,
        city_id: UUID,
        unrestricted_value: str,
        entrance: str | None,
        floor: str | None,
        apartment: str | None,
        comment: str | None,
    ) -> AddressDTO: ...

    async def set_current_work_address(
        self,
        *,
        telegram_id: int,
        address_id: UUID,
    ) -> AddressDTO: ...

    async def delete_work_address(
        self,
        *,
        telegram_id: int,
        address_id: UUID,
    ) -> None: ...

    async def upload_avatar(
        self,
        *,
        telegram_id: int,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> FileDTO: ...

    async def delete_avatar(self, *, telegram_id: int) -> None: ...

    async def list_performer_services(
        self,
        *,
        telegram_id: int,
    ) -> tuple[PerformerServiceDTO, ...]: ...

    async def set_service_enabled(
        self,
        *,
        telegram_id: int,
        service_id: UUID,
        is_enabled: bool,
    ) -> PerformerServiceDTO: ...

    async def set_service_max_objects(
        self,
        *,
        telegram_id: int,
        service_id: UUID,
        performer_max_objects: int,
    ) -> PerformerServiceDTO: ...

    async def set_accepting_orders(
        self,
        *,
        telegram_id: int,
        is_accepting_orders: bool,
    ) -> PerformerProfileDTO: ...

    async def set_schedule(
        self,
        *,
        telegram_id: int,
        schedule_type: str,
        work_days: tuple[int, ...] | None,
        work_start_time: time,
        work_end_time: time,
    ) -> PerformerScheduleDTO: ...

    async def add_tomorrow_unavailable(self, *, telegram_id: int) -> None: ...
