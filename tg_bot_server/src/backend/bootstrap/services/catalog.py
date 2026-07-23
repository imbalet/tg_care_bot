from ._shared import (
    Any,
    SqlAlchemyCatalogQueryService,
)
from .context import Service


class CatalogServices(Service):
    async def list_cities(self, *, active_only: bool) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyCatalogQueryService(uow.session).list_cities(
                active_only=active_only,
            )

    async def get_catalog(self, *, active_only: bool) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyCatalogQueryService(uow.session).get_catalog(
                active_only=active_only,
            )

    async def get_support_contact(self) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyCatalogQueryService(
                uow.session
            ).get_support_contact()

    async def list_legal_documents(self, *, active_only: bool) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyCatalogQueryService(
                uow.session,
            ).list_legal_documents(active_only=active_only)
