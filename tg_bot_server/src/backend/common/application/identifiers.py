from uuid import UUID, uuid4


def new_uuid() -> UUID:
    return uuid4()


__all__ = ["new_uuid"]
