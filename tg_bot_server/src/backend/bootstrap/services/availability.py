from ._shared import (
    AddCalendarOverrideCommand,
    AddCalendarOverrideUseCase,
    Any,
    CheckPerformerAvailabilityCommand,
    CheckPerformerAvailabilityUseCase,
    FindSuitablePerformersCommand,
    FindSuitablePerformersUseCase,
    GetPerformerCalendarUseCase,
    NotFoundError,
    SetPerformerScheduleCommand,
    SetPerformerScheduleUseCase,
    SqlAlchemyAvailabilityRepository,
    SqlAlchemyCatalogQueryService,
    ValidationError,
    to_utc,
)
from .context import Service


class AvailabilityServices(Service):
    async def set_performer_schedule(
        self,
        command: SetPerformerScheduleCommand,
    ) -> Any:
        async with self._uow() as uow:
            schedule = await SetPerformerScheduleUseCase(
                SqlAlchemyAvailabilityRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return schedule

    async def add_calendar_override(
        self,
        command: AddCalendarOverrideCommand,
    ) -> Any:
        async with self._uow() as uow:
            repository = SqlAlchemyAvailabilityRepository(uow.session)
            timezone = await repository.get_performer_timezone_by_telegram_id(
                command.telegram_id,
            )
            if timezone is None:
                raise NotFoundError("Performer not found")
            override = await AddCalendarOverrideUseCase(
                repository,
            ).execute(
                AddCalendarOverrideCommand(
                    telegram_id=command.telegram_id,
                    override_type=command.override_type,
                    starts_at=to_utc(command.starts_at, timezone),
                    ends_at=to_utc(command.ends_at, timezone),
                    comment=command.comment,
                ),
            )
            await uow.commit()
            return override

    async def get_performer_calendar(self, telegram_id: int) -> Any:
        async with self._uow() as uow:
            return await GetPerformerCalendarUseCase(
                SqlAlchemyAvailabilityRepository(uow.session),
            ).execute(telegram_id)

    async def check_performer_availability(
        self,
        command: CheckPerformerAvailabilityCommand,
    ) -> Any:
        async with self._uow() as uow:
            repository = SqlAlchemyAvailabilityRepository(uow.session)
            timezone = await repository.get_performer_timezone(command.performer_id)
            if timezone is None:
                raise NotFoundError("Performer not found")
            return await CheckPerformerAvailabilityUseCase(
                repository,
            ).execute(
                CheckPerformerAvailabilityCommand(
                    performer_id=command.performer_id,
                    service_id=command.service_id,
                    starts_at=to_utc(command.starts_at, timezone),
                    ends_at=to_utc(command.ends_at, timezone),
                    exclude_order_id=command.exclude_order_id,
                    exclude_match_id=command.exclude_match_id,
                ),
            )

    async def find_suitable_performers(
        self,
        command: FindSuitablePerformersCommand,
    ) -> Any:
        async with self._uow() as uow:
            repository = SqlAlchemyAvailabilityRepository(uow.session)
            timezone = await SqlAlchemyCatalogQueryService(
                uow.session
            ).get_city_timezone(
                command.city_id,
            )
            if timezone is None:
                raise ValidationError("City is inactive or unknown")
            return await FindSuitablePerformersUseCase(
                repository,
            ).execute(
                FindSuitablePerformersCommand(
                    city_id=command.city_id,
                    service_id=command.service_id,
                    starts_at=to_utc(command.starts_at, timezone),
                    ends_at=to_utc(command.ends_at, timezone),
                    objects_count=command.objects_count,
                    care_object_ids=command.care_object_ids,
                    address_id=command.address_id,
                    limit=command.limit,
                ),
            )
