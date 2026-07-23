from decimal import Decimal
from uuid import uuid4

import pytest

from backend.modules.availability.application.dto import SuitablePerformerDTO
from backend.modules.availability.infrastructure.persistence.repositories import (
    _sort_suitable_performers,
)


def _performer(
    name: str,
    distance: Decimal | None,
) -> SuitablePerformerDTO:
    return SuitablePerformerDTO(
        performer_id=uuid4(),
        full_name=name,
        service_id=uuid4(),
        service_code="care",
        service_name="Care",
        performer_max_objects=1,
        distance_km=distance,
        current_address_id=None,
    )


@pytest.mark.unit
def test_suitable_performers_are_sorted_by_distance_with_unknown_last() -> None:
    unknown = _performer("A", None)
    far = _performer("B", Decimal("10"))
    near = _performer("C", Decimal("1"))

    assert _sort_suitable_performers([unknown, far, near]) == [near, far, unknown]
