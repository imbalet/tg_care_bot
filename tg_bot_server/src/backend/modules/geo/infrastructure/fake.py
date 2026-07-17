from backend.common.domain import NotFoundError
from backend.modules.geo.application import (
    AddressSuggestionDTO,
    Geocoder,
    NormalizedAddressDTO,
)


class FakeGeocoder(Geocoder):
    def __init__(self, suggestions: tuple[AddressSuggestionDTO, ...]) -> None:
        self._suggestions = suggestions

    async def suggest(
        self,
        *,
        query: str,
        city: str | None = None,
        limit: int = 5,
    ) -> tuple[AddressSuggestionDTO, ...]:
        del city
        if not query.strip():
            return ()
        return self._suggestions[:limit]

    async def normalize(self, *, unrestricted_value: str) -> NormalizedAddressDTO:
        for suggestion in self._suggestions:
            if suggestion.unrestricted_value == unrestricted_value:
                return NormalizedAddressDTO(
                    address_text=suggestion.value,
                    fias_id=suggestion.fias_id,
                    latitude=suggestion.latitude,
                    longitude=suggestion.longitude,
                    provider="fake",
                    quality=suggestion.quality,
                )
        raise NotFoundError("Address suggestion not found")
