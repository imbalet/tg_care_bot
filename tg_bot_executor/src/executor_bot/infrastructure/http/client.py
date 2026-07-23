import logging
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID

import httpx

from executor_bot.application.dto import (
    AddressDTO,
    AddressSuggestionDTO,
    AvailableOrderDTO,
    CityDTO,
    FileDTO,
    LegalDocumentDTO,
    MatchActionDTO,
    MyOrderCardDTO,
    MyOrdersPageDTO,
    OrderMatchDTO,
    PerformerProfileDTO,
    PerformerScheduleDTO,
    PerformerServiceDTO,
    RegistrationStateDTO,
    ServiceCategoryDTO,
    SupportContactDTO,
)
from executor_bot.application.errors import (
    BackendNotFoundError,
    BackendUnauthorizedError,
    BackendUnavailableError,
    BackendValidationError,
)
from executor_bot.application.ports import BackendPort
from executor_bot.infrastructure.http.parsers import (
    address_from_json as _address_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    available_order_from_json as _available_order_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    error_message as _error_message,
)
from executor_bot.infrastructure.http.parsers import (
    match_action_from_json as _match_action_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    my_order_card_from_json as _my_order_card_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    my_orders_page_from_json as _my_orders_page_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    order_match_from_json as _order_match_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    performer_from_json as _performer_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    performer_service_from_json as _performer_service_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    schedule_from_json as _schedule_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    service_category_from_json as _service_category_from_json,
)
from executor_bot.infrastructure.http.parsers import (
    support_contact_from_json as _support_contact_from_json,
)

logger = logging.getLogger(__name__)


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
            headers={
                "X-Service-Name": "executor-bot",
                "X-Service-Key": service_key,
            },
            timeout=timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        logger.info("Closing backend HTTP client")
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

    async def get_support_contact(self) -> SupportContactDTO:
        response = await self._request("GET", "/api/catalog/support-contact")
        self._raise_for_status(response)
        return _support_contact_from_json(response.json())

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

    async def list_available_orders(
        self,
        *,
        performer_id: UUID,
    ) -> tuple[AvailableOrderDTO, ...]:
        response = await self._request(
            "GET",
            "/api/orders/available",
            params={"performer_id": str(performer_id)},
        )
        self._raise_for_status(response)
        return tuple(_available_order_from_json(item) for item in response.json())

    async def create_pool_response(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
    ) -> OrderMatchDTO:
        response = await self._request(
            "POST",
            f"/api/orders/{order_id}/pool-responses",
            json={"performer_id": str(performer_id)},
        )
        self._raise_for_status(response)
        return _order_match_from_json(response.json())

    async def accept_direct_match(
        self,
        *,
        match_id: UUID,
        performer_id: UUID,
    ) -> MatchActionDTO:
        response = await self._request(
            "POST",
            f"/api/orders/matches/{match_id}/direct/accept",
            json={"performer_id": str(performer_id)},
        )
        self._raise_for_status(response)
        return _match_action_from_json(response.json())

    async def reject_direct_match(
        self,
        *,
        match_id: UUID,
        performer_id: UUID,
    ) -> OrderMatchDTO:
        response = await self._request(
            "POST",
            f"/api/orders/matches/{match_id}/direct/reject",
            json={"performer_id": str(performer_id)},
        )
        self._raise_for_status(response)
        return _order_match_from_json(response.json())

    async def list_performer_orders(
        self,
        *,
        performer_id: UUID,
        group: str,
        page: int,
        page_size: int = 5,
    ) -> MyOrdersPageDTO:
        response = await self._request(
            "GET",
            f"/api/orders/performer/{performer_id}/my",
            params={"group": group, "page": page, "page_size": page_size},
        )
        self._raise_for_status(response)
        return _my_orders_page_from_json(response.json())

    async def get_performer_order_card(
        self,
        *,
        performer_id: UUID,
        order_id: UUID,
    ) -> MyOrderCardDTO:
        response = await self._request(
            "GET",
            f"/api/orders/performer/{performer_id}/my/{order_id}",
        )
        self._raise_for_status(response)
        return _my_order_card_from_json(response.json())

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
            response = await self._client.request(
                method,
                url,
                json=json,
                params=params,
                files=files,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "Backend request failed",
                extra={
                    "method": method,
                    "url": url,
                    "exception_type": type(exc).__name__,
                },
            )
            raise BackendUnavailableError("Backend is unavailable") from exc
        if response.status_code >= 400:
            logger.warning(
                "Backend returned error response",
                extra={
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                },
            )
        return response

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise BackendUnauthorizedError("Backend rejected service key")
        if response.status_code == 404:
            raise BackendNotFoundError("Backend resource not found")
        if response.status_code == 422:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            raise BackendValidationError(_error_message(payload))
        if response.status_code >= 400:
            raise BackendUnavailableError("Backend request failed")


__all__ = ["BackendClient"]
