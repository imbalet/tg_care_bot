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
