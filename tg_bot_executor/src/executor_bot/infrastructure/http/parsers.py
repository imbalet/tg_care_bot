from datetime import datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from executor_bot.application.dto import (
    AddressDTO,
    AddressSuggestionDTO,
    AvailableOrderDTO,
    BusyIntervalDTO,
    CalendarDTO,
    CalendarOverrideDTO,
    ContactRequestDTO,
    FileDTO,
    MatchActionDTO,
    MyOrderCardDTO,
    MyOrdersPageDTO,
    MyOrderSummaryDTO,
    OrderLocationDTO,
    OrderMatchDTO,
    OrderReportDTO,
    OrderReportFileDTO,
    PerformerProfileDTO,
    PerformerScheduleDTO,
    PerformerServiceDTO,
    ServiceCategoryDTO,
    ServiceDTO,
    SupportContactDTO,
)
from executor_bot.application.errors import BackendUnavailableError


def error_message(data: object) -> str:
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return str(error["message"])
    return "Backend rejected data"


def performer_from_json(data: dict[str, object]) -> PerformerProfileDTO:
    return PerformerProfileDTO(
        id=UUID(str(data["id"])),
        telegram_id=int(cast(str | int, data["telegram_id"])),
        full_name=str(data["full_name"]),
        phone=str(data["phone"]),
        telegram_username=data["telegram_username"]
        if isinstance(data["telegram_username"], str)
        else None,
        contact_method=str(data["contact_method"]),
        city_id=UUID(str(data["city_id"])),
        about_text=data["about_text"] if isinstance(data["about_text"], str) else None,
        status=str(data["status"]),
        is_accepting_orders=bool(data["is_accepting_orders"]),
        current_address_id=UUID(str(data["current_address_id"]))
        if data.get("current_address_id") is not None
        else None,
        avatar_url=str(data["avatar_url"])
        if isinstance(data.get("avatar_url"), str)
        else None,
    )


def service_category_from_json(data: dict[str, object]) -> ServiceCategoryDTO:
    services = data.get("services")
    return ServiceCategoryDTO(
        id=UUID(str(data["id"])),
        code=str(data["code"]),
        name=str(data["name"]),
        sort_order=int(cast(str | int, data["sort_order"])),
        care_object_type=str(data["care_object_type"]),
        services=tuple(
            service_from_json(item) for item in services if isinstance(item, dict)
        )
        if isinstance(services, list)
        else (),
    )


def service_from_json(data: dict[str, object]) -> ServiceDTO:
    return ServiceDTO(
        id=UUID(str(data["id"])),
        code=str(data["code"]),
        name=str(data["name"]),
        description=str(data["description"]),
        price_type=str(data["price_type"]),
        base_price=str(data["base_price"]),
        location_policy=str(data["location_policy"]),
        photo_policy=str(data["photo_policy"]),
        schedule_policy=str(data["schedule_policy"]),
        allows_multiday=bool(data["allows_multiday"]),
        min_duration_minutes=int(cast(str | int, data["min_duration_minutes"]))
        if data.get("min_duration_minutes") is not None
        else None,
        max_duration_minutes=int(cast(str | int, data["max_duration_minutes"]))
        if data.get("max_duration_minutes") is not None
        else None,
    )


def address_from_json(data: dict[str, object]) -> AddressDTO:
    return AddressDTO(
        id=UUID(str(data["id"])),
        city_id=UUID(str(data["city_id"])),
        address_text=str(data["address_text"]),
        entrance=data["entrance"] if isinstance(data["entrance"], str) else None,
        floor=data["floor"] if isinstance(data["floor"], str) else None,
        apartment=data["apartment"] if isinstance(data["apartment"], str) else None,
        comment=data["comment"] if isinstance(data["comment"], str) else None,
    )


def address_suggestion_from_json(data: dict[str, object]) -> AddressSuggestionDTO:
    return AddressSuggestionDTO(
        value=str(data["value"]),
        unrestricted_value=str(data["unrestricted_value"]),
    )


def support_contact_from_json(data: dict[str, object]) -> SupportContactDTO:
    return SupportContactDTO(
        label=str(data["label"]),
        telegram_url=data["telegram_url"]
        if isinstance(data["telegram_url"], str)
        else None,
    )


def file_from_json(data: dict[str, object]) -> FileDTO:
    return FileDTO(
        id=UUID(str(data["id"])),
        mime_type=str(data["mime_type"]),
        size_bytes=int(cast(str | int, data["size_bytes"]))
        if data.get("size_bytes") is not None
        else None,
        status=str(data["status"]),
    )


def performer_service_from_json(data: dict[str, object]) -> PerformerServiceDTO:
    constraints = data.get("constraints")
    return PerformerServiceDTO(
        service_id=UUID(str(data["service_id"])),
        service_code=str(data["service_code"]),
        service_name=str(data["service_name"]),
        service_location_policy=str(data["service_location_policy"]),
        is_approved=bool(data["is_approved"]),
        is_enabled=bool(data["is_enabled"]),
        admin_max_objects=int(cast(str | int, data["admin_max_objects"])),
        performer_max_objects=int(cast(str | int, data["performer_max_objects"])),
        constraints=constraints if isinstance(constraints, dict) else {},
    )


