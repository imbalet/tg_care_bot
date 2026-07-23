import os

import httpx
import pytest


@pytest.mark.e2e
async def test_api_is_reachable() -> None:
    base_url = os.getenv("E2E_BASE_URL", "http://api:8000")
    async with httpx.AsyncClient(base_url=base_url, timeout=5) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
