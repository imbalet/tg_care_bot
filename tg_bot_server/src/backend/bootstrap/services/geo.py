from ._shared import (
    Any,
    SqlAlchemyAddressRepository,
    SuggestAddressCommand,
    SuggestAddressesUseCase,
)
from .context import Service


class GeoServices(Service):
    async def suggest_addresses(self, command: SuggestAddressCommand) -> Any:
        async with self._uow() as uow:
            return await SuggestAddressesUseCase(
                SqlAlchemyAddressRepository(uow.session),
                self._geocoder(),
            ).execute(command)