def schedule_from_json(data: dict[str, object]) -> PerformerScheduleDTO:
    work_days = data.get("work_days")
    return PerformerScheduleDTO(
        schedule_type=str(data["schedule_type"]),
        work_days=tuple(int(item) for item in work_days)
        if isinstance(work_days, list)
        else None,
        work_start_time=str(data["work_start_time"]),
        work_end_time=str(data["work_end_time"]),
    )


def calendar_override_from_json(data: dict[str, object]) -> CalendarOverrideDTO:
    return CalendarOverrideDTO(
        id=UUID(str(data["id"])),
        override_type=str(data["override_type"]),
        starts_at=datetime.fromisoformat(str(data["starts_at"])),
        ends_at=datetime.fromisoformat(str(data["ends_at"])),
        comment=(
            str(data["comment"]) if isinstance(data.get("comment"), str) else None
        ),
        timezone=str(data["timezone"]),
        is_active=bool(data["is_active"]),
    )


def busy_interval_from_json(data: dict[str, object]) -> BusyIntervalDTO:
    return BusyIntervalDTO(
        id=UUID(str(data["id"])),
        kind=str(data["kind"]),
        status=str(data["status"]),
        starts_at=datetime.fromisoformat(str(data["starts_at"])),
        ends_at=datetime.fromisoformat(str(data["ends_at"])),
    )


def calendar_from_json(data: dict[str, object]) -> CalendarDTO:
    schedule_data = data.get("schedule")
    overrides = data.get("overrides")
    busy_intervals = data.get("busy_intervals")
    return CalendarDTO(
        schedule=schedule_from_json(schedule_data)
        if isinstance(schedule_data, dict)
        else None,
        overrides=tuple(
            calendar_override_from_json(item)
            for item in overrides
            if isinstance(item, dict)
        )
        if isinstance(overrides, list)
        else (),
        busy_intervals=tuple(
            busy_interval_from_json(item)
            for item in busy_intervals
            if isinstance(item, dict)
        )
        if isinstance(busy_intervals, list)
        else (),
    )


def available_order_from_json(data: dict[str, object]) -> AvailableOrderDTO:
    return AvailableOrderDTO(
        id=UUID(str(data["id"])),
        service_name=str(data["service_name"]),
        matching_mode=data["matching_mode"]
        if isinstance(data["matching_mode"], str)
        else None,
        status=str(data["status"]),
        start_at=datetime.fromisoformat(str(data["start_at"])),
        end_at=datetime.fromisoformat(str(data["end_at"])),
        objects_count=int(cast(str | int, data["objects_count"])),
        total_amount=Decimal(str(data["total_amount"])),
        distance_km=(
            Decimal(str(data["distance_km"]))
            if data.get("distance_km") is not None
            else None
        ),
    )


def order_match_from_json(data: dict[str, object]) -> OrderMatchDTO:
    return OrderMatchDTO(
        id=UUID(str(data["id"])),
        order_id=UUID(str(data["order_id"])),
        performer_id=UUID(str(data["performer_id"])),
        source=str(data["source"]),
        status=str(data["status"]),
        starts_at=datetime.fromisoformat(str(data["starts_at"])),
        ends_at=datetime.fromisoformat(str(data["ends_at"])),
        response_expires_at=datetime.fromisoformat(str(data["response_expires_at"])),
        selected_at=(
            datetime.fromisoformat(str(data["selected_at"]))
            if data.get("selected_at") is not None
            else None
        ),
        closed_at=(
            datetime.fromisoformat(str(data["closed_at"]))
            if data.get("closed_at") is not None
            else None
        ),
        close_reason=(
            str(data["close_reason"])
            if isinstance(data.get("close_reason"), str)
            else None
        ),
        timezone=str(data["timezone"]),
        service_name=(
            str(data["service_name"])
            if isinstance(data.get("service_name"), str)
            else None
        ),
        total_amount=(
            Decimal(str(data["total_amount"]))
            if data.get("total_amount") is not None
            else None
        ),
        distance_km=(
            Decimal(str(data["distance_km"]))
            if data.get("distance_km") is not None
            else None
        ),
        customer_comment=(
            str(data["customer_comment"])
            if isinstance(data.get("customer_comment"), str)
            else None
        ),
    )


def match_action_from_json(data: dict[str, object]) -> MatchActionDTO:
    order_data = data.get("order")
    match_data = data.get("match")
    payment_data = data.get("payment")
    if not isinstance(order_data, dict) or not isinstance(match_data, dict):
        raise BackendUnavailableError("Backend response is invalid")
    confirmation_url = (
        str(payment_data["confirmation_url"])
        if isinstance(payment_data, dict)
        and isinstance(payment_data.get("confirmation_url"), str)
        else None
    )
    return MatchActionDTO(
        order_id=UUID(str(order_data["id"])),
        match_id=UUID(str(match_data["id"])),
        status=str(order_data["status"]),
        confirmation_url=confirmation_url,
    )


