from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import httpx

from customer_bot.application.dto import (
    AddressDTO,
    CancellationPreviewDTO,
    CareObjectDTO,
    CustomerProfileDTO,
    FullAddressSnapshotDTO,
    MatchActionDTO,
    MyOrderCardDTO,
    MyOrdersPageDTO,
    MyOrderSummaryDTO,
    OrderDTO,
    OrderLocationDTO,
    OrderMatchDTO,
    OrderReportDTO,
    OrderReportFileDTO,
    PaymentStatusDTO,
    PricePreviewDTO,
    ServiceCategoryDTO,
    ServiceDTO,
    ServiceOptionDTO,
    SuitablePerformerDTO,
    SupportContactDTO,
    SupportRecordDTO,
)


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return "Backend rejected data"
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str):
                return message
    return "Backend rejected data"


def _customer_from_json(data: dict[str, object]) -> CustomerProfileDTO:
    return CustomerProfileDTO(
        id=UUID(str(data["id"])),
        telegram_id=int(cast(str | int, data["telegram_id"])),
        full_name=str(data["full_name"]),
        phone=str(data["phone"]),
        telegram_username=data["telegram_username"]
        if isinstance(data["telegram_username"], str)
        else None,
        contact_method=str(data["contact_method"]),
        city_id=UUID(str(data["city_id"])),
        status=str(data["status"]),
    )


def _service_category_from_json(data: dict[str, object]) -> ServiceCategoryDTO:
    services = data["services"] if isinstance(data["services"], list) else []
    return ServiceCategoryDTO(
        id=UUID(str(data["id"])),
        code=str(data["code"]),
        name=str(data["name"]),
        care_object_type=str(data["care_object_type"]),
        max_objects_per_order=int(cast(str | int, data["max_objects_per_order"])),
        services=tuple(_service_from_json(item) for item in services),
    )


def _service_from_json(data: dict[str, object]) -> ServiceDTO:
    raw_options = data.get("options") if isinstance(data.get("options"), list) else []
    return ServiceDTO(
        id=UUID(str(data["id"])),
        code=str(data["code"]),
        name=str(data["name"]),
        description=str(data["description"]),
        price_type=str(data["price_type"]),
        base_price=Decimal(str(data["base_price"])),
        location_policy=str(data["location_policy"]),
        photo_policy=str(data["photo_policy"]),
        schedule_policy=str(data["schedule_policy"]),
        allows_multiday=bool(data["allows_multiday"]),
        min_duration_minutes=int(cast(str | int, data["min_duration_minutes"]))
        if data["min_duration_minutes"] is not None
        else None,
        max_duration_minutes=int(cast(str | int, data["max_duration_minutes"]))
        if data["max_duration_minutes"] is not None
        else None,
        duration_step_minutes=int(cast(str | int, data["duration_step_minutes"]))
        if data["duration_step_minutes"] is not None
        else None,
        options=tuple(_service_option_from_json(item) for item in raw_options),
    )


def _service_option_from_json(data: dict[str, object]) -> ServiceOptionDTO:
    return ServiceOptionDTO(
        id=UUID(str(data["id"])),
        code=str(data["code"]),
        name=str(data["name"]),
        value_type=str(data["value_type"]),
        is_required=bool(data["is_required"]),
    )


def _support_contact_from_json(data: dict[str, object]) -> SupportContactDTO:
    return SupportContactDTO(
        label=str(data["label"]),
        telegram_url=data["telegram_url"]
        if isinstance(data["telegram_url"], str)
        else None,
    )


def _care_object_from_json(data: dict[str, object]) -> CareObjectDTO:
    return CareObjectDTO(
        id=UUID(str(data["id"])),
        object_type=str(data["object_type"]),
        display_name=str(data["display_name"]),
        age_group=str(data["age_group"]),
        species=data["species"] if isinstance(data["species"], str) else None,
        breed=data["breed"] if isinstance(data["breed"], str) else None,
        pet_size=data["pet_size"] if isinstance(data["pet_size"], str) else None,
        mobility_assistance_required=data["mobility_assistance_required"]
        if isinstance(data["mobility_assistance_required"], bool)
        else None,
        routine_notes=data["routine_notes"]
        if isinstance(data["routine_notes"], str)
        else None,
        behavior_notes=data["behavior_notes"]
        if isinstance(data["behavior_notes"], str)
        else None,
    )


def _address_from_json(data: dict[str, object]) -> AddressDTO:
    return AddressDTO(
        id=UUID(str(data["id"])),
        city_id=UUID(str(data["city_id"])),
        address_text=str(data["address_text"]),
        entrance=data["entrance"] if isinstance(data["entrance"], str) else None,
        floor=data["floor"] if isinstance(data["floor"], str) else None,
        apartment=data["apartment"] if isinstance(data["apartment"], str) else None,
        comment=data["comment"] if isinstance(data["comment"], str) else None,
    )


