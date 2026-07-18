from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container

from .mappers import catalog_response, city_response, legal_document_response
from .schemas import CatalogResponse, CityResponse, LegalDocumentResponse

router = APIRouter(prefix="/api/catalog", tags=["catalog"])
legal_router = APIRouter(prefix="/api/legal-documents", tags=["legal-documents"])


@router.get("/cities")
async def list_cities(
    container: Annotated[Container, Depends(get_container)],
    active_only: Annotated[bool, Query(alias="active")] = True,
) -> list[CityResponse]:
    cities = await container.services().list_cities(active_only=active_only)
    return [city_response(city) for city in cities]


@router.get("")
async def get_catalog(
    container: Annotated[Container, Depends(get_container)],
    active_only: Annotated[bool, Query(alias="active")] = True,
) -> CatalogResponse:
    catalog = await container.services().get_catalog(active_only=active_only)
    return catalog_response(catalog)


@legal_router.get("")
async def list_legal_documents(
    container: Annotated[Container, Depends(get_container)],
    active_only: Annotated[bool, Query(alias="active")] = True,
) -> list[LegalDocumentResponse]:
    documents = await container.services().list_legal_documents(
        active_only=active_only,
    )
    return [legal_document_response(document) for document in documents]