def my_orders_page_from_json(data: dict[str, object]) -> MyOrdersPageDTO:
    raw_items = data.get("items")
    return MyOrdersPageDTO(
        items=tuple(
            my_order_summary_from_json(item)
            for item in raw_items
            if isinstance(item, dict)
        )
        if isinstance(raw_items, list)
        else (),
        page=int(cast(str | int, data["page"])),
        page_size=int(cast(str | int, data["page_size"])),
        total_items=int(cast(str | int, data["total_items"])),
        total_pages=int(cast(str | int, data["total_pages"])),
    )


def my_order_summary_from_json(data: dict[str, object]) -> MyOrderSummaryDTO:
    payment_deadline_at = (
        datetime.fromisoformat(str(data["payment_deadline_at"]))
        if data.get("payment_deadline_at") is not None
        else None
    )
    return MyOrderSummaryDTO(
        id=UUID(str(data["id"])),
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


def my_order_card_from_json(data: dict[str, object]) -> MyOrderCardDTO:
    summary = my_order_summary_from_json(data)
    payment_expires_at = (
        datetime.fromisoformat(str(data["payment_expires_at"]))
        if data.get("payment_expires_at") is not None
        else None
    )
    return MyOrderCardDTO(
        **summary.__dict__,
        payment_status=data["payment_status"]
        if isinstance(data["payment_status"], str)
        else None,
        payment_expires_at=payment_expires_at,
        customer_comment=(
            str(data["customer_comment"])
            if isinstance(data.get("customer_comment"), str)
            else None
        ),
    )


def contact_request_from_json(data: dict[str, object]) -> ContactRequestDTO:
    return ContactRequestDTO(
        id=UUID(str(data["id"])),
        order_id=UUID(str(data["order_id"])),
        performer_id=UUID(str(data["performer_id"])),
        requested_method=str(data["requested_method"]),
        status=str(data["status"]),
        failure_reason=(
            str(data["failure_reason"])
            if isinstance(data.get("failure_reason"), str)
            else None
        ),
        contact_name=str(data["contact_name"]),
        contact_phone=(
            str(data["contact_phone"])
            if data.get("contact_phone") is not None
            else None
        ),
        contact_telegram_username=(
            str(data["contact_telegram_username"])
            if data.get("contact_telegram_username") is not None
            else None
        ),
    )


def order_location_from_json(data: dict[str, object]) -> OrderLocationDTO:
    address = data.get("address")
    address_data = address if isinstance(address, dict) else {}
    return OrderLocationDTO(
        order_id=UUID(str(data["order_id"])),
        city_name=str(data["city_name"]),
        district_name=(
            str(data["district_name"])
            if isinstance(data.get("district_name"), str)
            else None
        ),
        address_text=address_data.get("address_text")
        if isinstance(address_data.get("address_text"), str)
        else None,
        entrance=address_data.get("entrance")
        if isinstance(address_data.get("entrance"), str)
        else None,
        floor=address_data.get("floor")
        if isinstance(address_data.get("floor"), str)
        else None,
        apartment=address_data.get("apartment")
        if isinstance(address_data.get("apartment"), str)
        else None,
        comment=address_data.get("comment")
        if isinstance(address_data.get("comment"), str)
        else None,
    )


def order_report_from_json(data: dict[str, object]) -> OrderReportDTO:
    files = data.get("files")
    return OrderReportDTO(
        id=UUID(str(data["id"])),
        order_id=UUID(str(data["order_id"])),
        performer_id=UUID(str(data["performer_id"])),
        completed_work=str(data["completed_work"]),
        comment=(
            str(data["comment"]) if isinstance(data.get("comment"), str) else None
        ),
        problem_flag=bool(data["problem_flag"]),
        problem_description=(
            str(data["problem_description"])
            if isinstance(data.get("problem_description"), str)
            else None
        ),
        submitted_at=datetime.fromisoformat(str(data["submitted_at"])),
        files=tuple(
            OrderReportFileDTO(
                id=UUID(str(item["id"])),
                original_name=item.get("original_name")
                if isinstance(item.get("original_name"), str)
                else None,
                mime_type=str(item["mime_type"]),
                signed_url=str(item["signed_url"]),
            )
            for item in files
            if isinstance(item, dict)
        )
        if isinstance(files, list)
        else (),
    )


__all__ = [
    "address_from_json",
    "address_suggestion_from_json",
    "available_order_from_json",
    "busy_interval_from_json",
    "calendar_from_json",
    "calendar_override_from_json",
    "contact_request_from_json",
    "error_message",
    "file_from_json",
    "match_action_from_json",
    "my_order_card_from_json",
    "my_order_summary_from_json",
    "my_orders_page_from_json",
    "order_location_from_json",
    "order_report_from_json",
    "order_match_from_json",
    "performer_from_json",
    "performer_service_from_json",
    "schedule_from_json",
    "service_category_from_json",
    "service_from_json",
    "support_contact_from_json",
]
