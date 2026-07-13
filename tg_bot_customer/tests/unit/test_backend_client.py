from datetime import datetime
from uuid import uuid4

import httpx
import pytest

from customer_bot.infrastructure.http import (
    BackendClient,
    BackendUnauthorizedError,
    BackendUnavailableError,
    BackendValidationError,
)


@pytest.mark.asyncio
async def test_ping_sends_service_key() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Service-Key"] == "secret"
        return httpx.Response(200, json={"status": "ok"})

    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    await client.ping()
    await client.close()


@pytest.mark.asyncio
async def test_ping_maps_unauthorized() -> None:
    client = BackendClient(
        base_url="http://backend",
        service_key="wrong",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda _request: httpx.Response(401)),
    )

    with pytest.raises(BackendUnauthorizedError):
        await client.ping()
    await client.close()


@pytest.mark.asyncio
async def test_ping_maps_server_error() -> None:
    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
    )

    with pytest.raises(BackendUnavailableError):
        await client.ping()
    await client.close()


@pytest.mark.asyncio
async def test_get_customer_profile_returns_none_on_404() -> None:
    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda _request: httpx.Response(404)),
    )

    assert await client.get_customer_profile(123) is None
    await client.close()


@pytest.mark.asyncio
async def test_catalog_methods_parse_backend_dtos() -> None:
    city_id = uuid4()
    document_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/catalog/cities":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(city_id),
                        "name": "Москва",
                        "slug": "moscow",
                        "timezone": "Europe/Moscow",
                        "is_active": True,
                    },
                ],
            )
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(document_id),
                    "document_type": "user_agreement",
                    "version": "v1",
                    "content_url": "https://example.invalid/legal",
                    "is_active": True,
                    "published_at": "2026-07-12T00:00:00+00:00",
                },
            ],
        )

    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    cities = await client.list_active_cities()
    documents = await client.list_active_legal_documents()

    assert cities[0].id == city_id
    assert cities[0].name == "Москва"
    assert documents[0].id == document_id
    assert documents[0].document_type == "user_agreement"
    await client.close()


@pytest.mark.asyncio
async def test_register_customer_sends_backend_payload() -> None:
    city_id = uuid4()
    document_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json_body(request)
        assert payload["telegram_id"] == 123
        assert payload["city_id"] == str(city_id)
        assert payload["accepted_legal_document_ids"] == [str(document_id)]
        return httpx.Response(
            201,
            json={
                "id": str(uuid4()),
                "telegram_id": 123,
                "full_name": "Customer User",
                "phone": "+79990000000",
                "telegram_username": None,
                "contact_method": "both",
                "city_id": str(city_id),
                "status": "active",
            },
        )

    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    profile = await client.register_customer(
        telegram_id=123,
        full_name="Customer User",
        phone="+79990000000",
        city_id=city_id,
        contact_method="both",
        telegram_username=None,
        accepted_legal_document_ids=(document_id,),
    )

    assert profile.telegram_id == 123
    assert profile.telegram_username is None
    await client.close()


@pytest.mark.asyncio
async def test_register_customer_maps_validation_error() -> None:
    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda _request: httpx.Response(422)),
    )

    with pytest.raises(BackendValidationError):
        await client.register_customer(
            telegram_id=123,
            full_name="Customer User",
            phone="+79990000000",
            city_id=uuid4(),
            contact_method="both",
            telegram_username=None,
            accepted_legal_document_ids=(uuid4(),),
        )
    await client.close()


@pytest.mark.asyncio
async def test_ensure_telegram_topics_sends_chat_id() -> None:
    topic_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/telegram-topics/customer/123/ensure"
        assert json_body(request) == {"chat_id": 456}
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(topic_id),
                    "account_type": "customer",
                    "owner_id": str(uuid4()),
                    "topic_kind": "notifications",
                    "chat_id": 456,
                    "message_thread_id": None,
                    "status": "fallback",
                },
            ],
        )

    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    topics = await client.ensure_telegram_topics(telegram_id=123, chat_id=456)

    assert topics[0].id == topic_id
    assert topics[0].topic_kind == "notifications"
    assert topics[0].message_thread_id is None
    await client.close()


@pytest.mark.asyncio
async def test_update_telegram_topic_mapping_sends_backend_payload() -> None:
    topic_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/telegram-topics/{topic_id}/mapping"
        assert json_body(request) == {
            "chat_id": 456,
            "message_thread_id": 789,
            "status": "active",
        }
        return httpx.Response(
            200,
            json={
                "id": str(topic_id),
                "account_type": "customer",
                "owner_id": str(uuid4()),
                "topic_kind": "pets",
                "chat_id": 456,
                "message_thread_id": 789,
                "status": "active",
            },
        )

    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    topic = await client.update_telegram_topic_mapping(
        topic_id=topic_id,
        chat_id=456,
        message_thread_id=789,
        status="active",
    )

    assert topic.id == topic_id
    assert topic.topic_kind == "pets"
    assert topic.message_thread_id == 789
    await client.close()


