from datetime import date, datetime, time, timedelta
from typing import Any, cast
from uuid import UUID

import httpx

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
    ServiceDTO,
)
from executor_bot.application.errors import (
    BackendUnauthorizedError,
    BackendUnavailableError,
    BackendValidationError,
)
from executor_bot.application.ports import BackendPort


class BackendClient(BackendPort):
    def __init__(
        self,
        base_url: str,
        service_key: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-Service-Key": service_key},
            timeout=timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def ping(self) -> None:
        response = await self._request("GET", "/internal/ping")
        self._raise_for_status(response)

    async def get_registration_state(self, telegram_id: int) -> RegistrationStateDTO:
        response = await self._request(
            "GET",
            f"/api/performers/by-telegram/{telegram_id}/registration-state",
        )
        self._raise_for_status(response)
        data = response.json()
        performer_data = data.get("performer")
        return RegistrationStateDTO(
            state=data["state"],
            performer=_performer_from_json(performer_data)
            if isinstance(performer_data, dict)
            else None,
        )

    async def list_active_cities(self) -> tuple[CityDTO, ...]:
        response = await self._request("GET", "/api/catalog/cities")
        self._raise_for_status(response)
        return tuple(
            CityDTO(id=UUID(item["id"]), name=item["name"]) for item in response.json()
        )

    async def list_active_legal_documents(self) -> tuple[LegalDocumentDTO, ...]:
        response = await self._request("GET", "/api/legal-documents")
        self._raise_for_status(response)
        return tuple(
            LegalDocumentDTO(
                id=UUID(item["id"]),
                document_type=item["document_type"],
                version=item["version"],
                content_url=item["content_url"],
            )
            for item in response.json()
        )

    async def list_catalog_categories(self) -> tuple[ServiceCategoryDTO, ...]:
        response = await self._request("GET", "/api/catalog")
        self._raise_for_status(response)
        payload = response.json()
        categories = payload["categories"] if isinstance(payload, dict) else []
        return tuple(_service_category_from_json(item) for item in categories)

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
    ) -> PerformerProfileDTO:
        response = await self._request(
            "POST",
            "/api/performers/register-by-invitation",
            json={
                "telegram_id": telegram_id,
                "full_name": full_name,
                "phone": phone,
                "city_id": str(city_id),
                "contact_method": contact_method,
                "about_text": about_text,
                "telegram_username": telegram_username,
                "accepted_legal_document_ids": [
                    str(document_id) for document_id in accepted_legal_document_ids
                ],
            },
        )
        self._raise_for_status(response)
        return _performer_from_json(response.json())

    async def update_performer_username(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
    ) -> PerformerProfileDTO:
        response = await self._request(
            "PATCH",
            f"/api/performers/by-telegram/{telegram_id}/telegram-username",
            json={"telegram_username": telegram_username},
        )
        self._raise_for_status(response)
        return _performer_from_json(response.json())

    async def suggest_addresses(
        self,
        *,
        city_id: UUID,
        query: str,
    ) -> tuple[AddressSuggestionDTO, ...]:
        response = await self._request(
            "GET",
            "/api/geocoding/address-suggestions",
            params={"city_id": str(city_id), "query": query},
        )
        self._raise_for_status(response)
        return tuple(
            AddressSuggestionDTO(
                value=str(item["value"]),
                unrestricted_value=str(item["unrestricted_value"]),
            )
            for item in response.json()
        )

    async def list_work_addresses(self, *, telegram_id: int) -> tuple[AddressDTO, ...]:
        response = await self._request(
            "GET",
            f"/api/performers/by-telegram/{telegram_id}/addresses",
        )
        self._raise_for_status(response)
        return tuple(_address_from_json(item) for item in response.json())

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
    ) -> AddressDTO:
        response = await self._request(
            "POST",
            f"/api/performers/by-telegram/{telegram_id}/addresses",
            json={
                "city_id": str(city_id),
                "unrestricted_value": unrestricted_value,
                "entrance": entrance,
                "floor": floor,
                "apartment": apartment,
                "comment": comment,
            },
        )
        self._raise_for_status(response)
        return _address_from_json(response.json())

    async def set_current_work_address(
        self,
        *,
        telegram_id: int,
        address_id: UUID,
    ) -> AddressDTO:
        response = await self._request(
            "PATCH",
            f"/api/performers/by-telegram/{telegram_id}/current-address/{address_id}",
        )
        self._raise_for_status(response)
        return _address_from_json(response.json())

    async def delete_work_address(self, *, telegram_id: int, address_id: UUID) -> None:
        response = await self._request(
            "DELETE",
            f"/api/performers/by-telegram/{telegram_id}/addresses/{address_id}",
        )
        self._raise_for_status(response)

    async def upload_avatar(
        self,
        *,
        telegram_id: int,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> FileDTO:
        response = await self._request(
            "POST",
            f"/api/performers/by-telegram/{telegram_id}/avatar",
            files={"file": (filename, content, content_type)},
        )
        self._raise_for_status(response)
        data = response.json()
        return FileDTO(
            id=UUID(str(data["id"])),
            mime_type=str(data["mime_type"]),
            size_bytes=int(data["size_bytes"])
            if data.get("size_bytes") is not None
            else None,
            status=str(data["status"]),
        )

    async def delete_avatar(self, *, telegram_id: int) -> None:
        response = await self._request(
            "DELETE",
            f"/api/performers/by-telegram/{telegram_id}/avatar",
        )
        self._raise_for_status(response)

    async def list_performer_services(
        self,
        *,
        telegram_id: int,
    ) -> tuple[PerformerServiceDTO, ...]:
        response = await self._request(
            "GET",
            f"/api/performers/by-telegram/{telegram_id}/services",
        )
        self._raise_for_status(response)
        return tuple(_performer_service_from_json(item) for item in response.json())

    async def set_service_enabled(
        self,
        *,
        telegram_id: int,
        service_id: UUID,
        is_enabled: bool,
    ) -> PerformerServiceDTO:
        response = await self._request(
            "PATCH",
            f"/api/performers/by-telegram/{telegram_id}/services/{service_id}/enabled",
            json={"is_enabled": is_enabled},
        )
        self._raise_for_status(response)
        return _performer_service_from_json(response.json())

    async def set_service_max_objects(
        self,
        *,
        telegram_id: int,
        service_id: UUID,
        performer_max_objects: int,
    ) -> PerformerServiceDTO:
        response = await self._request(
            "PATCH",
            f"/api/performers/by-telegram/{telegram_id}/services/{service_id}/max-objects",
            json={"performer_max_objects": performer_max_objects},
        )
        self._raise_for_status(response)
        return _performer_service_from_json(response.json())

    async def set_accepting_orders(
        self,
        *,
        telegram_id: int,
        is_accepting_orders: bool,
    ) -> PerformerProfileDTO:
        response = await self._request(
            "PATCH",
            f"/api/performers/by-telegram/{telegram_id}/accepting-orders",
            json={"is_accepting_orders": is_accepting_orders},
        )
        self._raise_for_status(response)
        return _performer_from_json(response.json())

    async def set_schedule(
        self,
        *,
        telegram_id: int,
        schedule_type: str,
        work_days: tuple[int, ...] | None,
        work_start_time: time,
        work_end_time: time,
    ) -> PerformerScheduleDTO:
        response = await self._request(
            "PATCH",
            f"/api/performers/by-telegram/{telegram_id}/schedule",
            json={
                "schedule_type": schedule_type,
                "work_days": list(work_days) if work_days is not None else None,
                "work_start_time": work_start_time.isoformat(),
                "work_end_time": work_end_time.isoformat(),
            },
        )
        self._raise_for_status(response)
        return _schedule_from_json(response.json())

    async def add_tomorrow_unavailable(self, *, telegram_id: int) -> None:
        tomorrow = date.today() + timedelta(days=1)
        starts_at = datetime.combine(tomorrow, time.min)
        ends_at = starts_at + timedelta(days=1)
        response = await self._request(
            "POST",
            f"/api/performers/by-telegram/{telegram_id}/calendar-overrides",
            json={
                "override_type": "unavailable",
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "comment": "Telegram quick action",
            },
        )
        self._raise_for_status(response)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.request(
                method,
                url,
                json=json,
                params=params,
                files=files,
            )
        except httpx.HTTPError as exc:
            raise BackendUnavailableError("Backend is unavailable") from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise BackendUnauthorizedError("Backend rejected service key")
        if response.status_code == 422:
            raise BackendValidationError(_error_message(response))
        if response.status_code >= 400:
            raise BackendUnavailableError("Backend request failed")


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


def _performer_from_json(data: dict[str, object]) -> PerformerProfileDTO:
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
    )


