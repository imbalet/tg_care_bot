import httpx
import pytest

from tests.support.settings import TestSettings


@pytest.mark.e2e
async def test_deterministic_external_mock_is_reachable(
    test_settings: TestSettings,
) -> None:
    async with httpx.AsyncClient(
        base_url=test_settings.telegram_api_base_url,
        timeout=test_settings.e2e_request_timeout_seconds,
    ) as client:
        response = await client.post("/payments/init", json={"test": True})

    assert response.status_code == 200
    assert response.json() == {
        "Success": True,
        "PaymentId": "test-payment",
        "PaymentURL": "https://pay.test/confirmation/test-payment",
    }
