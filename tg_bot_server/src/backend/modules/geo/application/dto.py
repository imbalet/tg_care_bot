from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AddressSuggestionDTO:
    value: str
    unrestricted_value: str
    fias_id: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    quality: str | None


@dataclass(frozen=True)
class NormalizedAddressDTO:
    address_text: str
    fias_id: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    provider: str
    quality: str | None


__all__ = ["AddressSuggestionDTO", "NormalizedAddressDTO"]
