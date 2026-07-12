from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.bootstrap.api import create_app
from backend.bootstrap.settings import get_settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_live_returns_ok(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_internal_ping_requires_service_key(client: TestClient) -> None:
    response = client.get("/internal/ping")

    assert response.status_code == 401


def test_internal_ping_accepts_service_key(client: TestClient) -> None:
    response = client.get(
        "/internal/ping",
        headers={"X-Service-Key": "dev-service-key"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
