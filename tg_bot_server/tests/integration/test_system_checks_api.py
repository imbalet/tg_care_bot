import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.bootstrap.api import create_app
from backend.bootstrap.settings import get_settings
from tests.integration.database import IntegrationDatabase, migrate_to_head

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="PostgreSQL integration tests require RUN_POSTGRES_TESTS=1",
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    get_settings.cache_clear()
    migrate_to_head(IntegrationDatabase())
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_system_check_endpoint_persists_record(client: TestClient) -> None:
    response = client.post(
        "/internal/system-checks",
        json={"name": "integration-smoke"},
        headers={"X-Service-Key": "dev-service-key"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "integration-smoke"
    assert data["id"]
    assert data["created_at"]