@pytest.mark.asyncio
async def test_care_object_methods_use_backend_contract() -> None:
    care_object_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/api/customers/by-telegram/123/care-objects"
            assert request.url.params["object_type"] == "pet"
            return httpx.Response(200, json=[care_object_json(care_object_id)])
        if request.method == "POST":
            payload = json_body(request)
            assert payload["object_type"] == "pet"
            assert payload["display_name"] == "Barsik"
            return httpx.Response(201, json=care_object_json(care_object_id))
        if request.method == "PATCH":
            assert str(care_object_id) in request.url.path
            payload = json_body(request)
            assert payload["display_name"] == "Updated"
            return httpx.Response(200, json=care_object_json(care_object_id))
        if request.method == "DELETE":
            assert str(care_object_id) in request.url.path
            return httpx.Response(200, json={"status": "deleted"})
        raise AssertionError("Unexpected request")

    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    listed = await client.list_care_objects(telegram_id=123, object_type="pet")
    created = await client.create_care_object(
        telegram_id=123,
        object_type="pet",
        display_name="Barsik",
        age_group="adult",
        species="cat",
        pet_size="small",
    )
    updated = await client.update_care_object(
        telegram_id=123,
        care_object_id=care_object_id,
        display_name="Updated",
        age_group="adult",
        species="cat",
        pet_size="small",
    )
    await client.delete_care_object(telegram_id=123, care_object_id=care_object_id)

    assert listed[0].id == care_object_id
    assert created.object_type == "pet"
    assert updated.id == care_object_id
    await client.close()


@pytest.mark.asyncio
async def test_address_methods_use_backend_contract() -> None:
    city_id = uuid4()
    address_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/geocoding/address-suggestions":
            assert request.url.params["city_id"] == str(city_id)
            return httpx.Response(
                200,
                json=[{"value": "Москва, Тверская, 1", "unrestricted_value": "full"}],
            )
        if request.method == "GET":
            return httpx.Response(200, json=[address_json(address_id, city_id)])
        if request.method == "POST":
            payload = json_body(request)
            assert payload["unrestricted_value"] == "full"
            return httpx.Response(201, json=address_json(address_id, city_id))
        if request.method == "DELETE":
            assert str(address_id) in request.url.path
            return httpx.Response(200, json={"status": "deleted"})
        raise AssertionError("Unexpected request")

    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    suggestions = await client.suggest_addresses(city_id=city_id, query="Тверская")
    addresses = await client.list_addresses(telegram_id=123)
    created = await client.create_address(
        telegram_id=123,
        city_id=city_id,
        unrestricted_value="full",
        entrance=None,
        floor=None,
        apartment=None,
        comment=None,
    )
    await client.delete_address(telegram_id=123, address_id=address_id)

    assert suggestions[0].unrestricted_value == "full"
    assert addresses[0].id == address_id
    assert created.address_text == "Москва, Тверская, 1"
    await client.close()


@pytest.mark.asyncio
async def test_order_methods_use_backend_contract() -> None:
    category_id = uuid4()
    service_id = uuid4()
    customer_id = uuid4()
    order_id = uuid4()
    performer_id = uuid4()
    address_id = uuid4()
    care_object_id = uuid4()
    start_at = datetime.fromisoformat("2026-07-14T10:00:00+03:00")
    end_at = datetime.fromisoformat("2026-07-14T12:00:00+03:00")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/catalog":
            return httpx.Response(
                200,
                json={
                    "categories": [
                        {
                            "id": str(category_id),
                            "code": "pets",
                            "name": "Питомцы",
                            "care_object_type": "pet",
                            "max_objects_per_order": 3,
                            "is_active": True,
                            "sort_order": 10,
                            "services": [service_json(service_id)],
                        },
                    ],
                },
            )
        if request.url.path == "/api/orders/price-preview":
            payload = json_body(request)
            assert payload["service_id"] == str(service_id)
            assert payload["objects_count"] == 1
            return httpx.Response(200, json=price_json(service_id))
        if request.url.path == "/api/orders/drafts":
            payload = json_body(request)
            assert payload["customer_id"] == str(customer_id)
            assert payload["care_object_ids"] == [str(care_object_id)]
            assert payload["address_id"] == str(address_id)
            return httpx.Response(
                201, json=order_json(order_id, customer_id, service_id)
            )
        if request.url.path == f"/api/orders/drafts/{order_id}/publish-pool":
            return httpx.Response(
                200, json=order_json(order_id, customer_id, service_id)
            )
        if request.url.path == f"/api/orders/drafts/{order_id}/publish-direct":
            assert json_body(request)["performer_id"] == str(performer_id)
            return httpx.Response(
                200, json=order_json(order_id, customer_id, service_id)
            )
        if request.url.path == "/api/availability/suitable-performers":
            assert request.url.params["city_id"]
            assert request.url.params["service_id"] == str(service_id)
            return httpx.Response(
                200,
                json=[
                    {
                        "performer_id": str(performer_id),
                        "full_name": "Executor User",
                        "service_id": str(service_id),
                        "service_code": "pet_sitting",
                        "service_name": "Передержка",
                        "performer_max_objects": 2,
                        "distance_km": "1.5",
                        "current_address_id": None,
                    },
                ],
            )
        raise AssertionError(f"Unexpected request {request.method} {request.url}")

    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    categories = await client.list_catalog_categories()
    price = await client.preview_order_price(
        service_id=service_id,
        start_at=start_at,
        end_at=end_at,
        objects_count=1,
    )
    draft = await client.create_order_draft(
        customer_id=customer_id,
        service_id=service_id,
        start_at=start_at,
        end_at=end_at,
        care_object_ids=(care_object_id,),
        address_id=address_id,
        customer_comment="comment",
        report_photo_consent=True,
    )
    pool = await client.publish_order_pool(order_id=order_id)
    direct = await client.publish_order_direct(
        order_id=order_id,
        performer_id=performer_id,
    )
    performers = await client.find_suitable_performers(
        city_id=uuid4(),
        service_id=service_id,
        start_at=start_at,
        end_at=end_at,
        objects_count=1,
        care_object_ids=(care_object_id,),
        address_id=address_id,
    )

    assert categories[0].services[0].id == service_id
    assert price.total_amount == 1200
    assert draft.id == order_id
    assert pool.status == "searching"
    assert direct.matching_mode == "pool"
    assert performers[0].performer_id == performer_id
    await client.close()


