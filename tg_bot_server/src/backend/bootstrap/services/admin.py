from ._shared import (
    UUID,
    Any,
    Argon2PasswordHasher,
    BootstrapAdminCommand,
    BootstrapAdminUseCase,
    BusinessSettingResponse,
    Decimal,
    GetCurrentAdminUseCase,
    InvalidOperation,
    LoginAdminCommand,
    LoginAdminUseCase,
    LogoutAdminUseCase,
    NotFoundError,
    NotificationModel,
    SqlAlchemyAdminAuditRepository,
    SqlAlchemyAdminRepository,
    SqlAlchemyBusinessSettingRepository,
    SqlAlchemyNotificationRepository,
    ValidationError,
    utc_now,
)
from .context import Service


class AdminServices(Service):
    async def list_admin_notifications(
        self,
        *,
        admin_id: UUID,
        status: str | None,
        is_read: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[NotificationModel], int]:
        async with self._uow() as uow:
            return await SqlAlchemyNotificationRepository(uow.session).list_admin_inbox(
                admin_id=admin_id,
                status=status,
                is_read=is_read,
                offset=(page - 1) * page_size,
                limit=page_size,
            )

    async def mark_admin_notifications_read(
        self,
        *,
        admin_id: UUID,
        notification_ids: list[UUID],
    ) -> int:
        async with self._uow() as uow:
            count = await SqlAlchemyNotificationRepository(uow.session).mark_admin_read(
                admin_id=admin_id,
                notification_ids=notification_ids,
            )
            await uow.commit()
            return count

    @staticmethod
    def _validated_setting_value(value_type: str, value: object) -> object:
        if value is None:
            return None
        if value_type == "boolean":
            if not isinstance(value, bool):
                raise ValidationError("Business setting value must be boolean")
            return value
        if value_type in {"number", "integer", "decimal"}:
            if isinstance(value, bool) or not isinstance(value, int | float | str):
                raise ValidationError("Business setting value must be numeric")
            try:
                parsed = Decimal(str(value))
            except InvalidOperation as exc:
                raise ValidationError("Business setting value must be numeric") from exc
            if value_type == "integer" and parsed % 1:
                raise ValidationError("Business setting value must be integer")
            return value
        if value_type == "string":
            if not isinstance(value, str):
                raise ValidationError("Business setting value must be string")
            return value
        if value_type == "json":
            return value
        raise ValidationError("Business setting value type is invalid")

    async def login_admin(self, command: LoginAdminCommand) -> Any:
        async with self._uow() as uow:
            result = await LoginAdminUseCase(
                repository=SqlAlchemyAdminRepository(uow.session),
                password_hasher=Argon2PasswordHasher(),
                session_store=self._session_store(),
            ).execute(command)
            await uow.commit()
            return result

    async def get_current_admin(self, session_id: str) -> Any:
        async with self._uow() as uow:
            return await GetCurrentAdminUseCase(
                repository=SqlAlchemyAdminRepository(uow.session),
                session_store=self._session_store(),
            ).execute(session_id)

    async def logout_admin(self, session_id: str) -> None:
        await LogoutAdminUseCase(self._session_store()).execute(session_id)

    async def bootstrap_admin(self, command: BootstrapAdminCommand) -> Any:
        async with self._uow() as uow:
            admin = await BootstrapAdminUseCase(
                repository=SqlAlchemyAdminRepository(uow.session),
                password_hasher=Argon2PasswordHasher(),
            ).execute(command)
            await uow.commit()
            return admin

    async def update_business_setting(
        self,
        *,
        key: str,
        value: object,
        admin_id: UUID,
    ) -> BusinessSettingResponse:
        async with self._uow() as uow:
            setting = await SqlAlchemyBusinessSettingRepository(
                uow.session,
            ).get_by_key(key)
            if setting is None:
                raise NotFoundError("Business setting not found")
            new_value = self._validated_setting_value(setting.value_type, value)
            old_value = setting.value
            setting.value = new_value
            setting.updated_by_admin_id = admin_id
            setting.updated_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="update_business_setting",
                entity_type="business_setting",
                entity_id=setting.id,
                audit_metadata={
                    "key": key,
                    "old_value": old_value,
                    "new_value": new_value,
                },
            )
            response = BusinessSettingResponse(
                key=setting.key,
                value=setting.value,
                value_type=setting.value_type,
            )
            await uow.commit()
            return response
