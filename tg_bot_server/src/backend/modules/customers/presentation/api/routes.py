from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.bootstrap.container import Container
from backend.bootstrap.dependencies import get_container
from backend.common.presentation import require_service_key
from backend.modules.customers.application import (
    GetCustomerProfileUseCase,
    RegisterCustomerCommand,
    RegisterCustomerUseCase,
    UpdateCustomerUsernameCommand,
    UpdateCustomerUsernameUseCase,
)
from backend.modules.customers.application.dto import CustomerDTO
from backend.modules.customers.infrastructure import SqlAlchemyCustomerRepository

router = APIRouter(
    prefix="/api/customers",
    tags=["customers"],
    dependencies=[Depends(require_service_key)],
)


class RegisterCustomerRequest(BaseModel):
    telegram_id: int
    full_name: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    city_id: UUID
    contact_method: str
    telegram_username: str | None = None
    accepted_legal_document_ids: list[UUID]


class UpdateTelegramUsernameRequest(BaseModel):
    telegram_username: str | None = None


class CustomerResponse(BaseModel):
    id: str
    telegram_id: int
    full_name: str
    phone: str
    telegram_username: str | None
    contact_method: str
    city_id: str
    status: str


def _to_response(customer: CustomerDTO) -> CustomerResponse:
    return CustomerResponse(
        id=str(customer.id),
        telegram_id=customer.telegram_id,
        full_name=customer.full_name,
        phone=customer.phone,
        telegram_username=customer.telegram_username,
        contact_method=customer.contact_method,
        city_id=str(customer.city_id),
        status=customer.status,
    )


@router.get("/by-telegram/{telegram_id}/profile")
async def get_profile(
    telegram_id: int,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    async with container.session_factory() as session:
        customer = await GetCustomerProfileUseCase(
            SqlAlchemyCustomerRepository(session),
        ).execute(telegram_id)
    return _to_response(customer)


@router.post("/register", status_code=201)
async def register(
    request: RegisterCustomerRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    async with container.session_factory() as session:
        customer = await RegisterCustomerUseCase(
            SqlAlchemyCustomerRepository(session),
        ).execute(
            RegisterCustomerCommand(
                telegram_id=request.telegram_id,
                full_name=request.full_name,
                phone=request.phone,
                city_id=request.city_id,
                contact_method=request.contact_method,
                telegram_username=request.telegram_username,
                accepted_legal_document_ids=tuple(request.accepted_legal_document_ids),
            ),
        )
        await session.commit()
    return _to_response(customer)


@router.patch("/by-telegram/{telegram_id}/telegram-username")
async def update_telegram_username(
    telegram_id: int,
    request: UpdateTelegramUsernameRequest,
    container: Annotated[Container, Depends(get_container)],
) -> CustomerResponse:
    async with container.session_factory() as session:
        customer = await UpdateCustomerUsernameUseCase(
            SqlAlchemyCustomerRepository(session),
        ).execute(
            UpdateCustomerUsernameCommand(
                telegram_id=telegram_id,
                telegram_username=request.telegram_username,
            ),
        )
        await session.commit()
    return _to_response(customer)


__all__ = ["router"]
