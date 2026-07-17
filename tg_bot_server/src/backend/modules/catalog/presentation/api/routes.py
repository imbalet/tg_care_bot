from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.modules.catalog.infrastructure import SqlAlchemyCatalogQueryService

router = APIRouter(prefix="/api/catalog", tags=["catalog"])
legal_router = APIRouter(prefix="/api/legal-documents", tags=["legal-documents"])


class CityResponse(BaseModel):
    id: str
    name: str
    slug: str
    timezone: str
    is_active: bool


class LegalDocumentResponse(BaseModel):
    id: str
    document_type: str
    version: str
    content_url: str
    is_active: bool
    published_at: str


class ServiceResponse(BaseModel):
    id: str
    code: str
    name: str
    description: str
    price_type: str
    base_price: Decimal
    location_policy: str
    photo_policy: str
    schedule_policy: str
    allows_multiday: bool
    min_duration_minutes: int | None
    max_duration_minutes: int | None
    duration_step_minutes: int | None
    is_active: bool
    sort_order: int


class ServiceCategoryResponse(BaseModel):
    id: str
    code: str
    name: str
    care_object_type: str
    max_objects_per_order: int
    is_active: bool
    sort_order: int
    services: list[ServiceResponse]


class CatalogResponse(BaseModel):
    categories: list[ServiceCategoryResponse]


@router.get("/cities")
async def list_cities(
    container: Annotated[Container, Depends(get_container)],
    active_only: Annotated[bool, Query(alias="active")] = True,
) -> list[CityResponse]:
    async with container.session_factory() as session:
        cities = await SqlAlchemyCatalogQueryService(session).list_cities(
            active_only=active_only,
        )
    return [
        CityResponse(
            id=str(city.id),
            name=city.name,
            slug=city.slug,
            timezone=city.timezone,
            is_active=city.is_active,
        )
        for city in cities
    ]


@router.get("")
async def get_catalog(
    container: Annotated[Container, Depends(get_container)],
    active_only: Annotated[bool, Query(alias="active")] = True,
) -> CatalogResponse:
    async with container.session_factory() as session:
        catalog = await SqlAlchemyCatalogQueryService(session).get_catalog(
            active_only=active_only,
        )
    return CatalogResponse(
        categories=[
            ServiceCategoryResponse(
                id=str(category.id),
                code=category.code,
                name=category.name,
                care_object_type=category.care_object_type,
                max_objects_per_order=category.max_objects_per_order,
                is_active=category.is_active,
                sort_order=category.sort_order,
                services=[
                    ServiceResponse(
                        id=str(service.id),
                        code=service.code,
                        name=service.name,
                        description=service.description,
                        price_type=service.price_type,
                        base_price=service.base_price,
                        location_policy=service.location_policy,
                        photo_policy=service.photo_policy,
                        schedule_policy=service.schedule_policy,
                        allows_multiday=service.allows_multiday,
                        min_duration_minutes=service.min_duration_minutes,
                        max_duration_minutes=service.max_duration_minutes,
                        duration_step_minutes=service.duration_step_minutes,
                        is_active=service.is_active,
                        sort_order=service.sort_order,
                    )
                    for service in category.services
                ],
            )
            for category in catalog.categories
        ],
    )


@legal_router.get("")
async def list_legal_documents(
    container: Annotated[Container, Depends(get_container)],
    active_only: Annotated[bool, Query(alias="active")] = True,
) -> list[LegalDocumentResponse]:
    async with container.session_factory() as session:
        documents = await SqlAlchemyCatalogQueryService(session).list_legal_documents(
            active_only=active_only,
        )
    return [
        LegalDocumentResponse(
            id=str(document.id),
            document_type=document.document_type,
            version=document.version,
            content_url=document.content_url,
            is_active=document.is_active,
            published_at=document.published_at.isoformat(),
        )
        for document in documents
    ]
