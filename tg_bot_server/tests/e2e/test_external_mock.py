import httpx
import pytest


@pytest.mark.e2e
async def test_deterministic_external_mock_is_reachable() -> None:
    async with httpx.AsyncClient(
        base_url="http://mock-external:8080",
        timeout=5,
    ) as client:
        response = await client.post("/payments/init", json={"test": True})

    assert response.status_code == 200
    assert response.json() == {"Success": True, "PaymentId": "test-payment"}
