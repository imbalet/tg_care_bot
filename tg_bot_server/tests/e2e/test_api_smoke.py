import httpx
import pytest

from tests.support.settings import TestSettings


@pytest.mark.e2e
async def test_api_is_reachable(test_settings: TestSettings) -> None:
    async with httpx.AsyncClient(
        base_url=test_settings.e2e_base_url,
        timeout=test_settings.e2e_request_timeout_seconds,
    ) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
