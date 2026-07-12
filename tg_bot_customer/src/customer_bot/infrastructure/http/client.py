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

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            return await self._client.request(method, url, json=json)
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


__all__ = [
    "BackendClient",
    "CityDTO",
    "CustomerProfileDTO",
    "LegalDocumentDTO",
    "TelegramTopicDTO",
]
