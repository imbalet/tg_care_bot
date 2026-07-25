from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import count
from typing import Any

import asyncpg
import boto3
import httpx
import pytest_asyncio
from botocore.exceptions import ClientError

from tests.support.settings import TestSettings

_CUSTOMER_IDS = count(910000001)
_PERFORMER_IDS = count(920000001)


@dataclass(frozen=True)
class E2EActor:
    telegram_id: int
    entity_id: str
    city_id: str


@pytest_asyncio.fixture
async def e2e_client(
    e2e_s3: None,
    test_settings: TestSettings,
) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        base_url=test_settings.e2e_base_url,
        headers={"X-Service-Key": test_settings.service_key},
        timeout=test_settings.e2e_request_timeout_seconds,
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="session", autouse=True)
async def e2e_s3(test_settings: TestSettings) -> AsyncIterator[None]:
    client = boto3.client(
        "s3",
        endpoint_url=test_settings.s3_endpoint_url,
        aws_access_key_id=test_settings.s3_access_key_id,
        aws_secret_access_key=test_settings.s3_secret_access_key,
        region_name=test_settings.s3_region,
    )
    try:
        await asyncio.to_thread(client.head_bucket, Bucket=test_settings.s3_bucket)
    except ClientError as error:
        if error.response["Error"]["Code"] not in {"404", "NoSuchBucket"}:
            raise
        await asyncio.to_thread(
            client.create_bucket,
            Bucket=test_settings.s3_bucket,
        )
    yield None


@pytest_asyncio.fixture
async def e2e_db(test_settings: TestSettings) -> AsyncIterator[asyncpg.Connection]:
    connection = await asyncpg.connect(
        host=test_settings.db_host,
        port=test_settings.db_port,
        user=test_settings.db_user,
        password=test_settings.db_pass,
        database=test_settings.db_name,
    )
    try:
        yield connection
    finally:
        await connection.close()


@pytest_asyncio.fixture
async def e2e_catalog(
    e2e_client: httpx.AsyncClient,
) -> dict[str, Any]:
    cities_response = await e2e_client.get("/api/catalog/cities")
    assert cities_response.status_code == 200, cities_response.text
    legal_response = await e2e_client.get("/api/legal-documents")
    assert legal_response.status_code == 200, legal_response.text
    catalog_response = await e2e_client.get("/api/catalog")
    assert catalog_response.status_code == 200, catalog_response.text
    return {
        "city": next(item for item in cities_response.json() if item["is_active"]),
        "legal_document_ids": [item["id"] for item in legal_response.json()],
        "catalog": catalog_response.json(),
    }


@pytest_asyncio.fixture
async def customer_factory(
    e2e_client: httpx.AsyncClient,
    e2e_catalog: dict[str, Any],
) -> Callable[[], Awaitable[E2EActor]]:

    async def create() -> E2EActor:
        telegram_id = next(_CUSTOMER_IDS)
        response = await e2e_client.post(
            "/api/customers/register",
            json={
                "telegram_id": telegram_id,
                "full_name": f"E2E Customer {telegram_id}",
                "phone": "+79990000000",
                "city_id": e2e_catalog["city"]["id"],
                "contact_method": "telegram",
                "telegram_username": f"e2e_customer_{telegram_id}",
                "accepted_legal_document_ids": e2e_catalog["legal_document_ids"],
            },
        )
        assert response.status_code == 201, response.text
        return E2EActor(
            telegram_id=telegram_id,
            entity_id=response.json()["id"],
            city_id=e2e_catalog["city"]["id"],
        )

    return create


