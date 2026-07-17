from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class CustomerDTO:
    id: UUID
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: UUID
    status: str
