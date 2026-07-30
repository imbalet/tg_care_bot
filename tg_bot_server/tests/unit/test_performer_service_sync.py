from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.performers.application import (
    PerformerServiceSelection,
    PerformerServicesSyncResult,
    SyncPerformerServicesCommand,
    SyncPerformerServicesUseCase,
)


def _selection(service_id, *, max_objects: int = 2):
    return PerformerServiceSelection(
        service_id=service_id,
        admin_max_objects=max_objects,
        constraints={},
    )


def _result():
    return PerformerServicesSyncResult(
        services=(),
        added=(),
        revoked=(),
        updated=(),
    )


@pytest.mark.asyncio
async def test_sync_services_validates_all_selections_before_repository_write() -> None:
    first_id = uuid4()
    second_id = uuid4()
    repository = SimpleNamespace(
        get_service_order_limit=AsyncMock(side_effect=[3, None]),
        sync_services=AsyncMock(return_value=_result()),
    )

    with pytest.raises(NotFoundError, match="Active service not found"):
        await SyncPerformerServicesUseCase(repository).execute(
            SyncPerformerServicesCommand(
                performer_id=uuid4(),
                selections=(_selection(first_id), _selection(second_id)),
                approved_by_admin_id=uuid4(),
            ),
        )

    repository.sync_services.assert_not_awaited()


@pytest.mark.asyncio
async def test_sync_services_passes_full_selection_to_one_repository_operation() -> (
    None
):
    first_id = uuid4()
    second_id = uuid4()
    repository = SimpleNamespace(
        get_service_order_limit=AsyncMock(return_value=4),
        sync_services=AsyncMock(return_value=_result()),
    )
    command = SyncPerformerServicesCommand(
        performer_id=uuid4(),
        selections=(_selection(first_id), _selection(second_id, max_objects=4)),
        approved_by_admin_id=uuid4(),
    )

    await SyncPerformerServicesUseCase(repository).execute(command)

    repository.sync_services.assert_awaited_once_with(
        performer_id=command.performer_id,
        selections=command.selections,
        approved_by_admin_id=command.approved_by_admin_id,
    )


@pytest.mark.asyncio
async def test_sync_services_rejects_duplicate_selection() -> None:
    service_id = uuid4()
    repository = SimpleNamespace(get_service_order_limit=AsyncMock(return_value=3))

    with pytest.raises(ValidationError, match="Duplicate"):
        await SyncPerformerServicesUseCase(repository).execute(
            SyncPerformerServicesCommand(
                performer_id=uuid4(),
                selections=(_selection(service_id), _selection(service_id)),
                approved_by_admin_id=uuid4(),
            ),
        )

    repository.get_service_order_limit.assert_awaited_once_with(service_id)
