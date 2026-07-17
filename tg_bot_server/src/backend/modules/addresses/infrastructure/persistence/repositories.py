from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.common.domain import NotFoundError, ValidationError
from backend.modules.addresses.application import AddressDTO, CreateAddressCommand
from backend.modules.catalog.infrastructure import CityModel

from .models import AddressModel


def _validate_owner(command: CreateAddressCommand) -> None:
    customer_owner = (
        command.owner_type == "customer"
        and command.customer_id is not None
        and command.performer_id is None
    )
    performer_owner = (
        command.owner_type == "performer"
        and command.customer_id is None
        and command.performer_id is not None
    )
    if not customer_owner and not performer_owner:
        raise ValidationError("Invalid address owner")


def _to_dto(model: AddressModel) -> AddressDTO:
    return AddressDTO(
        id=model.id,
        owner_type=model.owner_type,
        customer_id=model.customer_id,
        performer_id=model.performer_id,
        city_id=model.city_id,
        district_id=model.district_id,
        address_text=model.address_text,
        fias_id=model.fias_id,
        latitude=model.latitude,
        longitude=model.longitude,
        geocoding_provider=model.geocoding_provider,
        geocoding_quality=model.geocoding_quality,
        entrance=model.entrance,
        floor=model.floor,
        apartment=model.apartment,
        comment=model.comment,
        deleted_at=model.deleted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyAddressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, address_id: UUID) -> AddressDTO | None:
        model = await self._session.get(AddressModel, address_id)
        return _to_dto(model) if model is not None else None

    async def add(self, command: CreateAddressCommand) -> AddressDTO:
        _validate_owner(command)
        model = AddressModel(
            owner_type=command.owner_type,
            customer_id=command.customer_id,
            performer_id=command.performer_id,
            city_id=command.city_id,
            district_id=command.district_id,
            address_text=command.address_text,
            fias_id=command.fias_id,
            latitude=command.latitude,
            longitude=command.longitude,
            geocoding_provider=command.geocoding_provider,
            geocoding_quality=command.geocoding_quality,
            entrance=command.entrance,
            floor=command.floor,
            apartment=command.apartment,
            comment=command.comment,
        )
        self._session.add(model)
        await self._session.flush()
        return _to_dto(model)

    async def soft_delete(self, address_id: UUID) -> None:
        model = await self._session.get(AddressModel, address_id)
        if model is None or model.deleted_at is not None:
            raise NotFoundError("Address not found")
        model.deleted_at = utc_now()

    async def get_city_name(self, city_id: UUID) -> str | None:
        result = await self._session.execute(
            select(CityModel.name).where(
                CityModel.id == city_id,
                CityModel.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def list_for_customer(
        self,
        customer_id: UUID,
        *,
        active_only: bool = True,
    ) -> tuple[AddressDTO, ...]:
        statement = select(AddressModel).where(AddressModel.customer_id == customer_id)
        if active_only:
            statement = statement.where(AddressModel.deleted_at.is_(None))
        statement = statement.order_by(AddressModel.created_at)
        result = await self._session.execute(statement)
        return tuple(_to_dto(model) for model in result.scalars())

    async def list_for_performer(
        self,
        performer_id: UUID,
        *,
        active_only: bool = True,
    ) -> tuple[AddressDTO, ...]:
        statement = select(AddressModel).where(
            AddressModel.performer_id == performer_id,
        )
        if active_only:
            statement = statement.where(AddressModel.deleted_at.is_(None))
        statement = statement.order_by(AddressModel.created_at)
        result = await self._session.execute(statement)
        return tuple(_to_dto(model) for model in result.scalars())
