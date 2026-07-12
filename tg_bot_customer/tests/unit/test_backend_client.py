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


def json_body(request: httpx.Request) -> dict[str, object]:
    import json

    data = json.loads(request.content.decode())
    if not isinstance(data, dict):
        raise AssertionError("Expected object body")
    return data
