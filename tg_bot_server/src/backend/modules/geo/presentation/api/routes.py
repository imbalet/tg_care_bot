from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.addresses.application import (
    SuggestAddressCommand,
    SuggestAddressesUseCase,
)
from backend.modules.addresses.infrastructure import SqlAlchemyAddressRepository
from backend.modules.geo.application import AddressSuggestionDTO
from backend.modules.geo.infrastructure import DaDataGeocoder

router = APIRouter(
    prefix="/api/geocoding",
    tags=["geocoding"],
    dependencies=[Depends(require_service_key)],
)


class AddressSuggestionResponse(BaseModel):
    value: str
    unrestricted_value: str
    fias_id: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    quality: str | None


@router.get("/address-suggestions")
async def address_suggestions(
    container: Annotated[Container, Depends(get_container)],
    city_id: Annotated[UUID, Query()],
    query: Annotated[str, Query(min_length=1)],
) -> list[AddressSuggestionResponse]:
    settings = container.settings
    geocoder = DaDataGeocoder(
        api_key=settings.dadata_api_key,
        secret_key=settings.dadata_secret_key,
        base_url=settings.dadata_base_url,
        timeout_seconds=settings.dadata_timeout_seconds,
        retry_count=settings.dadata_retry_count,
    )
    async with container.session_factory() as session:
        suggestions = await SuggestAddressesUseCase(
            SqlAlchemyAddressRepository(session),
            geocoder,
        ).execute(SuggestAddressCommand(city_id=city_id, query=query))
    return [_suggestion_response(suggestion) for suggestion in suggestions]


def _suggestion_response(suggestion: AddressSuggestionDTO) -> AddressSuggestionResponse:
    return AddressSuggestionResponse(
        value=suggestion.value,
        unrestricted_value=suggestion.unrestricted_value,
        fias_id=suggestion.fias_id,
        latitude=suggestion.latitude,
        longitude=suggestion.longitude,
        quality=suggestion.quality,
    )
