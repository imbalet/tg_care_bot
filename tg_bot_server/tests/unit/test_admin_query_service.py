from decimal import Decimal
from uuid import uuid4

from backend.modules.admin.infrastructure.persistence.query_service import (
    _performer_service_dict,
)
from backend.modules.catalog.infrastructure.persistence.models import ServiceModel
from backend.modules.performers.infrastructure.persistence.models import (
    PerformerServiceModel,
)


def test_performer_service_admin_row_contains_catalog_identity_and_limits() -> None:
    service = ServiceModel(
        category_id=uuid4(),
        code="pet_care",
        name="Уход за питомцем",
        description="Уход",
        price_type="fixed",
        base_price=Decimal("100.00"),
        location_policy="customer_home",
        photo_policy="none",
        schedule_policy="working_hours",
    )
    performer_service = PerformerServiceModel(
        performer_id=uuid4(),
        service_id=service.id,
        is_approved=True,
        is_enabled=False,
        admin_max_objects=3,
        performer_max_objects=2,
        constraints={"accepted_age_groups": ["school_age"]},
    )
    performer_service.service = service

    row = _performer_service_dict(performer_service)

    assert row["service_code"] == "pet_care"
    assert row["service_name"] == "Уход за питомцем"
    assert row["service_price_type"] == "fixed"
    assert row["is_approved"] is True
    assert row["is_enabled"] is False
    assert row["admin_max_objects"] == 3
    assert row["performer_max_objects"] == 2
