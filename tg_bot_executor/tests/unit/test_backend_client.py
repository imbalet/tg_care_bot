from uuid import uuid4

import httpx
import pytest

from executor_bot.infrastructure.http import (
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
async def test_registration_state_parses_registered_performer() -> None:
    performer_id = uuid4()
    city_id = uuid4()
    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "state": "registered",
                    "invitation": None,
                    "performer": {
                        "id": str(performer_id),
                        "telegram_id": 123,
                        "full_name": "Performer User",
                        "phone": "+79990000000",
                        "telegram_username": None,
                        "contact_method": "both",
                        "city_id": str(city_id),
                        "about_text": "About",
                        "status": "profile_pending",
                        "is_accepting_orders": False,
                        "current_address_id": None,
                    },
                },
            ),
        ),
    )

    state = await client.get_registration_state(123)

    assert state.state == "registered"
    assert state.performer is not None
    assert state.performer.id == performer_id
    await client.close()


@pytest.mark.asyncio
async def test_register_performer_maps_validation_error() -> None:
    client = BackendClient(
        base_url="http://backend",
        service_key="secret",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda _request: httpx.Response(422)),
    )

    with pytest.raises(BackendValidationError):
        await client.register_performer(
            telegram_id=123,
            full_name="Performer User",
            phone="+79990000000",
            city_id=uuid4(),
            contact_method="both",
            about_text="About",
            telegram_username=None,
            accepted_legal_document_ids=(uuid4(),),
        )
    await client.close()


@pytest.mark.asyncio
async def test_ensure_telegram_topics_sends_chat_id() -> None:
    topic_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/telegram-topics/performer/123/ensure"
        assert json_body(request) == {"chat_id": 456}
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(topic_id),
                    "account_type": "performer",
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
async def test_work_address_methods_use_backend_contract() -> None:
    city_id = uuid4()
    address_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/geocoding/address-suggestions":
            return httpx.Response(
                200,
                json=[{"value": "Москва, Тверская, 1", "unrestricted_value": "full"}],
            )
        if request.method == "GET":
            return httpx.Response(200, json=[address_json(address_id, city_id)])
        if request.method == "POST":
            assert json_body(request)["unrestricted_value"] == "full"
            return httpx.Response(201, json=address_json(address_id, city_id))
        if request.method == "PATCH":
            assert "current-address" in request.url.path
            return httpx.Response(200, json=address_json(address_id, city_id))
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
    addresses = await client.list_work_addresses(telegram_id=123)
    created = await client.create_work_address(
        telegram_id=123,
        city_id=city_id,
        unrestricted_value="full",
        entrance=None,
        floor=None,
        apartment=None,
        comment=None,
    )
    current = await client.set_current_work_address(
        telegram_id=123,
        address_id=address_id,
    )
    await client.delete_work_address(telegram_id=123, address_id=address_id)

    assert suggestions[0].unrestricted_value == "full"
    assert addresses[0].id == address_id
    assert created.address_text == "Москва, Тверская, 1"
    assert current.id == address_id
    await client.close()


def address_json(address_id: object, city_id: object) -> dict[str, object]:
    return {
        "id": str(address_id),
        "owner_type": "performer",
        "customer_id": None,
        "performer_id": str(uuid4()),
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


def json_body(request: httpx.Request) -> dict[str, object]:
    import json

    data = json.loads(request.content.decode())
    if not isinstance(data, dict):
        raise AssertionError("Expected object body")
    return data
