from decimal import Decimal

from pydantic import BaseModel


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


class ServiceOptionResponse(BaseModel):
    id: str
    code: str
    name: str
    value_type: str
    is_required: bool
    sort_order: int


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
    options: list[ServiceOptionResponse]


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
