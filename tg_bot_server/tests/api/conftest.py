from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest

from backend.bootstrap.api import create_app
from backend.bootstrap.settings import get_settings
from tests.support.settings import apply_test_environment


@pytest.fixture(scope="session", autouse=True)
def api_environment() -> Iterator[None]:
    monkeypatch = pytest.MonkeyPatch()
    apply_test_environment(monkeypatch)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    monkeypatch.undo()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as test_client:
            yield test_client
