import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import httpx

from customer_bot.application.dto import (
    AddressDTO,
    AddressSuggestionDTO,
    CareObjectDTO,
    CityDTO,
    CustomerProfileDTO,
    LegalDocumentDTO,
    MatchActionDTO,
    OrderDTO,
    OrderMatchDTO,
    PaymentStatusDTO,
    PricePreviewDTO,
    ServiceCategoryDTO,
    ServiceDTO,
    ServiceOptionDTO,
    SuitablePerformerDTO,
)
from customer_bot.application.ports import BackendPort

from .errors import (
    BackendNotFoundError,
    BackendUnauthorizedError,
    BackendUnavailableError,
    BackendValidationError,
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
            headers={"X-Service-Name": "customer-bot", "X-Service-Key": service_key},
            timeout=timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        logger.info("Closing backend HTTP client")
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

    async def list_catalog_categories(self) -> tuple[ServiceCategoryDTO, ...]:
        response = await self._request("GET", "/api/catalog")
        self._raise_for_status(response)
        payload = response.json()
        categories = payload["categories"] if isinstance(payload, dict) else []
        return tuple(_service_category_from_json(item) for item in categories)

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

    async def preview_order_price(
        self,
        *,
        customer_id: UUID,
        service_id: UUID,
        start_at: datetime,
        end_at: datetime,
        objects_count: int,
    ) -> PricePreviewDTO:
        response = await self._request(
            "POST",
            "/api/orders/price-preview",
            json={
                "customer_id": str(customer_id),
                "service_id": str(service_id),
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "objects_count": objects_count,
            },
        )
        self._raise_for_status(response)
        return _price_preview_from_json(response.json())

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
    ) -> OrderDTO:
        response = await self._request(
            "POST",
            "/api/orders/pool",
            json=_order_request_json(
                customer_id=customer_id,
                service_id=service_id,
                start_at=start_at,
                end_at=end_at,
                care_object_ids=care_object_ids,
                address_id=address_id,
                customer_comment=customer_comment,
                report_photo_consent=report_photo_consent,
                option_values=option_values,
            ),
        )
        self._raise_for_status(response)
        return _order_from_json(response.json())

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
    ) -> OrderDTO:
        payload = _order_request_json(
            customer_id=customer_id,
            service_id=service_id,
            start_at=start_at,
            end_at=end_at,
            care_object_ids=care_object_ids,
            address_id=address_id,
            customer_comment=customer_comment,
            report_photo_consent=report_photo_consent,
            option_values=option_values,
        )
        payload["performer_id"] = str(performer_id)
        response = await self._request(
            "POST",
            "/api/orders/direct",
            json=payload,
        )
        self._raise_for_status(response)
        return _order_from_json(response.json())

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
    ) -> tuple[SuitablePerformerDTO, ...]:
        params: dict[str, Any] = {
            "city_id": str(city_id),
            "service_id": str(service_id),
            "starts_at": start_at.isoformat(),
            "ends_at": end_at.isoformat(),
            "objects_count": objects_count,
            "limit": 5,
        }
        if care_object_ids:
            params["care_object_ids"] = [str(item) for item in care_object_ids]
        if address_id is not None:
            params["address_id"] = str(address_id)
        response = await self._request(
            "GET",
            "/api/availability/suitable-performers",
            params=params,
        )
        self._raise_for_status(response)
        return tuple(_suitable_performer_from_json(item) for item in response.json())

    async def list_order_matches(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> tuple[OrderMatchDTO, ...]:
        response = await self._request(
            "GET",
            f"/api/orders/{order_id}/matches",
            params={"customer_id": str(customer_id)},
        )
        self._raise_for_status(response)
        return tuple(_order_match_from_json(item) for item in response.json())

    async def select_pool_response(
        self,
        *,
        match_id: UUID,
        customer_id: UUID,
    ) -> MatchActionDTO:
        response = await self._request(
            "POST",
            f"/api/orders/matches/{match_id}/pool/select",
            json={"customer_id": str(customer_id)},
        )
        self._raise_for_status(response)
        return _match_action_from_json(response.json())

    async def reject_pool_response(
        self,
        *,
        match_id: UUID,
        customer_id: UUID,
    ) -> OrderMatchDTO:
        response = await self._request(
            "POST",
            f"/api/orders/matches/{match_id}/pool/reject",
            json={"customer_id": str(customer_id)},
        )
        self._raise_for_status(response)
        return _order_match_from_json(response.json())

    async def get_payment_status(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> PaymentStatusDTO:
        response = await self._request(
            "GET",
            f"/api/payments/orders/{order_id}/status",
            params={"customer_id": str(customer_id)},
        )
        self._raise_for_status(response)
        return _payment_status_from_json(response.json())

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            response = await self._client.request(
                method,
                url,
                json=json,
                params=params,
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
    raw_options = data["options"] if isinstance(data["options"], list) else []
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
        match_type=str(data["match_type"]),
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