def address_json(address_id: object, city_id: object) -> dict[str, object]:
    return {
        "id": str(address_id),
        "owner_type": "customer",
        "customer_id": str(uuid4()),
        "performer_id": None,
        "city_id": str(city_id),
        "district_id": None,
        "address_text": "Москва, Тверская, 1",
        "fias_id": None,
        "latitude": "55.1",
        "longitude": "37.1",
        "geocoding_provider": "fake",
        "geocoding_quality": "0",
        "entrance": None,
        "floor": None,
        "apartment": None,
        "comment": None,
        "deleted_at": None,
        "created_at": "2026-07-13T00:00:00+00:00",
        "updated_at": "2026-07-13T00:00:00+00:00",
    }


def care_object_json(care_object_id: object) -> dict[str, object]:
    return {
        "id": str(care_object_id),
        "customer_id": str(uuid4()),
        "object_type": "pet",
        "display_name": "Barsik",
        "age_group": "adult",
        "species": "cat",
        "breed": None,
        "pet_size": "small",
        "mobility_assistance_required": None,
        "routine_notes": None,
        "behavior_notes": None,
        "deleted_at": None,
        "created_at": "2026-07-13T00:00:00+00:00",
        "updated_at": "2026-07-13T00:00:00+00:00",
    }


def service_json(service_id: object) -> dict[str, object]:
    return {
        "id": str(service_id),
        "code": "pet_sitting",
        "name": "Передержка",
        "description": "Описание",
        "price_type": "hourly",
        "base_price": "500.00",
        "location_policy": "customer_address",
        "photo_policy": "requires_customer_consent",
        "schedule_policy": "working_hours",
        "allows_multiday": False,
        "min_duration_minutes": 60,
        "max_duration_minutes": 480,
        "duration_step_minutes": 60,
        "is_active": True,
        "sort_order": 10,
    }


def price_json(service_id: object) -> dict[str, object]:
    return {
        "service_id": str(service_id),
        "service_code": "pet_sitting",
        "service_name": "Передержка",
        "price_type": "hourly",
        "duration_minutes": 120,
        "billable_minutes": 120,
        "started_24h_units": None,
        "objects_count": 1,
        "object_multiplier": "1.00",
        "base_price": "500.00",
        "service_amount": "1000.00",
        "platform_fee_percent": "20.00",
        "platform_fee_amount": "200.00",
        "performer_amount": "1000.00",
        "total_amount": "1200.00",
        "hold_limit_checked": True,
    }


def order_json(
    order_id: object, customer_id: object, service_id: object
) -> dict[str, object]:
    return {
        "id": str(order_id),
        "customer_id": str(customer_id),
        "service_id": str(service_id),
        "service_code": "pet_sitting",
        "service_name": "Передержка",
        "schedule_policy": "working_hours",
        "photo_policy": "requires_customer_consent",
        "matching_mode": "pool",
        "status": "searching",
        "address_id": str(uuid4()),
        "location_source": "customer_address",
        "start_at": "2026-07-14T10:00:00+03:00",
        "end_at": "2026-07-14T12:00:00+03:00",
        "objects_count": 1,
        "total_amount": "1200.00",
        "performer_amount": "1000.00",
        "platform_fee_amount": "200.00",
        "matching_deadline_at": "2026-07-14T09:30:00+03:00",
    }


def json_body(request: httpx.Request) -> dict[str, object]:
    import json

    data = json.loads(request.content.decode())
    if not isinstance(data, dict):
        raise AssertionError("Expected object body")
    return data
