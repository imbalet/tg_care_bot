from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.addresses.application import (
    SuggestAddressCommand,
)

from .mappers import suggestion_response
from .schemas import AddressSuggestionResponse

router = APIRouter(
    prefix="/api/geocoding",
    tags=["geocoding"],
    dependencies=[Depends(require_service_key)],
)


@router.get("/address-suggestions")
async def address_suggestions(
    container: Annotated[Container, Depends(get_container)],
    city_id: Annotated[UUID, Query()],
    query: Annotated[str, Query(min_length=1)],
) -> list[AddressSuggestionResponse]:
    suggestions = await container.geo.suggest_addresses(
        SuggestAddressCommand(city_id=city_id, query=query),
    )
    return [suggestion_response(suggestion) for suggestion in suggestions]
