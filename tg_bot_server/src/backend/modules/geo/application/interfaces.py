from typing import Protocol

from .dto import AddressSuggestionDTO, NormalizedAddressDTO


class Geocoder(Protocol):
    async def suggest(
        self,
        *,
        query: str,
        city: str | None = None,
        limit: int = 5,
    ) -> tuple[AddressSuggestionDTO, ...]:
        pass

    async def normalize(self, *, unrestricted_value: str) -> NormalizedAddressDTO:
        pass
