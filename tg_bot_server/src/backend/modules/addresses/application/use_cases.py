from dataclasses import dataclass
from uuid import UUID

from backend.common.domain import NotFoundError, ValidationError
from backend.modules.addresses.application.dto import AddressDTO, CreateAddressCommand
from backend.modules.addresses.application.interfaces import AddressRepository
from backend.modules.customers.application.interfaces import CustomerRepository
from backend.modules.customers.domain import CustomerStatus
from backend.modules.geo.application import AddressSuggestionDTO, Geocoder
from backend.modules.performers.application.interfaces import PerformerRepository


@dataclass(frozen=True)
class SuggestAddressCommand:
    city_id: UUID
    query: str


@dataclass(frozen=True)
class CreateOwnerAddressCommand:
    telegram_id: int
    city_id: UUID
    unrestricted_value: str
    entrance: str | None = None
    floor: str | None = None
    apartment: str | None = None
    comment: str | None = None


class SuggestAddressesUseCase:
    def __init__(
        self, address_repository: AddressRepository, geocoder: Geocoder
    ) -> None:
        self._address_repository = address_repository
        self._geocoder = geocoder

    async def execute(
        self,
        command: SuggestAddressCommand,
    ) -> tuple[AddressSuggestionDTO, ...]:
        if not command.query.strip():
            return ()
        city_name = await self._address_repository.get_city_name(command.city_id)
        if city_name is None:
            raise ValidationError("City is inactive or unknown")
        return await self._geocoder.suggest(query=command.query, city=city_name)


class CreateCustomerAddressUseCase:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        address_repository: AddressRepository,
        geocoder: Geocoder,
    ) -> None:
        self._customer_repository = customer_repository
        self._address_repository = address_repository
        self._geocoder = geocoder

    async def execute(self, command: CreateOwnerAddressCommand) -> AddressDTO:
        customer = await self._customer_repository.get_by_telegram_id(
            command.telegram_id,
        )
        if customer is None:
            raise NotFoundError("Customer is not registered")
        if customer.status != CustomerStatus.ACTIVE:
            raise ValidationError("Customer cannot manage addresses")
        normalized = await self._geocoder.normalize(
            unrestricted_value=command.unrestricted_value,
        )
        return await self._address_repository.add(
            CreateAddressCommand(
                owner_type="customer",
                customer_id=customer.id,
                performer_id=None,
                city_id=command.city_id,
                district_id=None,
                address_text=normalized.address_text,
                fias_id=normalized.fias_id,
                latitude=normalized.latitude,
                longitude=normalized.longitude,
                geocoding_provider=normalized.provider,
                geocoding_quality=normalized.quality,
                entrance=command.entrance,
                floor=command.floor,
                apartment=command.apartment,
                comment=command.comment,
            ),
        )


class CreatePerformerAddressUseCase:
    def __init__(
        self,
        performer_repository: PerformerRepository,
        address_repository: AddressRepository,
        geocoder: Geocoder,
    ) -> None:
        self._performer_repository = performer_repository
        self._address_repository = address_repository
        self._geocoder = geocoder

    async def execute(self, command: CreateOwnerAddressCommand) -> AddressDTO:
        performer = await self._performer_repository.get_performer_by_telegram_id(
            command.telegram_id,
        )
        if performer is None:
            raise NotFoundError("Performer is not registered")
        normalized = await self._geocoder.normalize(
            unrestricted_value=command.unrestricted_value,
        )
        address = await self._address_repository.add(
            CreateAddressCommand(
                owner_type="performer",
                customer_id=None,
                performer_id=performer.id,
                city_id=command.city_id,
                district_id=None,
                address_text=normalized.address_text,
                fias_id=normalized.fias_id,
                latitude=normalized.latitude,
                longitude=normalized.longitude,
                geocoding_provider=normalized.provider,
                geocoding_quality=normalized.quality,
                entrance=command.entrance,
                floor=command.floor,
                apartment=command.apartment,
                comment=command.comment,
            ),
        )
        if performer.current_address_id is None:
            await self._performer_repository.set_current_address(
                performer_id=performer.id,
                address_id=address.id,
            )
        return address


class DeleteCustomerAddressUseCase:
    def __init__(
        self,
        customer_repository: CustomerRepository,
        address_repository: AddressRepository,
    ) -> None:
        self._customer_repository = customer_repository
        self._address_repository = address_repository

    async def execute(self, *, telegram_id: int, address_id: UUID) -> None:
        customer = await self._customer_repository.get_by_telegram_id(telegram_id)
        if customer is None:
            raise NotFoundError("Customer is not registered")
        address = await self._address_repository.get(address_id)
        if address is None or address.customer_id != customer.id:
            raise NotFoundError("Address not found")
        await self._address_repository.soft_delete(address_id)


class DeletePerformerAddressUseCase:
    def __init__(
        self,
        performer_repository: PerformerRepository,
        address_repository: AddressRepository,
    ) -> None:
        self._performer_repository = performer_repository
        self._address_repository = address_repository

    async def execute(self, *, telegram_id: int, address_id: UUID) -> None:
        performer = await self._performer_repository.get_performer_by_telegram_id(
            telegram_id,
        )
        if performer is None:
            raise NotFoundError("Performer is not registered")
        if performer.current_address_id == address_id:
            raise ValidationError("Current performer address cannot be deleted")
        address = await self._address_repository.get(address_id)
        if address is None or address.performer_id != performer.id:
            raise NotFoundError("Address not found")
        await self._address_repository.soft_delete(address_id)


class SetPerformerCurrentAddressUseCase:
    def __init__(
        self,
        performer_repository: PerformerRepository,
        address_repository: AddressRepository,
    ) -> None:
        self._performer_repository = performer_repository
        self._address_repository = address_repository

    async def execute(self, *, telegram_id: int, address_id: UUID) -> AddressDTO:
        performer = await self._performer_repository.get_performer_by_telegram_id(
            telegram_id,
        )
        if performer is None:
            raise NotFoundError("Performer is not registered")
        address = await self._address_repository.get(address_id)
        if (
            address is None
            or address.performer_id != performer.id
            or address.deleted_at is not None
        ):
            raise NotFoundError("Address not found")
        await self._performer_repository.set_current_address(
            performer_id=performer.id,
            address_id=address.id,
        )
        return address