def _service_category_from_json(data: dict[str, object]) -> ServiceCategoryDTO:
    services = data.get("services")
    return ServiceCategoryDTO(
        id=UUID(str(data["id"])),
        code=str(data["code"]),
        name=str(data["name"]),
        sort_order=int(cast(str | int, data["sort_order"])),
        care_object_type=str(data["care_object_type"]),
        services=tuple(
            _service_from_json(item) for item in services if isinstance(item, dict)
        )
        if isinstance(services, list)
        else (),
    )


def _service_from_json(data: dict[str, object]) -> ServiceDTO:
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


def _performer_service_from_json(data: dict[str, object]) -> PerformerServiceDTO:
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


def _schedule_from_json(data: dict[str, object]) -> PerformerScheduleDTO:
    work_days = data.get("work_days")
    return PerformerScheduleDTO(
        schedule_type=str(data["schedule_type"]),
        work_days=tuple(int(item) for item in work_days)
        if isinstance(work_days, list)
        else None,
        work_start_time=str(data["work_start_time"]),
        work_end_time=str(data["work_end_time"]),
    )


__all__ = [
    "AddressDTO",
    "AddressSuggestionDTO",
    "BackendClient",
    "CityDTO",
    "FileDTO",
    "LegalDocumentDTO",
    "PerformerProfileDTO",
    "PerformerScheduleDTO",
    "PerformerServiceDTO",
    "RegistrationStateDTO",
]
