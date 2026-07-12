from collections.abc import Callable
from decimal import Decimal
from typing import Any

from backend.common.application import new_uuid, utc_now
from backend.modules.admin.infrastructure import AdminModel
from backend.modules.catalog.infrastructure import (
    BusinessSettingModel,
    CityModel,
    DistrictModel,
    LegalDocumentModel,
    ObjectCountMultiplierModel,
    ServiceCategoryModel,
    ServiceModel,
    ServiceOptionModel,
)
from backend.modules.customers.infrastructure import (
    CustomerModel,
    LegalAcceptanceModel,
)
from backend.modules.performers.infrastructure import (
    PerformerInvitationModel,
    PerformerModel,
)
from backend.modules.system_checks.infrastructure import SystemCheckRecordModel

ALL_MODELS = (
    SystemCheckRecordModel,
    AdminModel,
    CityModel,
    DistrictModel,
    ServiceCategoryModel,
    ServiceModel,
    ServiceOptionModel,
    ObjectCountMultiplierModel,
    BusinessSettingModel,
    LegalDocumentModel,
    CustomerModel,
    LegalAcceptanceModel,
    PerformerModel,
    PerformerInvitationModel,
)

UPDATED_AT_MODELS = (
    AdminModel,
    CityModel,
    DistrictModel,
    ServiceCategoryModel,
    ServiceModel,
    ServiceOptionModel,
    ObjectCountMultiplierModel,
    BusinessSettingModel,
    CustomerModel,
    PerformerModel,
    PerformerInvitationModel,
)


def test_all_models_have_uuid_primary_key_default() -> None:
    for model in ALL_MODELS:
        assert model.__table__.c.id.default is not None
        assert _same_callable(model.__table__.c.id.default.arg, new_uuid)


def test_all_models_have_created_at_default() -> None:
    for model in ALL_MODELS:
        assert model.__table__.c.created_at.default is not None
        assert _same_callable(model.__table__.c.created_at.default.arg, utc_now)


def test_updated_at_models_have_default_and_onupdate() -> None:
    for model in UPDATED_AT_MODELS:
        column = model.__table__.c.updated_at
        assert column.default is not None
        assert _same_callable(column.default.arg, utc_now)
        assert column.onupdate is not None
        assert _same_callable(column.onupdate.arg, utc_now)


def test_safe_catalog_defaults_are_declared() -> None:
    assert _default_arg(CityModel.__table__.c.is_active) is True
    assert _default_arg(DistrictModel.__table__.c.is_active) is True
    assert _default_arg(ServiceCategoryModel.__table__.c.is_active) is True
    assert _default_arg(ServiceCategoryModel.__table__.c.sort_order) == 0
    assert _default_arg(ServiceModel.__table__.c.base_price) == Decimal("0.00")
    assert _default_arg(ServiceModel.__table__.c.allows_multiday) is False
    assert _default_arg(ServiceModel.__table__.c.is_active) is True
    assert _default_arg(ServiceModel.__table__.c.sort_order) == 0
    assert _default_arg(ServiceOptionModel.__table__.c.is_required) is False
    assert _default_arg(ServiceOptionModel.__table__.c.is_active) is True
    assert _default_arg(ServiceOptionModel.__table__.c.sort_order) == 0
    assert _default_arg(ObjectCountMultiplierModel.__table__.c.is_active) is True
    assert _default_arg(LegalDocumentModel.__table__.c.is_active) is True
    assert LegalDocumentModel.__table__.c.published_at.default is not None
    assert _same_callable(
        LegalDocumentModel.__table__.c.published_at.default.arg,
        utc_now,
    )


def test_safe_status_and_service_defaults_are_declared() -> None:
    assert _default_arg(AdminModel.__table__.c.status) == "active"
    assert _default_arg(CustomerModel.__table__.c.status) == "active"
    assert _default_arg(PerformerModel.__table__.c.status) == "profile_pending"
    assert _default_arg(PerformerModel.__table__.c.is_accepting_orders) is False
    assert _default_arg(PerformerInvitationModel.__table__.c.status) == "pending"
    assert LegalAcceptanceModel.__table__.c.accepted_at.default is not None
    assert _same_callable(
        LegalAcceptanceModel.__table__.c.accepted_at.default.arg,
        utc_now,
    )


def _default_arg(column: Any) -> object:
    assert column.default is not None
    return column.default.arg


def _same_callable(candidate: object, expected: Callable[[], object]) -> bool:
    return (
        callable(candidate)
        and getattr(candidate, "__module__", None) == expected.__module__
        and getattr(candidate, "__name__", None) == expected.__name__
    )
