from decimal import Decimal

from pydantic import BaseModel


class AddressSuggestionResponse(BaseModel):
    value: str
    unrestricted_value: str
    fias_id: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    quality: str | None
