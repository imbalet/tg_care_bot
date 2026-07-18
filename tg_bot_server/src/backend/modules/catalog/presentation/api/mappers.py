from backend.modules.catalog.application import (
    CatalogDTO,
    CityDTO,
    LegalDocumentDTO,
    ServiceCategoryDTO,
    ServiceDTO,
)

from .schemas import (
    CatalogResponse,
    CityResponse,
    LegalDocumentResponse,
    ServiceCategoryResponse,
    ServiceResponse,
)


def city_response(city: CityDTO) -> CityResponse:
    return CityResponse(
        id=str(city.id),
        name=city.name,
        slug=city.slug,
        timezone=city.timezone,
        is_active=city.is_active,
    )


def service_response(service: ServiceDTO) -> ServiceResponse:
    return ServiceResponse(
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


def service_category_response(
    category: ServiceCategoryDTO,
) -> ServiceCategoryResponse:
    return ServiceCategoryResponse(
        id=str(category.id),
        code=category.code,
        name=category.name,
        care_object_type=category.care_object_type,
        max_objects_per_order=category.max_objects_per_order,
        is_active=category.is_active,
        sort_order=category.sort_order,
        services=[service_response(service) for service in category.services],
    )


def catalog_response(catalog: CatalogDTO) -> CatalogResponse:
    return CatalogResponse(
        categories=[
            service_category_response(category) for category in catalog.categories
        ],
    )


def legal_document_response(document: LegalDocumentDTO) -> LegalDocumentResponse:
    return LegalDocumentResponse(
        id=str(document.id),
        document_type=document.document_type,
        version=document.version,
        content_url=document.content_url,
        is_active=document.is_active,
        published_at=document.published_at.isoformat(),
    )
