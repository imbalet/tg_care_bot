from typing import Protocol
from uuid import UUID

from .dto import CareObjectDTO, CreateCareObjectCommand, UpdateCareObjectCommand


class CareObjectRepository(Protocol):
    async def get(self, care_object_id: UUID) -> CareObjectDTO | None:
        pass

    async def add(self, command: CreateCareObjectCommand) -> CareObjectDTO:
        pass

    async def update(self, command: UpdateCareObjectCommand) -> CareObjectDTO:
        pass

    async def soft_delete(self, care_object_id: UUID) -> None:
        pass

    async def list_for_customer(
        self,
        customer_id: UUID,
        *,
        active_only: bool = True,
        object_type: str | None = None,
    ) -> tuple[CareObjectDTO, ...]:
        pass


class CareObjectQueryService(Protocol):
    async def list_for_customer(
        self,
        customer_id: UUID,
        *,
        active_only: bool = True,
        object_type: str | None = None,
    ) -> tuple[CareObjectDTO, ...]:
        pass


__all__ = ["CareObjectQueryService", "CareObjectRepository"]
