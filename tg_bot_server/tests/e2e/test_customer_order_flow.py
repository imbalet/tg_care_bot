import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest


def _headers() -> dict[str, str]:
    return {"X-Service-Key": os.getenv("SERVICE_KEY", "test-service-key")}


@pytest.mark.e2e
async def test_customer_can_register_create_object_and_publish_boarding_order() -> None:
    base_url = os.getenv("E2E_BASE_URL", "http://api:8000")
    headers = _headers()
    telegram_id = 900000001
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        cities_response = await client.get("/api/catalog/cities", headers=headers)
        assert cities_response.status_code == 200
        city = next(item for item in cities_response.json() if item["is_active"])

        legal_response = await client.get(
            "/api/legal-documents",
            headers=headers,
        )
        assert legal_response.status_code == 200
        legal_ids = [item["id"] for item in legal_response.json()]

        register_response = await client.post(
            "/api/customers/register",
            headers=headers,
            json={
                "telegram_id": telegram_id,
                "full_name": "E2E Customer",
                "phone": "+79990000000",
                "city_id": city["id"],
                "contact_method": "telegram",
                "telegram_username": "e2e_customer",
                "accepted_legal_document_ids": legal_ids,
            },
        )
        assert register_response.status_code == 201, register_response.text
        customer_id = register_response.json()["id"]

        object_response = await client.post(
            f"/api/customers/by-telegram/{telegram_id}/care-objects",
            headers=headers,
            json={
                "object_type": "pet",
                "display_name": "E2E Pet",
                "age_group": "adult",
                "species": "dog",
                "pet_size": "medium",
            },
        )
        assert object_response.status_code == 201, object_response.text
        care_object_id = object_response.json()["id"]

        catalog_response = await client.get("/api/catalog", headers=headers)
        assert catalog_response.status_code == 200
        boarding_service = next(
            service
            for category in catalog_response.json()["categories"]
            if category["care_object_type"] == "pet"
            for service in category["services"]
            if service["code"] == "pet_boarding"
        )
        start = datetime.now(UTC) + timedelta(days=1)
        order_response = await client.post(
            "/api/orders/pool",
            headers=headers,
            json={
                "customer_id": customer_id,
                "service_id": boarding_service["id"],
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(days=1)).isoformat(),
                "care_object_ids": [care_object_id],
                "address_id": None,
                "report_photo_consent": None,
                "option_values": {},
            },
        )
        assert order_response.status_code == 201, order_response.text
        order = order_response.json()
        assert order["status"] == "searching"
        assert order["location_source"] == "performer_address"

        orders_response = await client.get(
            f"/api/orders/customer/{customer_id}/my",
            headers=headers,
        )
        assert orders_response.status_code == 200
        assert any(
            item["id"] == order["id"] for item in orders_response.json()["items"]
        )


@pytest.mark.e2e
async def test_business_api_rejects_missing_service_key_without_touching_state() -> (
    None
):
    base_url = os.getenv("E2E_BASE_URL", "http://api:8000")
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        response = await client.get(f"/api/orders/customer/{uuid4()}/my")

    assert response.status_code == 401
