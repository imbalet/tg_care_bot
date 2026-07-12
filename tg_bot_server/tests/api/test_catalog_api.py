from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.bootstrap.api import create_app
from backend.bootstrap.settings import get_settings
from backend.modules.catalog.application import (
    CatalogDTO,
    CityDTO,
    LegalDocumentDTO,
    ServiceCategoryDTO,
    ServiceDTO,
)
from backend.modules.catalog.presentation.api import routes


class FakeSessionFactory:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *args: object) -> None:
        return None

    def __call__(self) -> FakeSessionFactory:
        return self


class FakeCatalogQueryService:
    def __init__(self, _session: object) -> None:
        pass

    async def list_cities(self, *, active_only: bool) -> tuple[CityDTO, ...]:
        return (
            CityDTO(
                id=uuid4(),
                name="Москва",
                slug="moscow",
                timezone="Europe/Moscow",
                is_active=active_only,
            ),
        )

    async def list_legal_documents(
        self,
        *,
        active_only: bool,
    ) -> tuple[LegalDocumentDTO, ...]:
        return (
            LegalDocumentDTO(
                id=uuid4(),
                document_type="user_agreement",
                version="v1",
                content_url="https://example.invalid/legal/user_agreement/v1",
                is_active=active_only,
                published_at=datetime.now(UTC),
            ),
        )

    async def get_catalog(self, *, active_only: bool) -> CatalogDTO:
        service = ServiceDTO(
            id=uuid4(),
            code="nanny_care",
            name="Присмотр за ребенком",
            description="Присмотр за ребенком",
            price_type="hourly",
            base_price=Decimal("0.00"),
            location_policy="customer_address",
            photo_policy="requires_customer_consent",
            schedule_policy="working_hours",
            allows_multiday=False,
            min_duration_minutes=None,
            max_duration_minutes=None,
            duration_step_minutes=60,
            is_active=active_only,
            sort_order=10,
        )
        return CatalogDTO(
            categories=(
                ServiceCategoryDTO(
                    id=uuid4(),
                    code="nanny",
                    name="Няня",
                    care_object_type="child",
                    max_objects_per_order=2,
                    is_active=active_only,
                    sort_order=10,
                    services=(service,),
                ),
            ),
        )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    get_settings.cache_clear()
    monkeypatch.setattr(
        routes,
        "SqlAlchemyCatalogQueryService",
        FakeCatalogQueryService,
    )
    app = create_app()
    with TestClient(app) as test_client:
        app.state.container = SimpleNamespace(session_factory=FakeSessionFactory())
        yield test_client
    get_settings.cache_clear()


def test_list_active_cities(client: TestClient) -> None:
    response = client.get("/api/catalog/cities")

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "moscow"
    assert response.json()[0]["is_active"] is True


def test_list_active_legal_documents(client: TestClient) -> None:
    response = client.get("/api/legal-documents")

    assert response.status_code == 200
    assert response.json()[0]["document_type"] == "user_agreement"
    assert response.json()[0]["is_active"] is True


def test_get_active_catalog(client: TestClient) -> None:
    response = client.get("/api/catalog")

    assert response.status_code == 200
    data = response.json()
    assert data["categories"][0]["code"] == "nanny"
    assert data["categories"][0]["services"][0]["code"] == "nanny_care"
