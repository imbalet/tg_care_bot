from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class HelpView:
    include_main_menu: bool


@dataclass(frozen=True, slots=True)
class ServiceOptionView:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class ServiceView:
    id: str
    name: str
    category_code: str
    category_name: str
    care_object_type: str
    max_objects_per_order: int
    price_type: str
    allows_multiday: bool
    min_duration_minutes: int | None
    max_duration_minutes: int | None
    duration_step_minutes: int | None
    location_policy: str
    photo_policy: str
    options: tuple[ServiceOptionView, ...]


@dataclass(frozen=True, slots=True)
class ServicesView:
    services: tuple[ServiceView, ...]


@dataclass(frozen=True, slots=True)
class ObjectTypeView:
    object_type: str


@dataclass(frozen=True, slots=True)
class ObjectNameView:
    object_type_label: str


@dataclass(frozen=True, slots=True)
class SelectableObjectView:
    id: str
    display_name: str


@dataclass(frozen=True, slots=True)
class ObjectsStepView:
    max_count: int
    selected_count: int
    selected_ids: tuple[str, ...]
    items: tuple[SelectableObjectView, ...]
    can_finish: bool


@dataclass(frozen=True, slots=True)
class SelectableOptionView:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class OptionsStepView:
    selected_count: int
    selected_ids: tuple[str, ...]
    items: tuple[SelectableOptionView, ...]
    can_finish: bool


@dataclass(frozen=True, slots=True)
class DateLabelView:
    date_label: str


@dataclass(frozen=True, slots=True)
class DurationView:
    unit: str


@dataclass(frozen=True, slots=True)
class OrderSummaryView:
    service_name: str
    duration_minutes: int
    objects_count: int
    service_amount: Decimal
    platform_fee_amount: Decimal
    total_amount: Decimal
    performers_count: int
    duration_unit: str = "minutes"
    start_at: datetime | None = None
    end_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PerformerView:
    performer_id: UUID
    full_name: str
    service_name: str
    distance_km: Decimal | None


@dataclass(frozen=True, slots=True)
class SelectedOrderResponseView:
    order_status: str
    id: UUID
    payment_confirmation_url: str | None


@dataclass(frozen=True, slots=True)
class PaymentStatusView:
    id: UUID
    order_status: str
    payment_status: str | None
    confirmation_url: str | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class AddressCardView:
    id: str
    address_text: str
    entrance: str
    floor: str
    apartment: str
    comment: str


@dataclass(frozen=True, slots=True)
class AddressDeleteView:
    id: str


@dataclass(frozen=True, slots=True)
class AddressListView:
    count: int
    items: tuple[AddressListItemView, ...]


@dataclass(frozen=True, slots=True)
class AddressListItemView:
    id: UUID
    address_text: str


@dataclass(frozen=True, slots=True)
class AddressExtraView:
    field_name: str


@dataclass(frozen=True, slots=True)
class CareObjectCardView:
    id: str
    object_type: str
    display_name: str
    age_group: str
    species: str | None
    breed: str | None
    pet_size: str | None
    mobility_assistance_required: bool | None
    routine_notes: str | None
    behavior_notes: str | None


@dataclass(frozen=True, slots=True)
class CareObjectListView:
    category: str
    object_type: str
    count: int
    items: tuple[CareObjectListItemView, ...]


@dataclass(frozen=True, slots=True)
class CareObjectListItemView:
    id: UUID
    display_name: str


@dataclass(frozen=True, slots=True)
class CareObjectDeleteView:
    id: str


@dataclass(frozen=True, slots=True)
class CareObjectBlockedView:
    index: int


@dataclass(frozen=True, slots=True)
class MyOrderCardView:
    id: UUID
    service_name: str
    matching_mode: str | None
    status: str
    start_at: datetime
    end_at: datetime
    objects_count: int
    total_amount: Decimal
    payment_deadline_at: datetime | None
    matching_deadline_at: datetime
    payment_status: str | None
    payment_confirmation_url: str | None
    payment_expires_at: datetime | None
    group: str
    page: int


@dataclass(frozen=True, slots=True)
class MyOrdersPageView:
    items: tuple[OrderListItemView, ...]
    page: int
    total_pages: int
    total_items: int
    group: str
    category_code: str | None
    active_category_code: str | None


@dataclass(frozen=True, slots=True)
class OrderListItemView:
    id: UUID
    category_code: str
    service_name: str
    matching_mode: str | None
    status: str
    start_at: datetime
    end_at: datetime
    objects_count: int
    total_amount: Decimal
    payment_deadline_at: datetime | None
    matching_deadline_at: datetime
