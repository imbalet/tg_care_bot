from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.modules.geo.application import AddressSuggestionDTO
from backend.modules.payments.application import PaymentGatewayInitCommand
from tests.support.fakes import (
    FakeClock,
    FakeExternalTransport,
    FakeGeocoder,
    FakeObjectStorage,
    FakePaymentGateway,
    FakeRepository,
    FakeUnitOfWork,
)


@pytest.mark.unit
async def test_test_doubles_implement_external_ports() -> None:
    clock = FakeClock(datetime(2026, 2, 1, tzinfo=UTC))
    storage = FakeObjectStorage()
    gateway = FakePaymentGateway()
    geocoder = FakeGeocoder(
        (
            AddressSuggestionDTO(
                value="Moscow, Test street, 1",
                unrestricted_value="Moscow, Test street, 1",
                fias_id=None,
                latitude=None,
                longitude=None,
                quality="high",
            ),
        ),
    )
    transport = FakeExternalTransport()
    repository = FakeRepository()
    unit_of_work = FakeUnitOfWork()

    key = "files/test.png"
    stored = await storage.put(key, b"png", "image/png")
    command = PaymentGatewayInitCommand(
        payment_id=uuid4(),
        order_id=uuid4(),
        idempotency_key="payment:test",
        amount=Decimal("10.00"),
        description="Test payment",
        customer_phone="+79990000000",
        customer_name="Test Customer",
    )
    payment = await gateway.create_payment(command)
    suggestions = await geocoder.suggest(query="Test")
    response = await transport.request("POST", "https://external.test", {})
    await repository.add("key", "value")
    async with unit_of_work:
        assert await repository.get("key") == "value"
        await unit_of_work.commit()

    assert clock.now() == datetime(2026, 2, 1, tzinfo=UTC)
    assert stored.size_bytes == 3
    assert await storage.get(key) == b"png"
    assert payment.provider_payment_id.startswith("provider-")
    assert suggestions[0].quality == "high"
    assert response == {"Success": True}
    assert len(gateway.created) == 1
    assert unit_of_work.committed
