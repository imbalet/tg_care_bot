from datetime import datetime
from typing import Protocol
from uuid import UUID

from customer_bot.application.dto import (
    AddressDTO,
    AddressSuggestionDTO,
    CancellationPreviewDTO,
    CareObjectDTO,
    CityDTO,
    ContactRequestDTO,
    CustomerProfileDTO,
    DeletionPreflightDTO,
    LegalDocumentDTO,
    MatchActionDTO,
    MyOrderCardDTO,
    MyOrdersPageDTO,
    OrderDTO,
    OrderLocationDTO,
    OrderMatchDTO,
    OrderReportDTO,
    PaymentStatusDTO,
    PerformerProfileDTO,
    PricePreviewDTO,
    ServiceCategoryDTO,
    SuitablePerformerDTO,
    SupportContactDTO,
    SupportRecordDTO,
)


class BackendPort(Protocol):
    async def ping(self) -> None: ...

    async def get_customer_profile(
        self,
        telegram_id: int,
    ) -> CustomerProfileDTO | None: ...

    async def update_customer_profile(
        self,
        *,
        telegram_id: int,
        phone: str,
        contact_method: str,
    ) -> CustomerProfileDTO: ...

    async def list_active_cities(self) -> tuple[CityDTO, ...]: ...

    async def list_active_legal_documents(self) -> tuple[LegalDocumentDTO, ...]: ...

    async def list_catalog_categories(self) -> tuple[ServiceCategoryDTO, ...]: ...

    async def get_support_contact(self) -> SupportContactDTO: ...

    async def register_customer(
        self,
        *,
        telegram_id: int,
        full_name: str,
        phone: str,
        city_id: UUID,
        contact_method: str,
        telegram_username: str | None,
        accepted_legal_document_ids: tuple[UUID, ...],
    ) -> CustomerProfileDTO: ...

    async def update_customer_username(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
    ) -> CustomerProfileDTO: ...

    async def list_care_objects(
        self,
        *,
        telegram_id: int,
        object_type: str | None = None,
    ) -> tuple[CareObjectDTO, ...]: ...

    async def create_care_object(
        self,
        *,
        telegram_id: int,
        object_type: str,
        display_name: str,
        age_group: str,
        species: str | None = None,
        breed: str | None = None,
        pet_size: str | None = None,
        mobility_assistance_required: bool | None = None,
        routine_notes: str | None = None,
        behavior_notes: str | None = None,
    ) -> CareObjectDTO: ...

    async def update_care_object(
        self,
        *,
        telegram_id: int,
        care_object_id: UUID,
        display_name: str,
        age_group: str,
        species: str | None = None,
        breed: str | None = None,
        pet_size: str | None = None,
        mobility_assistance_required: bool | None = None,
        routine_notes: str | None = None,
        behavior_notes: str | None = None,
    ) -> CareObjectDTO: ...

    async def delete_care_object(
        self,
        *,
        telegram_id: int,
        care_object_id: UUID,
    ) -> None: ...

    async def suggest_addresses(
        self,
        *,
        city_id: UUID,
        query: str,
    ) -> tuple[AddressSuggestionDTO, ...]: ...

    async def list_addresses(self, *, telegram_id: int) -> tuple[AddressDTO, ...]: ...

    async def create_address(
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

    async def delete_address(self, *, telegram_id: int, address_id: UUID) -> None: ...

    async def get_deletion_preflight(
        self, *, telegram_id: int
    ) -> DeletionPreflightDTO: ...

    async def create_deletion_request(
        self, *, telegram_id: int
    ) -> SupportRecordDTO: ...

    async def create_dispute(
        self,
        *,
        telegram_id: int,
        order_id: UUID,
        text: str,
        file_ids: tuple[UUID, ...] = (),
    ) -> SupportRecordDTO: ...

    async def create_contact_request(
        self, *, telegram_id: int, order_id: UUID
    ) -> ContactRequestDTO: ...

    async def get_performer_profile(
        self, *, telegram_id: int, order_id: UUID
    ) -> PerformerProfileDTO: ...

    async def upload_file(
        self,
        *,
        telegram_id: int,
        content: bytes,
        content_type: str,
        original_name: str | None,
    ) -> UUID: ...

    async def preview_order_price(
        self,
        *,
        customer_id: UUID,
        service_id: UUID,
        start_at: datetime,
        end_at: datetime,
        objects_count: int,
    ) -> PricePreviewDTO: ...

    async def create_order_pool(
        self,
        *,
        customer_id: UUID,
        service_id: UUID,
        start_at: datetime,
        end_at: datetime,
        care_object_ids: tuple[UUID, ...],
        address_id: UUID | None,
        customer_comment: str | None,
        report_photo_consent: bool | None,
        option_values: dict[UUID, object],
    ) -> OrderDTO: ...

    async def create_order_direct(
        self,
        *,
        customer_id: UUID,
        service_id: UUID,
        start_at: datetime,
        end_at: datetime,
        care_object_ids: tuple[UUID, ...],
        address_id: UUID | None,
        customer_comment: str | None,
        report_photo_consent: bool | None,
        option_values: dict[UUID, object],
        performer_id: UUID,
    ) -> OrderDTO: ...

    async def find_suitable_performers(
        self,
        *,
        city_id: UUID,
        service_id: UUID,
        start_at: datetime,
        end_at: datetime,
        objects_count: int,
        care_object_ids: tuple[UUID, ...],
        address_id: UUID | None,
    ) -> tuple[SuitablePerformerDTO, ...]: ...

    async def list_order_matches(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> tuple[OrderMatchDTO, ...]: ...

    async def select_pool_response(
        self,
        *,
        match_id: UUID,
        customer_id: UUID,
    ) -> MatchActionDTO: ...

    async def reject_pool_response(
        self,
        *,
        match_id: UUID,
        customer_id: UUID,
    ) -> OrderMatchDTO: ...

    async def get_payment_status(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> PaymentStatusDTO: ...

    async def cancel_customer_order(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> OrderDTO: ...

    async def get_customer_cancellation_preview(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> CancellationPreviewDTO: ...

    async def list_customer_orders(
        self,
        *,
        customer_id: UUID,
        group: str,
        page: int,
        page_size: int = 5,
        category_code: str | None = None,
    ) -> MyOrdersPageDTO: ...

    async def get_customer_order_card(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> MyOrderCardDTO: ...

    async def get_customer_order_location(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> OrderLocationDTO: ...

    async def get_customer_order_report(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> OrderReportDTO: ...

    async def confirm_customer_order_report(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> OrderDTO: ...

    async def start_customer_order(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> OrderDTO: ...

    async def create_support_request(
        self,
        *,
        telegram_id: int,
        order_id: UUID | None,
        request_type: str,
        text: str,
    ) -> SupportRecordDTO: ...

    async def create_complaint(
        self,
        *,
        telegram_id: int,
        order_id: UUID | None,
        category: str,
        text: str,
    ) -> SupportRecordDTO: ...
