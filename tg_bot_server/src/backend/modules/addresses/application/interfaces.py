from typing import Protocol
from uuid import UUID

from .dto import AddressDTO, CreateAddressCommand


class AddressRepository(Protocol):
    async def get(self, address_id: UUID) -> AddressDTO | None:
        pass

    async def add(self, command: CreateAddressCommand) -> AddressDTO:
        pass

    async def soft_delete(self, address_id: UUID) -> None:
        pass


class AddressQueryService(Protocol):
    async def list_for_customer(
        self,
        customer_id: UUID,
        *,
        active_only: bool = True,
    ) -> tuple[AddressDTO, ...]:
        pass

    async def list_for_performer(
        self,
        performer_id: UUID,
        *,
        active_only: bool = True,
    ) -> tuple[AddressDTO, ...]:
        pass


__all__ = ["AddressQueryService", "AddressRepository"]
