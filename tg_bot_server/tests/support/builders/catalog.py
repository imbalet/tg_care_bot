from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from backend.modules.catalog.infrastructure import CityModel


@dataclass(frozen=True)
class CatalogBuilder:
    """Build explicit catalog entities for persistence scenarios."""

    def city(
        self,
        *,
        city_id: UUID | None = None,
        name: str = "Test City",
        slug: str | None = None,
        timezone: str = "Europe/Moscow",
    ) -> CityModel:
        identifier = city_id or uuid4()
        return CityModel(
            id=identifier,
            name=name,
            slug=slug or f"test-city-{identifier.hex[:8]}",
            timezone=timezone,
        )
