from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Any, Self

from backend.common.application import StoredObject
from backend.modules.geo.application import (
    AddressSuggestionDTO,
    NormalizedAddressDTO,
)
from backend.modules.payments.application import (
    PaymentGatewayConfirmCommand,
    PaymentGatewayConfirmResult,
    PaymentGatewayInitCommand,
    PaymentGatewayInitResult,
    PaymentGatewayRefundCommand,
    PaymentGatewayRefundResult,
    PaymentGatewayStateCommand,
    PaymentGatewayStateResult,
)


class FakeClock:
    def __init__(self, now: datetime | None = None) -> None:
        self.current = now or datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc, traceback
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeRepository:
    def __init__(self, records: dict[str, Any] | None = None) -> None:
        self.records = records or {}

    async def get(self, key: str) -> Any:
        return self.records.get(key)

    async def add(self, key: str, value: Any) -> Any:
        self.records[key] = value
        return value


class FakeObjectStorage:
    def __init__(self, bucket: str = "test-bucket") -> None:
        self.bucket = bucket
        self.objects: dict[str, tuple[bytes, str]] = {}

    async def get(self, storage_key: str) -> bytes:
        return self.objects[storage_key][0]

    async def put(
        self,
        storage_key: str,
        content: bytes,
        content_type: str,
    ) -> StoredObject:
        self.objects[storage_key] = (content, content_type)
        return StoredObject(
            bucket=self.bucket,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=len(content),
        )

    async def delete(self, storage_key: str) -> None:
        self.objects.pop(storage_key, None)

    async def create_download_url(self, storage_key: str) -> str:
        if storage_key not in self.objects:
            raise KeyError(storage_key)
        return f"https://storage.test/{self.bucket}/{storage_key}"


class FakeGeocoder:
    def __init__(self, suggestions: tuple[AddressSuggestionDTO, ...]) -> None:
        self.suggestions = suggestions

    async def suggest(
        self,
        *,
        query: str,
        city: str | None = None,
        limit: int = 5,
    ) -> tuple[AddressSuggestionDTO, ...]:
        del city
        if not query.strip():
            return ()
        return self.suggestions[:limit]

    async def normalize(self, *, unrestricted_value: str) -> NormalizedAddressDTO:
        for suggestion in self.suggestions:
            if suggestion.unrestricted_value == unrestricted_value:
                return NormalizedAddressDTO(
                    address_text=suggestion.value,
                    fias_id=suggestion.fias_id,
                    latitude=suggestion.latitude,
                    longitude=suggestion.longitude,
                    provider="fake",
                    quality=suggestion.quality,
                )
        raise LookupError(unrestricted_value)


class FakePaymentGateway:
    def __init__(self) -> None:
        self.created: list[PaymentGatewayInitCommand] = []
        self.confirmed: list[PaymentGatewayConfirmCommand] = []
        self.refunds: list[PaymentGatewayRefundCommand] = []
        self.states: list[PaymentGatewayStateCommand] = []

    async def create_payment(
        self,
        command: PaymentGatewayInitCommand,
    ) -> PaymentGatewayInitResult:
        self.created.append(command)
        return PaymentGatewayInitResult(
            provider_payment_id=f"provider-{command.payment_id}",
            provider_deal_id=None,
            confirmation_url=f"https://pay.test/{command.idempotency_key}",
        )

    async def create_refund(
        self,
        command: PaymentGatewayRefundCommand,
    ) -> PaymentGatewayRefundResult:
        self.refunds.append(command)
        return PaymentGatewayRefundResult(
            provider_refund_id=f"refund-{command.refund_id}",
        )

    async def confirm_payment(
        self,
        command: PaymentGatewayConfirmCommand,
    ) -> PaymentGatewayConfirmResult:
        self.confirmed.append(command)
        return PaymentGatewayConfirmResult(
            provider_payment_id=command.provider_payment_id,
            status="CONFIRMED",
        )

    async def get_payment_state(
        self,
        command: PaymentGatewayStateCommand,
    ) -> PaymentGatewayStateResult:
        self.states.append(command)
        return PaymentGatewayStateResult(
            provider_payment_id=command.provider_payment_id,
            status="CONFIRMED",
            amount=Decimal("0"),
            paid_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


class FakeExternalTransport:
    """Small deterministic transport for adapter contract tests."""

    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = response or {"Success": True}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    async def request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append((method, url, payload))
        return self.response
