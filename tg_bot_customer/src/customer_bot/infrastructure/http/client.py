import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from customer_bot.application.dto import (
    AddressDTO,
    AddressSuggestionDTO,
    CancellationPreviewDTO,
    CareObjectDTO,
    CityDTO,
    CustomerProfileDTO,
    LegalDocumentDTO,
    MatchActionDTO,
    MyOrderCardDTO,
    MyOrdersPageDTO,
    OrderDTO,
    OrderLocationDTO,
    OrderMatchDTO,
    OrderReportDTO,
    PaymentStatusDTO,
    PricePreviewDTO,
    ServiceCategoryDTO,
    SuitablePerformerDTO,
    SupportContactDTO,
    SupportRecordDTO,
)
from customer_bot.application.ports import BackendPort

from .errors import (
    BackendNotFoundError,
    BackendUnauthorizedError,
    BackendUnavailableError,
    BackendValidationError,
)
from .parsers import (
    _address_from_json,
    _cancellation_preview_from_json,
    _care_object_from_json,
    _customer_from_json,
    _error_message,
    _match_action_from_json,
    _my_order_card_from_json,
    _my_orders_page_from_json,
    _order_from_json,
    _order_location_from_json,
    _order_match_from_json,
    _order_report_from_json,
    _order_request_json,
    _payment_status_from_json,
    _price_preview_from_json,
    _service_category_from_json,
    _suitable_performer_from_json,
    _support_contact_from_json,
    _support_record_from_json,
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

    async def get_support_contact(self) -> SupportContactDTO:
        response = await self._request("GET", "/api/catalog/support-contact")
        self._raise_for_status(response)
        return _support_contact_from_json(response.json())

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

    async def cancel_customer_order(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> OrderDTO:
        response = await self._request(
            "POST",
            f"/api/orders/{order_id}/cancel",
            json={"actor_type": "customer", "actor_id": str(customer_id)},
        )
        self._raise_for_status(response)
        return _order_from_json(response.json())

    async def get_customer_cancellation_preview(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> CancellationPreviewDTO:
        response = await self._request(
            "GET",
            f"/api/orders/customer/{customer_id}/my/{order_id}/cancellation-preview",
        )
        self._raise_for_status(response)
        return _cancellation_preview_from_json(response.json())

    async def list_customer_orders(
        self,
        *,
        customer_id: UUID,
        group: str,
        page: int,
        page_size: int = 5,
        category_code: str | None = None,
    ) -> MyOrdersPageDTO:
        response = await self._request(
            "GET",
            f"/api/orders/customer/{customer_id}/my",
            params={
                "group": group,
                "page": page,
                "page_size": page_size,
                "category_code": category_code,
            },
        )
        self._raise_for_status(response)
        return _my_orders_page_from_json(response.json())

    async def get_customer_order_card(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> MyOrderCardDTO:
        response = await self._request(
            "GET",
            f"/api/orders/customer/{customer_id}/my/{order_id}",
        )
        self._raise_for_status(response)
        return _my_order_card_from_json(response.json())

    async def get_customer_order_location(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> OrderLocationDTO:
        response = await self._request(
            "GET",
            f"/api/orders/customer/{customer_id}/my/{order_id}/location",
        )
        self._raise_for_status(response)
        return _order_location_from_json(response.json())

    async def get_customer_order_report(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> OrderReportDTO:
        response = await self._request(
            "GET",
            f"/api/orders/customer/{customer_id}/my/{order_id}/report",
        )
        self._raise_for_status(response)
        return _order_report_from_json(response.json())

    async def confirm_customer_order_report(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> OrderDTO:
        response = await self._request(
            "POST",
            f"/api/orders/customer/{customer_id}/my/{order_id}/confirm-report",
        )
        self._raise_for_status(response)
        return _order_from_json(response.json())

    async def start_customer_order(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> OrderDTO:
        response = await self._request(
            "POST",
            f"/api/orders/customer/{customer_id}/my/{order_id}/start",
        )
        self._raise_for_status(response)
        return _order_from_json(response.json())

    async def create_support_request(
        self,
        *,
        telegram_id: int,
        order_id: UUID | None,
        request_type: str,
        text: str,
    ) -> SupportRecordDTO:
        response = await self._request(
            "POST",
            f"/api/customers/by-telegram/{telegram_id}/support-requests",
            json={
                "order_id": str(order_id) if order_id is not None else None,
                "type": request_type,
                "text": text,
                "file_ids": [],
            },
        )
        self._raise_for_status(response)
        return _support_record_from_json(response.json())

    async def create_complaint(
        self,
        *,
        telegram_id: int,
        order_id: UUID | None,
        category: str,
        text: str,
    ) -> SupportRecordDTO:
        response = await self._request(
            "POST",
            f"/api/customers/by-telegram/{telegram_id}/complaints",
            json={
                "order_id": str(order_id) if order_id is not None else None,
                "category": category,
                "text": text,
                "file_ids": [],
            },
        )
        self._raise_for_status(response)
        return _support_record_from_json(response.json())

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
