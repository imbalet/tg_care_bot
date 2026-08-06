from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from backend.common.domain import ConflictError
from backend.modules.orders.infrastructure.persistence.matching_repositories import (
    SqlAlchemyMatchingRepository,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_pool_response_rejects_performer_without_matching_service() -> None:
    order = SimpleNamespace(
        id=uuid4(),
        matching_mode="pool",
        status="searching",
        matching_deadline_at=datetime.now(UTC) + timedelta(hours=1),
        start_at=datetime.now(UTC) + timedelta(days=1),
        end_at=datetime.now(UTC) + timedelta(days=1, hours=1),
    )
    performer = SimpleNamespace(
        id=uuid4(),
        status="active",
        is_accepting_orders=True,
        current_address_id=uuid4(),
    )
    session = AsyncMock()
    repository = SqlAlchemyMatchingRepository(session)
    repository._lock_order = AsyncMock(return_value=order)
    repository._lock_performer = AsyncMock(return_value=performer)
    repository._performer_can_receive_order = AsyncMock(return_value=False)
    repository._ensure_no_historical_match = AsyncMock()

    with pytest.raises(ConflictError, match="suitable"):
        await repository.create_pool_response(
            order_id=order.id,
            performer_id=performer.id,
        )

    repository._ensure_no_historical_match.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_available_orders_query_scopes_to_performer_services() -> None:
    performer = SimpleNamespace(
        status="active",
        is_accepting_orders=True,
        current_address_id=uuid4(),
    )
    result = SimpleNamespace(scalars=lambda: ())
    session = AsyncMock()
    session.get.return_value = performer
    session.scalar.side_effect = (uuid4(), uuid4(), None)
    session.execute.return_value = result
    repository = SqlAlchemyMatchingRepository(session)

    await repository.list_available_pool_orders(
        performer_id=uuid4(),
        limit=20,
    )

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "performer_services.service_id = orders.service_id" in sql
