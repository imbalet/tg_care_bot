from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import Clock, SystemClock, new_uuid
from backend.modules.catalog.infrastructure.persistence.models import (
    BusinessSettingModel,
    CityModel,
    DistrictModel,
    LegalDocumentModel,
    ObjectCountMultiplierModel,
    ServiceCategoryModel,
    ServiceModel,
    ServiceOptionModel,
)


@dataclass(frozen=True)
class _CategorySeed:
    code: str
    name: str
    care_object_type: str
    max_objects_per_order: int
    sort_order: int


@dataclass(frozen=True)
class _ServiceSeed:
    category_code: str
    code: str
    name: str
    price_type: str
    location_policy: str
    photo_policy: str
    schedule_policy: str
    allows_multiday: bool
    sort_order: int


class SeedMvpCatalogUseCase:
    def __init__(self, session: AsyncSession, clock: Clock | None = None) -> None:
        self._session = session
        self._clock = clock or SystemClock()

    async def execute(self) -> None:
        now = self._clock.now()
        await self._seed_cities(now)
        await self._seed_districts(now)
        categories = await self._seed_categories(now)
        services = await self._seed_services(categories, now)
        await self._seed_options(services, now)
        await self._seed_multipliers(categories, now)
        await self._seed_settings(now)
        await self._seed_legal_documents(now)

    async def _seed_cities(self, now: datetime) -> None:
        if await self._get_by(CityModel, CityModel.slug, "moscow") is None:
            self._session.add(
                CityModel(
                    id=new_uuid(),
                    name="Москва",
                    slug="moscow",
                    timezone="Europe/Moscow",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            )

    async def _seed_districts(self, now: datetime) -> None:
        city = cast(
            CityModel | None, await self._get_by(CityModel, CityModel.slug, "moscow")
        )
        if city is None:
            return
        for name in ("Центр", "Север", "Юг", "Запад", "Восток"):
            exists = await self._session.execute(
                select(DistrictModel).where(
                    DistrictModel.city_id == city.id,
                    DistrictModel.name == name,
                ),
            )
            if exists.scalar_one_or_none() is not None:
                continue
            self._session.add(
                DistrictModel(
                    id=new_uuid(),
                    city_id=city.id,
                    name=name,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            )

    async def _seed_categories(
        self,
        now: datetime,
    ) -> dict[str, ServiceCategoryModel]:
        seeds = (
            _CategorySeed("nanny", "Няня", "child", 2, 10),
            _CategorySeed("caregiver", "Сиделка", "ward", 1, 20),
            _CategorySeed("petsitter", "Петситтер", "pet", 3, 30),
        )
        categories: dict[str, ServiceCategoryModel] = {}
        for seed in seeds:
            model = cast(
                ServiceCategoryModel | None,
                await self._get_by(
                    ServiceCategoryModel,
                    ServiceCategoryModel.code,
                    seed.code,
                ),
            )
            if model is None:
                model = ServiceCategoryModel(
                    id=new_uuid(),
                    code=seed.code,
                    name=seed.name,
                    care_object_type=seed.care_object_type,
                    max_objects_per_order=seed.max_objects_per_order,
                    is_active=True,
                    sort_order=seed.sort_order,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(model)
                await self._session.flush()
            categories[seed.code] = model
        return categories

    async def _seed_services(
        self,
        categories: dict[str, ServiceCategoryModel],
        now: datetime,
    ) -> dict[str, ServiceModel]:
        seeds = (
            _ServiceSeed(
                "nanny",
                "nanny_care",
                "Присмотр за ребенком",
                "hourly",
                "customer_address",
                "requires_customer_consent",
                "working_hours",
                False,
                10,
            ),
            _ServiceSeed(
                "caregiver",
                "caregiver_household_help",
                "Присмотр и бытовая помощь",
                "hourly",
                "customer_address",
                "requires_customer_consent",
                "working_hours",
                False,
                20,
            ),
            _ServiceSeed(
                "petsitter",
                "pet_walk",
                "Выгул",
                "hourly",
                "customer_address",
                "required",
                "working_hours",
                False,
                30,
            ),
            _ServiceSeed(
                "petsitter",
                "pet_visit_feeding",
                "Визит и кормление",
                "fixed",
                "customer_address",
                "required",
                "working_hours",
                False,
                40,
            ),
            _ServiceSeed(
                "petsitter",
                "pet_sitting",
                "Зооняня",
                "hourly",
                "customer_address",
                "required",
                "working_hours",
                False,
                50,
            ),
            _ServiceSeed(
                "petsitter",
                "pet_boarding",
                "Передержка",
                "started_24h",
                "performer_address",
                "required",
                "calendar_only",
                True,
                60,
            ),
        )
        services: dict[str, ServiceModel] = {}
        for seed in seeds:
            model = cast(
                ServiceModel | None,
                await self._get_by(ServiceModel, ServiceModel.code, seed.code),
            )
            if model is None:
                model = ServiceModel(
                    id=new_uuid(),
                    category_id=categories[seed.category_code].id,
                    code=seed.code,
                    name=seed.name,
                    description=seed.name,
                    price_type=seed.price_type,
                    base_price=Decimal("0.00"),
                    location_policy=seed.location_policy,
                    photo_policy=seed.photo_policy,
                    schedule_policy=seed.schedule_policy,
                    allows_multiday=seed.allows_multiday,
                    min_duration_minutes=None,
                    max_duration_minutes=None,
                    duration_step_minutes=60,
                    is_active=True,
                    sort_order=seed.sort_order,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(model)
                await self._session.flush()
            services[seed.code] = model
        return services

    async def _seed_options(
        self,
        services: dict[str, ServiceModel],
        now: datetime,
    ) -> None:
        options = {
            "caregiver_household_help": (
                ("household_help", "Помощь по дому"),
                ("mobility_help", "Помощь при передвижении"),
            ),
            "pet_visit_feeding": (("feeding", "Кормление"),),
            "pet_sitting": (
                ("feeding", "Кормление"),
                ("walk", "Прогулка"),
                ("play", "Игры"),
                ("sleep", "Сон"),
            ),
            "pet_boarding": (
                ("feeding", "Кормление"),
                ("walk", "Прогулка"),
                ("play", "Игры"),
                ("sleep", "Сон"),
            ),
        }
        for service_code, service_options in options.items():
            service = services[service_code]
            for index, (code, name) in enumerate(service_options, start=1):
                exists = await self._session.execute(
                    select(ServiceOptionModel).where(
                        ServiceOptionModel.service_id == service.id,
                        ServiceOptionModel.code == code,
                    ),
                )
                if exists.scalar_one_or_none() is not None:
                    continue
                self._session.add(
                    ServiceOptionModel(
                        id=new_uuid(),
                        service_id=service.id,
                        code=code,
                        name=name,
                        value_type="boolean",
                        is_required=False,
                        is_active=True,
                        sort_order=index * 10,
                        created_at=now,
                        updated_at=now,
                    ),
                )

    async def _seed_multipliers(
        self,
        categories: dict[str, ServiceCategoryModel],
        now: datetime,
    ) -> None:
        seeds = {
            "nanny": ((1, "1.00"), (2, "1.40")),
            "caregiver": ((1, "1.00"),),
            "petsitter": ((1, "1.00"), (2, "1.30"), (3, "1.50")),
        }
        for category_code, rows in seeds.items():
            category = categories[category_code]
            for count, multiplier in rows:
                exists = await self._session.execute(
                    select(ObjectCountMultiplierModel).where(
                        ObjectCountMultiplierModel.category_id == category.id,
                        ObjectCountMultiplierModel.objects_count == count,
                    ),
                )
                if exists.scalar_one_or_none() is not None:
                    continue
                self._session.add(
                    ObjectCountMultiplierModel(
                        id=new_uuid(),
                        category_id=category.id,
                        objects_count=count,
                        multiplier=Decimal(multiplier),
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    ),
                )

    async def _seed_settings(self, now: datetime) -> None:
        settings: tuple[tuple[str, object, str], ...] = (
            ("minimum_order_lead_minutes", 360, "number"),
            ("matching_close_before_start_minutes", 210, "number"),
            ("direct_response_window_minutes", 180, "number"),
            ("pool_response_window_minutes", 180, "number"),
            ("payment_window_minutes", 30, "number"),
            ("payment_close_before_start_minutes", 180, "number"),
            ("start_button_before_minutes", 15, "number"),
            ("auto_waiting_report_after_end_minutes", 15, "number"),
            ("report_reminder_first_minutes", 30, "number"),
            ("report_reminder_second_minutes", 60, "number"),
            ("report_admin_escalation_minutes", 120, "number"),
            ("report_confirmation_window_minutes", 1440, "number"),
            ("start_not_confirmed_escalation_minutes", 15, "number"),
            ("full_refund_before_start_minutes", 720, "number"),
            ("partial_refund_before_start_minutes", 360, "number"),
            ("refund_policy_version", "v1", "string"),
            ("partial_refund_percent", None, "number"),
            ("platform_fee_percent", 5, "number"),
            ("max_active_pool_responses", 5, "number"),
            ("notification_retention_days", 30, "number"),
            ("complaint_retention_days", 30, "number"),
            ("payment_provider_hold_limit_minutes", None, "number"),
        )
        for key, value, value_type in settings:
            existing = await self._get_by(
                BusinessSettingModel,
                BusinessSettingModel.key,
                key,
            )
            if existing is not None:
                continue
            self._session.add(
                BusinessSettingModel(
                    id=new_uuid(),
                    key=key,
                    value=value,
                    value_type=value_type,
                    description=f"MVP setting {key}",
                    updated_by_admin_id=None,
                    created_at=now,
                    updated_at=now,
                ),
            )

    async def _seed_legal_documents(self, now: datetime) -> None:
        for document_type in (
            "personal_data_policy",
            "personal_data_consent",
            "user_agreement",
            "representative_confirmation",
        ):
            exists = await self._session.execute(
                select(LegalDocumentModel).where(
                    LegalDocumentModel.document_type == document_type,
                    LegalDocumentModel.version == "v1",
                ),
            )
            if exists.scalar_one_or_none() is not None:
                continue
            self._session.add(
                LegalDocumentModel(
                    id=new_uuid(),
                    document_type=document_type,
                    version="v1",
                    content_url=f"https://example.invalid/legal/{document_type}/v1",
                    is_active=True,
                    published_at=now,
                    created_at=now,
                ),
            )

    async def _get_by(
        self,
        model_type: type[Any],
        column: Any,
        value: str,
    ) -> Any | None:
        result = await self._session.execute(select(model_type).where(column == value))
        return result.scalar_one_or_none()


__all__ = ["SeedMvpCatalogUseCase"]
