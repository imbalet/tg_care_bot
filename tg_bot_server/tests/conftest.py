from __future__ import annotations

import pytest

from tests.support.settings import TestSettings, get_test_settings


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: isolated unit tests")
    config.addinivalue_line("markers", "api: FastAPI tests through ASGI transport")
    config.addinivalue_line(
        "markers",
        "integration: tests requiring PostgreSQL, Redis and MinIO",
    )
    config.addinivalue_line("markers", "e2e: tests executed against the Compose stack")


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    return get_test_settings()


@pytest.fixture
def no_op() -> None:
    """Provide a readable fixture for tests that only need pytest setup."""