@pytest_asyncio.fixture
async def performer_factory(
    e2e_client: httpx.AsyncClient,
    e2e_catalog: dict[str, Any],
    test_settings: TestSettings,
) -> Callable[[], Awaitable[E2EActor]]:
    async def create() -> E2EActor:
        telegram_id = next(_PERFORMER_IDS)
        login_response = await e2e_client.post(
            "/admin/login",
            json={
                "email": test_settings.default_admin_email,
                "password": test_settings.default_admin_password,
            },
        )
        assert login_response.status_code == 200, login_response.text
        admin_id = login_response.json()["admin"]["id"]
        csrf_token = login_response.json()["csrf_token"]

        invitation_response = await e2e_client.post(
            "/api/admin/performer-invitations",
            json={
                "telegram_id": telegram_id,
                "created_by_admin_id": admin_id,
            },
        )
        assert invitation_response.status_code == 201, invitation_response.text

        registration_response = await e2e_client.post(
            "/api/performers/register-by-invitation",
            json={
                "telegram_id": telegram_id,
                "full_name": f"E2E Performer {telegram_id}",
                "phone": "+79991112233",
                "city_id": e2e_catalog["city"]["id"],
                "contact_method": "telegram",
                "about_text": "E2E performer",
                "telegram_username": f"e2e_performer_{telegram_id}",
                "accepted_legal_document_ids": e2e_catalog["legal_document_ids"],
            },
        )
        assert registration_response.status_code == 201, registration_response.text
        performer_id = registration_response.json()["id"]

        activation_response = await e2e_client.post(
            f"/api/admin/performers/{performer_id}/activate",
        )
        assert activation_response.status_code == 200, activation_response.text

        service = next(
            service
            for category in e2e_catalog["catalog"]["categories"]
            for service in category["services"]
            if service["code"] == "pet_boarding"
        )
        approval_response = await e2e_client.post(
            f"/admin/performers/{performer_id}/services/{service['id']}/approve",
            headers={"X-CSRF-Token": csrf_token},
            json={"admin_max_objects": 3, "constraints": {}},
        )
        assert approval_response.status_code == 200, approval_response.text

        address_response = await e2e_client.post(
            f"/api/performers/by-telegram/{telegram_id}/addresses",
            json={
                "city_id": e2e_catalog["city"]["id"],
                "unrestricted_value": "г. Москва, ул. Тестовая, д. 1",
            },
        )
        assert address_response.status_code == 201, address_response.text
        address_id = address_response.json()["id"]
        current_address_response = await e2e_client.patch(
            f"/api/performers/by-telegram/{telegram_id}/current-address/{address_id}",
        )
        assert current_address_response.status_code == 200, (
            current_address_response.text
        )

        enabled_response = await e2e_client.patch(
            f"/api/performers/by-telegram/{telegram_id}/services/{service['id']}/enabled",
            json={"is_enabled": True},
        )
        assert enabled_response.status_code == 200, enabled_response.text

        accepting_response = await e2e_client.patch(
            f"/api/performers/by-telegram/{telegram_id}/accepting-orders",
            json={"is_accepting_orders": True},
        )
        assert accepting_response.status_code == 200, accepting_response.text

        schedule_response = await e2e_client.patch(
            f"/api/performers/by-telegram/{telegram_id}/schedule",
            json={
                "schedule_type": "every_day",
                "work_start_time": "00:00:00",
                "work_end_time": "23:59:00",
            },
        )
        assert schedule_response.status_code == 200, schedule_response.text

        return E2EActor(
            telegram_id=telegram_id,
            entity_id=performer_id,
            city_id=e2e_catalog["city"]["id"],
        )

    return create


@pytest_asyncio.fixture
async def pool_order_factory(
    e2e_client: httpx.AsyncClient,
    e2e_catalog: dict[str, Any],
    customer_factory: Callable[[], Awaitable[E2EActor]],
) -> Callable[[], Awaitable[tuple[E2EActor, dict[str, Any]]]]:
    async def create() -> tuple[E2EActor, dict[str, Any]]:
        customer = await customer_factory()
        care_object_response = await e2e_client.post(
            f"/api/customers/by-telegram/{customer.telegram_id}/care-objects",
            json={
                "object_type": "pet",
                "display_name": "E2E Pet",
                "age_group": "adult",
                "species": "dog",
                "pet_size": "medium",
            },
        )
        assert care_object_response.status_code == 201, care_object_response.text

        service = next(
            service
            for category in e2e_catalog["catalog"]["categories"]
            for service in category["services"]
            if service["code"] == "pet_boarding"
        )
        start = datetime.now(UTC) + timedelta(days=1)
        order_response = await e2e_client.post(
            "/api/orders/pool",
            json={
                "customer_id": customer.entity_id,
                "service_id": service["id"],
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(days=1)).isoformat(),
                "care_object_ids": [care_object_response.json()["id"]],
                "address_id": None,
                "report_photo_consent": None,
                "option_values": {},
            },
        )
        assert order_response.status_code == 201, order_response.text
        return customer, order_response.json()

    return create


@pytest_asyncio.fixture
async def direct_order_factory(
    e2e_client: httpx.AsyncClient,
    e2e_db: asyncpg.Connection,
    e2e_catalog: dict[str, Any],
    customer_factory: Callable[[], Awaitable[E2EActor]],
    performer_factory: Callable[[], Awaitable[E2EActor]],
) -> Callable[[], Awaitable[tuple[E2EActor, E2EActor, dict[str, Any]]]]:
    async def create() -> tuple[E2EActor, E2EActor, dict[str, Any]]:
        customer = await customer_factory()
        performer = await performer_factory()
        care_object_response = await e2e_client.post(
            f"/api/customers/by-telegram/{customer.telegram_id}/care-objects",
            json={
                "object_type": "pet",
                "display_name": "E2E Direct Pet",
                "age_group": "adult",
                "species": "dog",
                "pet_size": "medium",
            },
        )
        assert care_object_response.status_code == 201, care_object_response.text
        service = next(
            service
            for category in e2e_catalog["catalog"]["categories"]
            for service in category["services"]
            if service["code"] == "pet_boarding"
        )
        await e2e_db.execute(
            "UPDATE services SET base_price = 100 WHERE id = $1",
            service["id"],
        )
        start = datetime.now(UTC) + timedelta(days=1)
        order_response = await e2e_client.post(
            "/api/orders/direct",
            json={
                "customer_id": customer.entity_id,
                "performer_id": performer.entity_id,
                "service_id": service["id"],
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(days=1)).isoformat(),
                "care_object_ids": [care_object_response.json()["id"]],
                "address_id": None,
                "report_photo_consent": None,
                "option_values": {},
            },
        )
        assert order_response.status_code == 201, order_response.text
        return customer, performer, order_response.json()

    return create
