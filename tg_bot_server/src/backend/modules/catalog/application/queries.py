from typing import Protocol
from uuid import UUID

from backend.modules.catalog.application.dto import (
    CatalogDTO,
    CityDTO,
    LegalDocumentDTO,
)


class CatalogQueryService(Protocol):
    async def get_city_timezone(self, city_id: UUID) -> str | None:
        pass

    async def list_cities(self, *, active_only: bool) -> tuple[CityDTO, ...]:
        pass

    async def list_legal_documents(
        self,
        *,
        active_only: bool,
    ) -> tuple[LegalDocumentDTO, ...]:
        pass

    async def get_catalog(self, *, active_only: bool) -> CatalogDTO:
        pass
