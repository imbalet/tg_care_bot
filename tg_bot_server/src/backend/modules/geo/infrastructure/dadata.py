from decimal import Decimal, InvalidOperation

import httpx

from backend.common.domain import ValidationError
from backend.modules.geo.application import (
    AddressSuggestionDTO,
    Geocoder,
    NormalizedAddressDTO,
)

DADATA_PROVIDER = "dadata"


class DaDataGeocoder(Geocoder):
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        base_url: str,
        timeout_seconds: float,
        retry_count: int,
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._retry_count = retry_count

    async def suggest(
        self,
        *,
        query: str,
        city: str | None = None,
        limit: int = 5,
    ) -> tuple[AddressSuggestionDTO, ...]:
        payload: dict[str, object] = {"query": query, "count": limit}
        if city is not None:
            payload["locations"] = [{"city": city}]
        data = await self._post(payload)
        suggestions = data.get("suggestions")
        if not isinstance(suggestions, list):
            return ()
        return tuple(
            suggestion
            for item in suggestions
            if (suggestion := _suggestion_from_json(item)) is not None
        )

    async def normalize(self, *, unrestricted_value: str) -> NormalizedAddressDTO:
        suggestions = await self.suggest(query=unrestricted_value, limit=5)
        matches = tuple(
            suggestion
            for suggestion in suggestions
            if suggestion.unrestricted_value == unrestricted_value
        )
        if len(matches) != 1:
            raise ValidationError("Address selection is invalid or ambiguous")
        suggestion = matches[0]
        return NormalizedAddressDTO(
            address_text=suggestion.value,
            fias_id=suggestion.fias_id,
            latitude=suggestion.latitude,
            longitude=suggestion.longitude,
            provider=DADATA_PROVIDER,
            quality=suggestion.quality,
        )

    async def _post(self, payload: dict[str, object]) -> dict[str, object]:
        if not self._api_key:
            raise ValidationError("DaData API key is not configured")
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._secret_key:
            headers["X-Secret"] = self._secret_key
        last_error: httpx.HTTPError | None = None
        for _attempt in range(self._retry_count + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=self._timeout_seconds,
                    headers=headers,
                ) as client:
                    response = await client.post(
                        "/suggestions/api/4_1/rs/suggest/address",
                        json=payload,
                    )
                if response.status_code >= 400:
                    raise ValidationError("DaData rejected address request")
                data = response.json()
                if isinstance(data, dict):
                    return data
                return {}
            except httpx.HTTPError as exc:
                last_error = exc
        raise ValidationError("DaData is unavailable") from last_error


def _suggestion_from_json(item: object) -> AddressSuggestionDTO | None:
    if not isinstance(item, dict):
        return None
    value = item.get("value")
    unrestricted = item.get("unrestricted_value")
    data = item.get("data")
    if not isinstance(value, str) or not isinstance(unrestricted, str):
        return None
    if not isinstance(data, dict):
        data = {}
    return AddressSuggestionDTO(
        value=value,
        unrestricted_value=unrestricted,
        fias_id=_optional_str(data.get("fias_id")),
        latitude=_decimal_or_none(data.get("geo_lat")),
        longitude=_decimal_or_none(data.get("geo_lon")),
        quality=_optional_str(data.get("qc_geo")),
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _decimal_or_none(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None