def _price_preview_from_json(data: dict[str, object]) -> PricePreviewDTO:
    return PricePreviewDTO(
        service_id=UUID(str(data["service_id"])),
        service_code=str(data["service_code"]),
        service_name=str(data["service_name"]),
        duration_minutes=int(cast(str | int, data["duration_minutes"])),
        objects_count=int(cast(str | int, data["objects_count"])),
        service_amount=Decimal(str(data["service_amount"])),
        platform_fee_amount=Decimal(str(data["platform_fee_amount"])),
        total_amount=Decimal(str(data["total_amount"])),
    )


def _order_request_json(
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
) -> dict[str, object]:
    return {
        "customer_id": str(customer_id),
        "service_id": str(service_id),
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "care_object_ids": [str(item) for item in care_object_ids],
        "address_id": str(address_id) if address_id is not None else None,
        "customer_comment": customer_comment,
        "report_photo_consent": report_photo_consent,
        "option_values": {str(key): value for key, value in option_values.items()},
    }


def _order_from_json(data: dict[str, object]) -> OrderDTO:
    return OrderDTO(
        id=UUID(str(data["id"])),
        customer_id=UUID(str(data["customer_id"]))
        if data["customer_id"] is not None
        else None,
        service_id=UUID(str(data["service_id"])),
        service_name=str(data["service_name"]),
        matching_mode=data["matching_mode"]
        if isinstance(data["matching_mode"], str)
        else None,
        status=str(data["status"]),
        start_at=datetime.fromisoformat(str(data["start_at"])),
        end_at=datetime.fromisoformat(str(data["end_at"])),
        objects_count=int(cast(str | int, data["objects_count"])),
        total_amount=Decimal(str(data["total_amount"])),
    )


def _suitable_performer_from_json(data: dict[str, object]) -> SuitablePerformerDTO:
    return SuitablePerformerDTO(
        performer_id=UUID(str(data["performer_id"])),
        full_name=str(data["full_name"]),
        service_id=UUID(str(data["service_id"])),
        service_name=str(data["service_name"]),
        performer_max_objects=int(cast(str | int, data["performer_max_objects"])),
        distance_km=Decimal(str(data["distance_km"]))
        if data["distance_km"] is not None
        else None,
    )


def _order_match_from_json(data: dict[str, object]) -> OrderMatchDTO:
    return OrderMatchDTO(
        id=UUID(str(data["id"])),
        order_id=UUID(str(data["order_id"])),
        performer_id=UUID(str(data["performer_id"])),
        match_type=str(data.get("match_type", data["source"])),
        status=str(data["status"]),
    )


def _match_action_from_json(data: dict[str, object]) -> MatchActionDTO:
    payment = data["payment"] if isinstance(data["payment"], dict) else None
    confirmation_url = (
        str(payment["confirmation_url"])
        if payment is not None and payment["confirmation_url"] is not None
        else None
    )
    return MatchActionDTO(
        order_id=UUID(str(data["order_id"])),
        order_status=str(data["order_status"]),
        match_id=UUID(str(data["match_id"])),
        payment_confirmation_url=confirmation_url,
    )


def _cancellation_preview_from_json(
    data: dict[str, object],
) -> CancellationPreviewDTO:
    return CancellationPreviewDTO(
        order_id=UUID(str(data["order_id"])),
        order_status=str(data["order_status"]),
        can_cancel=bool(data["can_cancel"]),
        refund_outcome=str(data["refund_outcome"]),
        refund_amount=Decimal(str(data["refund_amount"])),
        policy_version=data["policy_version"]
        if isinstance(data["policy_version"], str)
        else None,
        partial_refund_percent=Decimal(str(data["partial_refund_percent"]))
        if data["partial_refund_percent"] is not None
        else None,
        remaining_minutes=int(cast(str | int, data["remaining_minutes"])),
    )


def _payment_status_from_json(data: dict[str, object]) -> PaymentStatusDTO:
    expires_at = data["expires_at"] if isinstance(data["expires_at"], str) else None
    return PaymentStatusDTO(
        order_id=UUID(str(data["order_id"])),
        order_status=str(data["order_status"]),
        payment_id=UUID(str(data["payment_id"]))
        if data["payment_id"] is not None
        else None,
        payment_status=data["payment_status"]
        if isinstance(data["payment_status"], str)
        else None,
        confirmation_url=data["confirmation_url"]
        if isinstance(data["confirmation_url"], str)
        else None,
        expires_at=datetime.fromisoformat(expires_at)
        if expires_at is not None
        else None,
    )


