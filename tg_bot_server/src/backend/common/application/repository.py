from typing import Protocol, TypeVar

EntityT = TypeVar("EntityT")
IdT_contra = TypeVar("IdT_contra", contravariant=True)


class Repository(Protocol[EntityT, IdT_contra]):
    async def get(self, entity_id: IdT_contra) -> EntityT | None:
        pass

    async def get_for_update(self, entity_id: IdT_contra) -> EntityT | None:
        pass

    async def add(self, entity: EntityT) -> None:
        pass

    async def delete(self, entity: EntityT) -> None:
        pass
