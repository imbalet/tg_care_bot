from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import httpx

from .errors import (
    BackendNotFoundError,
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
class CustomerProfileDTO:
    id: UUID
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: UUID
    status: str


@dataclass(frozen=True)
class TelegramTopicDTO:
    id: UUID
    topic_kind: str
    chat_id: int
    message_thread_id: int | None
    status: str


@dataclass(frozen=True)
class CareObjectDTO:
    id: UUID
    object_type: str
    display_name: str
    age_group: str
    species: str | None
    breed: str | None
    pet_size: str | None
    mobility_assistance_required: bool | None
    routine_notes: str | None
    behavior_notes: str | None


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

    async def get_customer_profile(
        self,
        telegram_id: int,
    ) -> CustomerProfileDTO | None:
        response = await self._request(
            "GET",
            f"/api/customers/by-telegram/{telegram_id}/profile",
        )
        if response.status_code == 404:
            return None
        self._raise_for_status(response)
        return _customer_from_json(response.json())

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
    ) -> CustomerProfileDTO:
        response = await self._request(
            "POST",
            "/api/customers/register",
            json={
                "telegram_id": telegram_id,
                "full_name": full_name,
                "phone": phone,
                "city_id": str(city_id),
                "contact_method": contact_method,
                "telegram_username": telegram_username,
                "accepted_legal_document_ids": [
                    str(document_id) for document_id in accepted_legal_document_ids
                ],
            },
        )
        self._raise_for_status(response)
        return _customer_from_json(response.json())

    async def update_customer_username(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
    ) -> CustomerProfileDTO:
        response = await self._request(
            "PATCH",
            f"/api/customers/by-telegram/{telegram_id}/telegram-username",
            json={"telegram_username": telegram_username},
        )
        self._raise_for_status(response)
        return _customer_from_json(response.json())

    async def ensure_telegram_topics(
        self,
        *,
        telegram_id: int,
        chat_id: int,
    ) -> tuple[TelegramTopicDTO, ...]:
        response = await self._request(
            "POST",
            f"/api/telegram-topics/customer/{telegram_id}/ensure",
            json={"chat_id": chat_id},
        )
        self._raise_for_status(response)
        return tuple(_topic_from_json(item) for item in response.json())

    async def list_care_objects(
        self,
        *,
        telegram_id: int,
        object_type: str | None = None,
    ) -> tuple[CareObjectDTO, ...]:
        params = {"object_type": object_type} if object_type is not None else None
        response = await self._request(
            "GET",
            f"/api/customers/by-telegram/{telegram_id}/care-objects",
            params=params,
        )
        self._raise_for_status(response)
        return tuple(_care_object_from_json(item) for item in response.json())

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
    ) -> CareObjectDTO:
        response = await self._request(
            "POST",
            f"/api/customers/by-telegram/{telegram_id}/care-objects",
            json={
                "object_type": object_type,
                "display_name": display_name,
                "age_group": age_group,
                "species": species,
                "breed": breed,
                "pet_size": pet_size,
                "mobility_assistance_required": mobility_assistance_required,
                "routine_notes": routine_notes,
                "behavior_notes": behavior_notes,
            },
        )
        self._raise_for_status(response)
        return _care_object_from_json(response.json())

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
    ) -> CareObjectDTO:
        response = await self._request(
            "PATCH",
            f"/api/customers/by-telegram/{telegram_id}/care-objects/{care_object_id}",
            json={
                "display_name": display_name,
                "age_group": age_group,
                "species": species,
                "breed": breed,
                "pet_size": pet_size,
                "mobility_assistance_required": mobility_assistance_required,
                "routine_notes": routine_notes,
                "behavior_notes": behavior_notes,
            },
        )
        self._raise_for_status(response)
        return _care_object_from_json(response.json())

    async def delete_care_object(
        self,
        *,
        telegram_id: int,
        care_object_id: UUID,
    ) -> None:
        response = await self._request(
            "DELETE",
            f"/api/customers/by-telegram/{telegram_id}/care-objects/{care_object_id}",
        )
        self._raise_for_status(response)

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

    async def list_addresses(self, *, telegram_id: int) -> tuple[AddressDTO, ...]:
        response = await self._request(
            "GET",
            f"/api/customers/by-telegram/{telegram_id}/addresses",
        )
        self._raise_for_status(response)
        return tuple(_address_from_json(item) for item in response.json())

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
    ) -> AddressDTO:
        response = await self._request(
            "POST",
            f"/api/customers/by-telegram/{telegram_id}/addresses",
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

    async def delete_address(self, *, telegram_id: int, address_id: UUID) -> None:
        response = await self._request(
            "DELETE",
            f"/api/customers/by-telegram/{telegram_id}/addresses/{address_id}",
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
        if response.status_code == 404:
            raise BackendNotFoundError("Backend resource not found")
        if response.status_code == 422:
            raise BackendValidationError("Backend rejected data")
        if response.status_code >= 400:
            raise BackendUnavailableError("Backend request failed")


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


__all__ = [
    "AddressDTO",
    "AddressSuggestionDTO",
    "BackendClient",
    "CareObjectDTO",
    "CityDTO",
    "CustomerProfileDTO",
    "LegalDocumentDTO",
    "TelegramTopicDTO",
]
