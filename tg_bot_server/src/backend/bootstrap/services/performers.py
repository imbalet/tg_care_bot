from dataclasses import replace

from sqlalchemy import select

from backend.modules.admin.infrastructure import AdminViolationModel

from ._shared import (
    UUID,
    ActivatePerformerUseCase,
    AddCalendarOverrideCommand,
    AddCalendarOverrideUseCase,
    Any,
    ApprovePerformerServiceCommand,
    ApprovePerformerServiceUseCase,
    Callable,
    ConflictError,
    CreateInvitationCommand,
    CreateInvitationUseCase,
    CreateOwnerAddressCommand,
    CreatePerformerAddressUseCase,
    DeletePerformerAddressUseCase,
    GetNearbyOrderNotificationsUseCase,
    GetRegistrationStateUseCase,
    ListPerformerServicesUseCase,
    NotFoundError,
    NotificationModel,
    PerformerModel,
    RegisterPerformerCommand,
    RegisterPerformerUseCase,
    RevokePerformerServiceCommand,
    RevokePerformerServiceUseCase,
    SetNearbyOrderNotificationsCommand,
    SetNearbyOrderNotificationsUseCase,
    SetPerformerAcceptingOrdersCommand,
    SetPerformerAcceptingOrdersUseCase,
    SetPerformerCurrentAddressUseCase,
    SetPerformerScheduleCommand,
    SetPerformerScheduleUseCase,
    SetPerformerServiceEnabledCommand,
    SetPerformerServiceEnabledUseCase,
    SetPerformerServiceMaxObjectsCommand,
    SetPerformerServiceMaxObjectsUseCase,
    SqlAlchemyAddressRepository,
    SqlAlchemyAdminAuditRepository,
    SqlAlchemyAvailabilityRepository,
    SqlAlchemyCustomerRepository,
    SqlAlchemyFileRepository,
    SqlAlchemyPerformerRepository,
    SyncPerformerServicesCommand,
    SyncPerformerServicesUseCase,
    UpdatePerformerProfileCommand,
    UpdatePerformerProfileUseCase,
    UpdatePerformerUsernameCommand,
    UpdatePerformerUsernameUseCase,
    UploadActorFileCommand,
    UploadActorFileUseCase,
    UploadPerformerAvatarCommand,
    UploadPerformerAvatarUseCase,
    timedelta,
    utc_now,
)
from .context import Service


