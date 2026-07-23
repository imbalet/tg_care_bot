import httpx
import pytest


@pytest.mark.api
async def test_live_endpoint(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.api
async def test_internal_ping_requires_service_key(client: httpx.AsyncClient) -> None:
    unauthorized = await client.get("/internal/ping")
    authorized = await client.get(
        "/internal/ping",
        headers={"X-Service-Key": "test-service-key"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {"status": "ok"}
