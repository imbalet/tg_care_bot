import httpx
import pytest


@pytest.mark.api
async def test_live_endpoint(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
