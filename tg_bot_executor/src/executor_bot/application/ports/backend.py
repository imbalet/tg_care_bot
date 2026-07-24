from datetime import time
from typing import Protocol
from uuid import UUID

from executor_bot.application.dto import (
    AddressDTO,
    AddressSuggestionDTO,
    AvailableOrderDTO,
    CityDTO,
    ContactRequestDTO,
    DeletionPreflightDTO,
    FileDTO,
    LegalDocumentDTO,
    MatchActionDTO,
    MyOrderCardDTO,
    MyOrdersPageDTO,
    OrderLocationDTO,
    OrderMatchDTO,
    OrderReportDTO,
    PerformerProfileDTO,
    PerformerScheduleDTO,
    PerformerServiceDTO,
    RegistrationStateDTO,
    ServiceCategoryDTO,
    SupportContactDTO,
)


class BackendPort(Protocol):
    async def ping(self) -> None: ...

    async def get_registration_state(
        self, telegram_id: int
    ) -> RegistrationStateDTO: ...

    async def list_active_cities(self) -> tuple[CityDTO, ...]: ...

    async def list_active_legal_documents(self) -> tuple[LegalDocumentDTO, ...]: ...

    async def list_catalog_categories(self) -> tuple[ServiceCategoryDTO, ...]: ...

    async def get_support_contact(self) -> SupportContactDTO: ...

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

    async def upload_file(
        self,
        *,
        telegram_id: int,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> FileDTO: ...

    async def get_deletion_preflight(
        self, *, telegram_id: int
    ) -> DeletionPreflightDTO: ...

    async def create_deletion_request(self, *, telegram_id: int) -> None: ...

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

    async def list_available_orders(
        self,
        *,
        performer_id: UUID,
    ) -> tuple[AvailableOrderDTO, ...]: ...

    async def create_pool_response(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
    ) -> OrderMatchDTO: ...

    async def list_performer_responses(
        self, *, performer_id: UUID, group: str
    ) -> tuple[OrderMatchDTO, ...]: ...

    async def accept_direct_match(
        self,
        *,
        match_id: UUID,
        performer_id: UUID,
    ) -> MatchActionDTO: ...

    async def reject_direct_match(
        self,
        *,
        match_id: UUID,
        performer_id: UUID,
    ) -> OrderMatchDTO: ...

    async def list_performer_orders(
        self,
        *,
        performer_id: UUID,
        group: str,
        page: int,
        page_size: int = 5,
    ) -> MyOrdersPageDTO: ...

    async def get_performer_order_card(
        self,
        *,
        performer_id: UUID,
        order_id: UUID,
    ) -> MyOrderCardDTO: ...

    async def get_performer_order_location(
        self, *, performer_id: UUID, order_id: UUID
    ) -> OrderLocationDTO: ...

    async def start_order(
        self, *, performer_id: UUID, order_id: UUID
    ) -> MyOrderCardDTO: ...

    async def finish_order(
        self, *, performer_id: UUID, order_id: UUID
    ) -> MyOrderCardDTO: ...

    async def submit_order_report(
        self,
        *,
        performer_id: UUID,
        order_id: UUID,
        completed_work: str,
        comment: str | None,
        problem_flag: bool,
        problem_description: str | None,
        file_ids: tuple[UUID, ...],
    ) -> OrderReportDTO: ...

    async def get_performer_order_report(
        self, *, performer_id: UUID, order_id: UUID
    ) -> OrderReportDTO: ...

    async def cancel_order(
        self, *, performer_id: UUID, order_id: UUID
    ) -> MyOrderCardDTO: ...

    async def create_contact_request(
        self, *, telegram_id: int, order_id: UUID
    ) -> ContactRequestDTO: ...

    async def create_support_request(
        self, *, telegram_id: int, order_id: UUID | None, request_type: str, text: str
    ) -> object: ...

    async def create_complaint(
        self,
        *,
        telegram_id: int,
        order_id: UUID | None,
        category: str,
        text: str,
        file_ids: tuple[UUID, ...] = (),
    ) -> object: ...
