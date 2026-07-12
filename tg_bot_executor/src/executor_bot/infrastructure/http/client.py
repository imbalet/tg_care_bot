from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import httpx

from .errors import (
    BackendUnauthorizedError,
    BackendUnavailableError,
    BackendValidationError,
)


@dataclass(frozen=True)
class CityDTO:
    id: UUID
    name: str


@dataclass(frozen=True)
class LegalDocumentDTO:
    id: UUID
    document_type: str
    version: str
    content_url: str


@dataclass(frozen=True)
class PerformerProfileDTO:
    id: UUID
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: UUID
    about_text: str | None
    status: str
    is_accepting_orders: bool
    current_address_id: UUID | None


@dataclass(frozen=True)
class RegistrationStateDTO:
    state: str
    performer: PerformerProfileDTO | None


@dataclass(frozen=True)
class TelegramTopicDTO:
    id: UUID
    topic_kind: str
    chat_id: int
    message_thread_id: int | None
    status: str


@dataclass(frozen=True)
class AddressSuggestionDTO:
    value: str
    unrestricted_value: str


@dataclass(frozen=True)
class AddressDTO:
    id: UUID
    city_id: UUID
    address_text: str
    entrance: str | None
    floor: str | None
    apartment: str | None
    comment: str | None


class BackendClient:
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

    async def ensure_telegram_topics(
        self,
        *,
        telegram_id: int,
        chat_id: int,
    ) -> tuple[TelegramTopicDTO, ...]:
        response = await self._request(
            "POST",
            f"/api/telegram-topics/performer/{telegram_id}/ensure",
            json={"chat_id": chat_id},
        )
        self._raise_for_status(response)
        return tuple(_topic_from_json(item) for item in response.json())

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

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.request(method, url, json=json, params=params)
        except httpx.HTTPError as exc:
            raise BackendUnavailableError("Backend is unavailable") from exc

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise BackendUnauthorizedError("Backend rejected service key")
        if response.status_code == 422:
            raise BackendValidationError("Backend rejected data")
        if response.status_code >= 400:
            raise BackendUnavailableError("Backend request failed")


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


def _topic_from_json(data: dict[str, object]) -> TelegramTopicDTO:
    return TelegramTopicDTO(
        id=UUID(str(data["id"])),
        topic_kind=str(data["topic_kind"]),
        chat_id=int(cast(str | int, data["chat_id"])),
        message_thread_id=int(cast(str | int, data["message_thread_id"]))
        if data["message_thread_id"] is not None
        else None,
        status=str(data["status"]),
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


__all__ = [
    "AddressDTO",
    "AddressSuggestionDTO",
    "BackendClient",
    "CityDTO",
    "LegalDocumentDTO",
    "PerformerProfileDTO",
    "RegistrationStateDTO",
    "TelegramTopicDTO",
]