def _my_orders_page_from_json(data: dict[str, object]) -> MyOrdersPageDTO:
    raw_items = data["items"] if isinstance(data["items"], list) else []
    return MyOrdersPageDTO(
        items=tuple(_my_order_summary_from_json(item) for item in raw_items),
        page=int(cast(str | int, data["page"])),
        page_size=int(cast(str | int, data["page_size"])),
        total_items=int(cast(str | int, data["total_items"])),
        total_pages=int(cast(str | int, data["total_pages"])),
    )


def _my_order_summary_from_json(data: dict[str, object]) -> MyOrderSummaryDTO:
    payment_deadline_at = (
        datetime.fromisoformat(str(data["payment_deadline_at"]))
        if data["payment_deadline_at"] is not None
        else None
    )
    return MyOrderSummaryDTO(
        id=UUID(str(data["id"])),
        category_code=str(data["category_code"]),
        service_name=str(data["service_name"]),
        matching_mode=data["matching_mode"]
        if isinstance(data["matching_mode"], str)
        else None,
        status=str(data["status"]),
        start_at=datetime.fromisoformat(str(data["start_at"])),
        end_at=datetime.fromisoformat(str(data["end_at"])),
        objects_count=int(cast(str | int, data["objects_count"])),
        total_amount=Decimal(str(data["total_amount"])),
        payment_deadline_at=payment_deadline_at,
        matching_deadline_at=datetime.fromisoformat(str(data["matching_deadline_at"])),
        timezone=str(data["timezone"]),
    )


def _my_order_card_from_json(data: dict[str, object]) -> MyOrderCardDTO:
    summary = _my_order_summary_from_json(data)
    payment_expires_at = (
        datetime.fromisoformat(str(data["payment_expires_at"]))
        if data["payment_expires_at"] is not None
        else None
    )
    return MyOrderCardDTO(
        **summary.__dict__,
        payment_status=data["payment_status"]
        if isinstance(data["payment_status"], str)
        else None,
        payment_confirmation_url=data["payment_confirmation_url"]
        if isinstance(data["payment_confirmation_url"], str)
        else None,
        payment_expires_at=payment_expires_at,
    )


def _order_location_from_json(data: dict[str, object]) -> OrderLocationDTO:
    raw_address = data["address"] if isinstance(data["address"], dict) else None
    address = (
        FullAddressSnapshotDTO(
            city_name=str(raw_address["city_name"]),
            district_name=(
                str(raw_address["district_name"])
                if raw_address["district_name"] is not None
                else None
            ),
            address_text=str(raw_address["address_text"]),
            entrance=(
                str(raw_address["entrance"])
                if raw_address["entrance"] is not None
                else None
            ),
            floor=(
                str(raw_address["floor"]) if raw_address["floor"] is not None else None
            ),
            apartment=(
                str(raw_address["apartment"])
                if raw_address["apartment"] is not None
                else None
            ),
            comment=(
                str(raw_address["comment"])
                if raw_address["comment"] is not None
                else None
            ),
        )
        if raw_address is not None
        else None
    )
    return OrderLocationDTO(
        order_id=UUID(str(data["order_id"])),
        city_name=str(data["city_name"]),
        district_name=(
            str(data["district_name"]) if data["district_name"] is not None else None
        ),
        address=address,
    )


def _order_report_from_json(data: dict[str, object]) -> OrderReportDTO:
    raw_files = data["files"] if isinstance(data["files"], list) else []
    return OrderReportDTO(
        id=UUID(str(data["id"])),
        order_id=UUID(str(data["order_id"])),
        performer_id=UUID(str(data["performer_id"])),
        completed_work=str(data["completed_work"]),
        comment=str(data["comment"]) if data["comment"] is not None else None,
        problem_flag=bool(data["problem_flag"]),
        problem_description=(
            str(data["problem_description"])
            if data["problem_description"] is not None
            else None
        ),
        submitted_at=datetime.fromisoformat(str(data["submitted_at"])),
        files=tuple(
            OrderReportFileDTO(
                id=UUID(str(item["id"])),
                original_name=(
                    str(item["original_name"])
                    if item["original_name"] is not None
                    else None
                ),
                mime_type=str(item["mime_type"]),
                signed_url=str(item["signed_url"]),
            )
            for item in raw_files
        ),
    )


def _support_record_from_json(data: dict[str, object]) -> SupportRecordDTO:
    raw_blockers = data["blockers"] if isinstance(data["blockers"], list) else []
    return SupportRecordDTO(
        id=UUID(str(data["id"])),
        kind=str(data["kind"]),
        order_id=(
            UUID(str(data["order_id"])) if data["order_id"] is not None else None
        ),
        status=str(data["status"]),
        text=str(data["text"]) if data["text"] is not None else None,
        category=(str(data["category"]) if data["category"] is not None else None),
        blockers=tuple(item for item in raw_blockers if isinstance(item, dict)),
    )
