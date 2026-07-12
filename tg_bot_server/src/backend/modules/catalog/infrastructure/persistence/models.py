from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.application import utc_now
from backend.common.infrastructure.database import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UuidPrimaryKeyMixin,
)


class CityModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cities"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class DistrictModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "districts"

    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class ServiceCategoryModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_categories"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    care_object_type: Mapped[str] = mapped_column(Text, nullable=False)
    max_objects_per_order: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    services: Mapped[list[ServiceModel]] = relationship(
        back_populates="category",
        lazy="selectin",
    )


class ServiceModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "services"

    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_categories.id"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price_type: Mapped[str] = mapped_column(Text, nullable=False)
    base_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    location_policy: Mapped[str] = mapped_column(Text, nullable=False)
    photo_policy: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_policy: Mapped[str] = mapped_column(Text, nullable=False)
    allows_multiday: Mapped[bool] = mapped_column(nullable=False, default=False)
    min_duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    max_duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    duration_step_minutes: Mapped[int | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
    category: Mapped[ServiceCategoryModel] = relationship(back_populates="services")


class ServiceOptionModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_options"

    service_id: Mapped[UUID] = mapped_column(ForeignKey("services.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(Text, nullable=False)
    is_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)


class ObjectCountMultiplierModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "object_count_multipliers"

    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("service_categories.id"),
        nullable=False,
    )
    objects_count: Mapped[int] = mapped_column(nullable=False)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class BusinessSettingModel(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "business_settings"

    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    value_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("admins.id"),
        nullable=True,
    )


class LegalDocumentModel(UuidPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "legal_documents"

    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    content_url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


__all__ = [
    "BusinessSettingModel",
    "CityModel",
    "DistrictModel",
    "LegalDocumentModel",
    "ObjectCountMultiplierModel",
    "ServiceCategoryModel",
    "ServiceModel",
    "ServiceOptionModel",
]
