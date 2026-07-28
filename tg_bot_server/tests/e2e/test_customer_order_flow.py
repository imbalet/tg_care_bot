from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest

from tests.support.settings import TestSettings


def _headers(settings: TestSettings) -> dict[str, str]:
    return {"X-Service-Key": settings.service_key}


@pytest.mark.e2e
async def test_customer_can_register_create_object_and_publish_boarding_order(
    test_settings: TestSettings,
) -> None:
    headers = _headers(test_settings)
    telegram_id = 900000001
    async with httpx.AsyncClient(
        base_url=test_settings.e2e_base_url,
        timeout=test_settings.e2e_request_timeout_seconds,
    ) as client:
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
                "location_source": "performer_address",
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
async def test_contact_request_requires_a_succeeded_active_payment(
    e2e_client: httpx.AsyncClient,
    e2e_db: Any,
    direct_order_factory: Any,
) -> None:
    customer, performer, order = await direct_order_factory()
    match_response = await e2e_client.get(
        f"/api/orders/{order['id']}/matches",
        params={"customer_id": customer.entity_id},
    )
    assert match_response.status_code == 200, match_response.text
    match = match_response.json()[0]

    accept_response = await e2e_client.post(
        f"/api/orders/matches/{match['id']}/direct/accept",
        json={"performer_id": performer.entity_id},
    )
    assert accept_response.status_code == 200, accept_response.text
    payment_id = accept_response.json()["payment"]["payment_id"]

    await e2e_db.execute(
        "UPDATE orders SET status = 'confirmed' WHERE id = $1",
        order["id"],
    )
    unpaid_customer_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer.telegram_id}/contact-requests",
        json={"order_id": order["id"]},
    )
    unpaid_performer_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer.telegram_id}/contact-requests",
        json={"order_id": order["id"]},
    )
    assert unpaid_customer_response.status_code == 409
    assert unpaid_performer_response.status_code == 409

    await e2e_db.execute(
        "UPDATE payments SET status = 'succeeded' WHERE id = $1",
        payment_id,
    )
    paid_customer_response = await e2e_client.post(
        f"/api/customers/by-telegram/{customer.telegram_id}/contact-requests",
        json={"order_id": order["id"]},
    )
    paid_performer_response = await e2e_client.post(
        f"/api/performers/by-telegram/{performer.telegram_id}/contact-requests",
        json={"order_id": order["id"]},
    )
    assert paid_customer_response.status_code == 201, paid_customer_response.text
    assert paid_performer_response.status_code == 201, paid_performer_response.text
    assert paid_customer_response.json()["contact_telegram_username"]
    assert paid_performer_response.json()["contact_telegram_username"]


@pytest.mark.e2e
async def test_business_api_rejects_missing_service_key_without_touching_state(
    test_settings: TestSettings,
) -> None:
    async with httpx.AsyncClient(
        base_url=test_settings.e2e_base_url,
        timeout=test_settings.e2e_request_timeout_seconds,
    ) as client:
        response = await client.get(f"/api/orders/customer/{uuid4()}/my")

    assert response.status_code == 401
