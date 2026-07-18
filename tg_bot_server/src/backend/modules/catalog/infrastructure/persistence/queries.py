from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.modules.catalog.application.dto import (
    CatalogDTO,
    CityDTO,
    LegalDocumentDTO,
    ServiceCategoryDTO,
    ServiceDTO,
    ServiceOptionDTO,
)
from backend.modules.catalog.application.queries import CatalogQueryService
from backend.modules.catalog.infrastructure.persistence.models import (
    CityModel,
    LegalDocumentModel,
    ServiceCategoryModel,
    ServiceModel,
)


class SqlAlchemyCatalogQueryService(CatalogQueryService):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_cities(self, *, active_only: bool) -> tuple[CityDTO, ...]:
        statement = select(CityModel).order_by(CityModel.name)
        if active_only:
            statement = statement.where(CityModel.is_active.is_(True))
        result = await self._session.execute(statement)
        return tuple(
            CityDTO(
                id=model.id,
                name=model.name,
                slug=model.slug,
                timezone=model.timezone,
                is_active=model.is_active,
            )
            for model in result.scalars()
        )

    async def list_legal_documents(
        self,
        *,
        active_only: bool,
    ) -> tuple[LegalDocumentDTO, ...]:
        statement = select(LegalDocumentModel).order_by(
            LegalDocumentModel.document_type,
            LegalDocumentModel.version,
        )
        if active_only:
            statement = statement.where(LegalDocumentModel.is_active.is_(True))
        result = await self._session.execute(statement)
        return tuple(
            LegalDocumentDTO(
                id=model.id,
                document_type=model.document_type,
                version=model.version,
                content_url=model.content_url,
                is_active=model.is_active,
                published_at=model.published_at,
            )
            for model in result.scalars()
        )

    async def get_catalog(self, *, active_only: bool) -> CatalogDTO:
        statement = (
            select(ServiceCategoryModel)
            .options(
                selectinload(ServiceCategoryModel.services).selectinload(
                    ServiceModel.options,
                ),
            )
            .order_by(ServiceCategoryModel.sort_order, ServiceCategoryModel.code)
        )
        if active_only:
            statement = statement.where(ServiceCategoryModel.is_active.is_(True))
        result = await self._session.execute(statement)
        categories = []
        for category in result.scalars():
            services = sorted(
                (
                    service
                    for service in category.services
                    if service.is_active or not active_only
                ),
                key=lambda service: (service.sort_order, service.code),
            )
            categories.append(
                ServiceCategoryDTO(
                    id=category.id,
                    code=category.code,
                    name=category.name,
                    care_object_type=category.care_object_type,
                    max_objects_per_order=category.max_objects_per_order,
                    is_active=category.is_active,
                    sort_order=category.sort_order,
                    services=tuple(
                        ServiceDTO(
                            id=service.id,
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
                            options=tuple(
                                ServiceOptionDTO(
                                    id=option.id,
                                    code=option.code,
                                    name=option.name,
                                    value_type=option.value_type,
                                    is_required=option.is_required,
                                    sort_order=option.sort_order,
                                )
                                for option in sorted(
                                    (
                                        option
                                        for option in service.options
                                        if option.is_active or not active_only
                                    ),
                                    key=lambda option: (
                                        option.sort_order,
                                        option.code,
                                    ),
                                )
                            ),
                        )
                        for service in services
                    ),
                ),
            )
        return CatalogDTO(categories=tuple(categories))
