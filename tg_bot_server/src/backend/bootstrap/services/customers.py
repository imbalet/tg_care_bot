from ._shared import (
    UUID,
    Any,
    CreateCustomerAddressUseCase,
    CreateCustomerCareObjectCommand,
    CreateCustomerCareObjectUseCase,
    CreateOwnerAddressCommand,
    DeleteCustomerAddressUseCase,
    DeleteCustomerCareObjectUseCase,
    GetCustomerProfileUseCase,
    ListCustomerCareObjectsUseCase,
    RegisterCustomerCommand,
    RegisterCustomerUseCase,
    SqlAlchemyAddressRepository,
    SqlAlchemyCareObjectRepository,
    SqlAlchemyCustomerRepository,
    UpdateCustomerAddressCommand,
    UpdateCustomerAddressUseCase,
    UpdateCustomerCareObjectCommand,
    UpdateCustomerCareObjectUseCase,
    UpdateCustomerProfileCommand,
    UpdateCustomerProfileUseCase,
    UpdateCustomerUsernameCommand,
    UpdateCustomerUsernameUseCase,
)
from .context import Service


class CustomerServices(Service):
    async def get_customer_profile(self, telegram_id: int) -> Any:
        async with self._uow() as uow:
            return await GetCustomerProfileUseCase(
                SqlAlchemyCustomerRepository(uow.session),
            ).execute(telegram_id)

    async def register_customer(self, command: RegisterCustomerCommand) -> Any:
        async with self._uow() as uow:
            customer = await RegisterCustomerUseCase(
                SqlAlchemyCustomerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return customer

    async def update_customer_username(
        self,
        command: UpdateCustomerUsernameCommand,
    ) -> Any:
        async with self._uow() as uow:
            customer = await UpdateCustomerUsernameUseCase(
                SqlAlchemyCustomerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return customer

    async def update_customer_profile(
        self,
        command: UpdateCustomerProfileCommand,
    ) -> Any:
        async with self._uow() as uow:
            customer = await UpdateCustomerProfileUseCase(
                SqlAlchemyCustomerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return customer

    async def list_customer_care_objects(
        self,
        *,
        telegram_id: int,
        object_type: str | None,
    ) -> Any:
        async with self._uow() as uow:
            return await ListCustomerCareObjectsUseCase(
                SqlAlchemyCustomerRepository(uow.session),
                SqlAlchemyCareObjectRepository(uow.session),
            ).execute(telegram_id=telegram_id, object_type=object_type)

    async def create_customer_care_object(
        self,
        command: CreateCustomerCareObjectCommand,
    ) -> Any:
        async with self._uow() as uow:
            care_object = await CreateCustomerCareObjectUseCase(
                SqlAlchemyCustomerRepository(uow.session),
                SqlAlchemyCareObjectRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return care_object

    async def update_customer_care_object(
        self,
        command: UpdateCustomerCareObjectCommand,
    ) -> Any:
        async with self._uow() as uow:
            care_object = await UpdateCustomerCareObjectUseCase(
                SqlAlchemyCustomerRepository(uow.session),
                SqlAlchemyCareObjectRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return care_object

    async def delete_customer_care_object(
        self,
        *,
        telegram_id: int,
        care_object_id: UUID,
    ) -> None:
        async with self._uow() as uow:
            await DeleteCustomerCareObjectUseCase(
                SqlAlchemyCustomerRepository(uow.session),
                SqlAlchemyCareObjectRepository(uow.session),
            ).execute(telegram_id=telegram_id, care_object_id=care_object_id)
            await uow.commit()

    async def list_customer_addresses(self, *, telegram_id: int) -> Any:
        async with self._uow() as uow:
            customer = await GetCustomerProfileUseCase(
                SqlAlchemyCustomerRepository(uow.session),
            ).execute(telegram_id)
            return await SqlAlchemyAddressRepository(uow.session).list_for_customer(
                customer.id,
            )

    async def create_customer_address(
        self,
        command: CreateOwnerAddressCommand,
    ) -> Any:
        async with self._uow() as uow:
            address = await CreateCustomerAddressUseCase(
                SqlAlchemyCustomerRepository(uow.session),
                SqlAlchemyAddressRepository(uow.session),
                self._geocoder(),
            ).execute(command)
            await uow.commit()
            return address

    async def delete_customer_address(
        self,
        *,
        telegram_id: int,
        address_id: UUID,
    ) -> None:
        async with self._uow() as uow:
            await DeleteCustomerAddressUseCase(
                SqlAlchemyCustomerRepository(uow.session),
                SqlAlchemyAddressRepository(uow.session),
            ).execute(telegram_id=telegram_id, address_id=address_id)
            await uow.commit()

    async def update_customer_address(
        self,
        command: UpdateCustomerAddressCommand,
    ) -> Any:
        async with self._uow() as uow:
            address = await UpdateCustomerAddressUseCase(
                SqlAlchemyCustomerRepository(uow.session),
                SqlAlchemyAddressRepository(uow.session),
                self._geocoder(),
            ).execute(command)
            await uow.commit()
            return address