class PerformerServices(Service):
    async def upload_performer_file(
        self,
        command: UploadActorFileCommand,
    ) -> Any:
        async with self._uow() as uow:
            file = await UploadActorFileUseCase(
                SqlAlchemyCustomerRepository(uow.session),
                SqlAlchemyPerformerRepository(uow.session),
                SqlAlchemyFileRepository(uow.session),
                self._storage(),
            ).execute(command)
            await uow.commit()
            return file

    async def create_invitation(
        self,
        command: CreateInvitationCommand,
        *,
        audit_admin_id: UUID | None = None,
    ) -> Any:
        async with self._uow() as uow:
            invitation = await CreateInvitationUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            if audit_admin_id is not None:
                await SqlAlchemyAdminAuditRepository(uow.session).add(
                    admin_id=audit_admin_id,
                    action="create_performer_invitation",
                    entity_type="performer_invitation",
                    entity_id=invitation.id,
                    audit_metadata={"telegram_id": command.telegram_id},
                )
            now = utc_now()
            uow.session.add(
                NotificationModel(
                    recipient_type="performer_invitation",
                    customer_id=None,
                    performer_id=None,
                    admin_id=None,
                    recipient_telegram_id=command.telegram_id,
                    channel="telegram",
                    type="performer_invitation_created",
                    entity_type="performer_invitation",
                    entity_id=invitation.id,
                    payload={"telegram_id": str(command.telegram_id)},
                    deduplication_key=(
                        f"performer-invitation-created:{invitation.id}:"
                        f"{invitation.updated_at.isoformat()}"
                    ),
                    status="pending",
                    attempts=0,
                    scheduled_at=now,
                    delete_after=now + timedelta(days=30),
                ),
            )
            await uow.commit()
            return invitation

    async def get_registration_state(self, telegram_id: int) -> Any:
        async with self._uow() as uow:
            state = await GetRegistrationStateUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(telegram_id)
            if state.performer is None:
                return state
            avatar = await SqlAlchemyFileRepository(
                uow.session,
            ).get_avatar_for_entity(
                entity_type="performer",
                entity_id=state.performer.id,
            )
            return replace(
                state,
                performer=replace(
                    state.performer,
                    avatar_url=(
                        await self._storage().create_download_url(avatar.storage_key)
                        if avatar is not None and avatar.storage_key is not None
                        else None
                    ),
                ),
            )

    async def get_performer_by_id(self, performer_id: UUID) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyPerformerRepository(
                uow.session,
            ).get_performer_by_id(performer_id)

    async def register_performer(self, command: RegisterPerformerCommand) -> Any:
        async with self._uow() as uow:
            performer = await RegisterPerformerUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return performer

    async def activate_performer(
        self,
        performer_id: UUID,
        *,
        audit_admin_id: UUID | None = None,
    ) -> Any:
        async with self._uow() as uow:
            performer = await ActivatePerformerUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(performer_id)
            if audit_admin_id is not None:
                await SqlAlchemyAdminAuditRepository(uow.session).add(
                    admin_id=audit_admin_id,
                    action="activate_performer",
                    entity_type="performer",
                    entity_id=performer.id,
                )
            await uow.commit()
            return performer

    async def reject_performer(
        self,
        *,
        performer_id: UUID,
        reason: str,
        comment: str,
        admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            performer = await uow.session.get(PerformerModel, performer_id)
            if performer is None:
                raise NotFoundError("Performer not found")
            if performer.status not in {"invited", "profile_pending"}:
                raise ConflictError("Performer cannot be rejected in current status")
            performer.status = "blocked"
            performer.is_accepting_orders = False
            performer.blocked_reason = reason
            performer.updated_at = utc_now()
            uow.session.add(
                AdminViolationModel(
                    account_type="performer",
                    performer_id=performer_id,
                    violation_type=reason,
                    action="block",
                    reason=comment,
                    status="open",
                    created_by_admin_id=admin_id,
                ),
            )
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="reject_performer",
                entity_type="performer",
                entity_id=performer_id,
                reason=comment,
                audit_metadata={"blocked_reason": reason},
            )
            await uow.commit()
            return performer

    async def set_accepting_orders_as_admin(
        self,
        *,
        performer_id: UUID,
        is_accepting_orders: bool,
        admin_id: UUID,
        comment: str,
    ) -> Any:
        async with self._uow() as uow:
            performer = await uow.session.get(PerformerModel, performer_id)
            if performer is None:
                raise NotFoundError("Performer not found")
            result = await SetPerformerAcceptingOrdersUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(
                SetPerformerAcceptingOrdersCommand(
                    telegram_id=performer.telegram_id,
                    is_accepting_orders=is_accepting_orders,
                ),
            )
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action=(
                    "resume_performer_orders"
                    if is_accepting_orders
                    else "pause_performer_orders"
                ),
                entity_type="performer",
                entity_id=performer_id,
                reason=comment,
            )
            await uow.commit()
            return result

    async def block_performer(
        self,
        *,
        performer_id: UUID,
        reason: str,
        comment: str,
        admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            result = await uow.session.execute(
                select(PerformerModel)
                .where(PerformerModel.id == performer_id)
                .with_for_update(),
            )
            performer = result.scalar_one_or_none()
            if performer is None:
                raise NotFoundError("Performer not found")
            if performer.status == "deletion_pending":
                raise ConflictError("Performer is pending deletion")
            performer.status = "blocked"
            performer.is_accepting_orders = False
            performer.blocked_reason = reason
            performer.updated_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="block_performer",
                entity_type="performer",
                entity_id=performer_id,
                reason=comment,
                audit_metadata={"blocked_reason": reason},
            )
            await uow.commit()
            return performer

    async def unblock_performer(
        self,
        *,
        performer_id: UUID,
        comment: str,
        admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            result = await uow.session.execute(
                select(PerformerModel)
                .where(PerformerModel.id == performer_id)
                .with_for_update(),
            )
            performer = result.scalar_one_or_none()
            if performer is None:
                raise NotFoundError("Performer not found")
            if performer.status != "blocked":
                raise ConflictError("Only blocked performers can be unblocked")
            performer.status = "active"
            performer.blocked_reason = None
            performer.updated_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="unblock_performer",
                entity_type="performer",
                entity_id=performer_id,
                reason=comment,
            )
            await uow.commit()
            return performer

    async def set_service_enabled_as_admin(
        self,
        *,
        performer_id: UUID,
        service_id: UUID,
        is_enabled: bool,
        admin_id: UUID,
        comment: str,
    ) -> Any:
        async with self._uow() as uow:
            performer = await uow.session.get(PerformerModel, performer_id)
            if performer is None:
                raise NotFoundError("Performer not found")
            result = await SetPerformerServiceEnabledUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(
                SetPerformerServiceEnabledCommand(
                    telegram_id=performer.telegram_id,
                    service_id=service_id,
                    is_enabled=is_enabled,
                ),
            )
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action=(
                    "enable_performer_service"
                    if is_enabled
                    else "disable_performer_service"
                ),
                entity_type="performer_service",
                entity_id=result.id,
                reason=comment,
            )
            await uow.commit()
            return result

    async def set_service_max_objects_as_admin(
        self,
        *,
        performer_id: UUID,
        service_id: UUID,
        performer_max_objects: int,
        admin_id: UUID,
        comment: str,
    ) -> Any:
        async with self._uow() as uow:
            performer = await uow.session.get(PerformerModel, performer_id)
            if performer is None:
                raise NotFoundError("Performer not found")
            result = await SetPerformerServiceMaxObjectsUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(
                SetPerformerServiceMaxObjectsCommand(
                    telegram_id=performer.telegram_id,
                    service_id=service_id,
                    performer_max_objects=performer_max_objects,
                ),
            )
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="set_performer_service_max_objects",
                entity_type="performer_service",
                entity_id=result.id,
                reason=comment,
                audit_metadata={"performer_max_objects": performer_max_objects},
            )
            await uow.commit()
            return result

    async def update_performer_profile_as_admin(
        self,
        *,
        performer_id: UUID,
        phone: str,
        contact_method: str,
        admin_id: UUID,
        comment: str,
    ) -> Any:
        async with self._uow() as uow:
            performer = await uow.session.get(PerformerModel, performer_id)
            if performer is None:
                raise NotFoundError("Performer not found")
            result = await UpdatePerformerProfileUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(
                UpdatePerformerProfileCommand(
                    telegram_id=performer.telegram_id,
                    phone=phone,
                    contact_method=contact_method,
                ),
            )
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="update_performer_profile",
                entity_type="performer",
                entity_id=performer_id,
                reason=comment,
            )
            await uow.commit()
            return result

    async def approve_performer_service(
        self,
        command: ApprovePerformerServiceCommand,
        *,
        audit_admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            service = await ApprovePerformerServiceUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=audit_admin_id,
                action="approve_performer_service",
                entity_type="performer_service",
                entity_id=service.id,
                audit_metadata={
                    "performer_id": str(command.performer_id),
                    "service_id": str(command.service_id),
                    "admin_max_objects": command.admin_max_objects,
                },
            )
            await uow.commit()
            return service

    async def sync_performer_services(
        self,
        command: SyncPerformerServicesCommand,
    ) -> Any:
        async with self._uow() as uow:
            result = await SyncPerformerServicesUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            for service in result.added:
                await SqlAlchemyAdminAuditRepository(uow.session).add(
                    admin_id=command.approved_by_admin_id,
                    action="approve_performer_service",
                    entity_type="performer_service",
                    entity_id=service.id,
                    audit_metadata={
                        "performer_id": str(command.performer_id),
                        "service_id": str(service.service_id),
                        "admin_max_objects": service.admin_max_objects,
                    },
                )
            for service in result.updated:
                await SqlAlchemyAdminAuditRepository(uow.session).add(
                    admin_id=command.approved_by_admin_id,
                    action="update_performer_service",
                    entity_type="performer_service",
                    entity_id=service.id,
                    audit_metadata={
                        "performer_id": str(command.performer_id),
                        "service_id": str(service.service_id),
                        "admin_max_objects": service.admin_max_objects,
                    },
                )
            for service in result.revoked:
                await SqlAlchemyAdminAuditRepository(uow.session).add(
                    admin_id=command.approved_by_admin_id,
                    action="revoke_performer_service",
                    entity_type="performer_service",
                    entity_id=service.id,
                    audit_metadata={
                        "performer_id": str(command.performer_id),
                        "service_id": str(service.service_id),
                    },
                )
            await uow.commit()
            return result

    async def list_performer_services_by_id(self, performer_id: UUID) -> Any:
        async with self._uow() as uow:
            return await ListPerformerServicesUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute_for_performer(performer_id)

    async def revoke_performer_service(
        self,
        *,
        performer_id: UUID,
        service_id: UUID,
        audit_admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            service = await RevokePerformerServiceUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(
                RevokePerformerServiceCommand(
                    performer_id=performer_id,
                    service_id=service_id,
                ),
            )
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=audit_admin_id,
                action="revoke_performer_service",
                entity_type="performer_service",
                entity_id=service.id,
                audit_metadata={
                    "performer_id": str(performer_id),
                    "service_id": str(service_id),
                },
            )
            await uow.commit()
            return service

    async def list_performer_services_by_telegram(self, telegram_id: int) -> Any:
        async with self._uow() as uow:
            return await ListPerformerServicesUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute_by_telegram_id(telegram_id)

    async def set_schedule_as_admin(
        self,
        performer_id: UUID,
        command_factory: Callable[[int], SetPerformerScheduleCommand],
        *,
        audit_admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            performer = await uow.session.get(PerformerModel, performer_id)
            if performer is None:
                raise NotFoundError("Performer not found")
            schedule = await SetPerformerScheduleUseCase(
                SqlAlchemyAvailabilityRepository(uow.session),
            ).execute(command_factory(performer.telegram_id))
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=audit_admin_id,
                action="set_performer_schedule",
                entity_type="performer_schedule",
                entity_id=schedule.id,
                audit_metadata={"performer_id": str(performer_id)},
            )
            await uow.commit()
            return schedule

    async def add_override_as_admin(
        self,
        performer_id: UUID,
        command_factory: Callable[[int], AddCalendarOverrideCommand],
        *,
        audit_admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            performer = await uow.session.get(PerformerModel, performer_id)
            if performer is None:
                raise NotFoundError("Performer not found")
            override = await AddCalendarOverrideUseCase(
                SqlAlchemyAvailabilityRepository(uow.session),
            ).execute(command_factory(performer.telegram_id))
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=audit_admin_id,
                action="add_performer_calendar_override",
                entity_type="performer_calendar_override",
                entity_id=override.id,
                audit_metadata={"performer_id": str(performer_id)},
            )
            await uow.commit()
            return override

    async def update_performer_username(
        self,
        command: UpdatePerformerUsernameCommand,
    ) -> Any:
        async with self._uow() as uow:
            performer = await UpdatePerformerUsernameUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return performer

    async def update_performer_profile(
        self,
        command: UpdatePerformerProfileCommand,
    ) -> Any:
        async with self._uow() as uow:
            performer = await UpdatePerformerProfileUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return performer

    async def set_performer_service_enabled(
        self,
        command: SetPerformerServiceEnabledCommand,
    ) -> Any:
        async with self._uow() as uow:
            service = await SetPerformerServiceEnabledUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return service

    async def set_performer_service_max_objects(
        self,
        command: SetPerformerServiceMaxObjectsCommand,
    ) -> Any:
        async with self._uow() as uow:
            service = await SetPerformerServiceMaxObjectsUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return service

    async def set_performer_accepting_orders(
        self,
        command: SetPerformerAcceptingOrdersCommand,
    ) -> Any:
        async with self._uow() as uow:
            performer = await SetPerformerAcceptingOrdersUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return performer

    async def set_nearby_order_notifications(
        self,
        command: SetNearbyOrderNotificationsCommand,
    ) -> bool:
        async with self._uow() as uow:
            enabled = await SetNearbyOrderNotificationsUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return enabled

    async def get_nearby_order_notifications(self, *, telegram_id: int) -> bool:
        async with self._uow() as uow:
            return await GetNearbyOrderNotificationsUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(telegram_id)

    async def list_performer_addresses(self, *, telegram_id: int) -> Any:
        async with self._uow() as uow:
            performer = await SqlAlchemyPerformerRepository(
                uow.session,
            ).get_performer_by_telegram_id(telegram_id)
            if performer is None:
                raise NotFoundError("Performer is not registered")
            return await SqlAlchemyAddressRepository(uow.session).list_for_performer(
                performer.id,
            )

    async def create_performer_address(
        self,
        command: CreateOwnerAddressCommand,
    ) -> Any:
        async with self._uow() as uow:
            address = await CreatePerformerAddressUseCase(
                SqlAlchemyPerformerRepository(uow.session),
                SqlAlchemyAddressRepository(uow.session),
                self._geocoder(),
            ).execute(command)
            await uow.commit()
            return address

    async def set_performer_current_address(
        self,
        *,
        telegram_id: int,
        address_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            address = await SetPerformerCurrentAddressUseCase(
                SqlAlchemyPerformerRepository(uow.session),
                SqlAlchemyAddressRepository(uow.session),
            ).execute(telegram_id=telegram_id, address_id=address_id)
            await uow.commit()
            return address

    async def delete_performer_address(
        self,
        *,
        telegram_id: int,
        address_id: UUID,
    ) -> None:
        async with self._uow() as uow:
            await DeletePerformerAddressUseCase(
                SqlAlchemyPerformerRepository(uow.session),
                SqlAlchemyAddressRepository(uow.session),
            ).execute(telegram_id=telegram_id, address_id=address_id)
            await uow.commit()

    async def upload_performer_avatar(
        self,
        command: UploadPerformerAvatarCommand,
    ) -> Any:
        async with self._uow() as uow:
            stored_file = await UploadPerformerAvatarUseCase(
                SqlAlchemyPerformerRepository(uow.session),
                SqlAlchemyFileRepository(uow.session),
                self._storage(),
            ).execute(command)
            await uow.commit()
            return stored_file

    async def delete_performer_avatar(self, *, telegram_id: int) -> None:
        async with self._uow() as uow:
            performer = await SqlAlchemyPerformerRepository(
                uow.session,
            ).get_performer_by_telegram_id(telegram_id)
            if performer is None:
                raise NotFoundError("Performer is not registered")
            file_repository = SqlAlchemyFileRepository(uow.session)
            avatar = await file_repository.get_avatar_for_entity(
                entity_type="performer",
                entity_id=performer.id,
            )
            if avatar is None:
                raise NotFoundError("Avatar not found")
            if avatar.storage_key is not None:
                await self._storage().delete(avatar.storage_key)
            await file_repository.delete_avatar_link(
                entity_type="performer",
                entity_id=performer.id,
            )
            await file_repository.mark_deleted(avatar.id)
            await uow.commit()
