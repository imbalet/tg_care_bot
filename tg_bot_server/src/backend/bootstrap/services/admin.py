from typing import Any

from backend.modules.admin.infrastructure import AdminAuditLogModel, AdminViolationModel
from backend.modules.admin.infrastructure.persistence.query_service import (
    SqlAlchemyAdminQueryService,
)
from backend.modules.catalog.infrastructure import (
    CityModel,
    DistrictModel,
    LegalDocumentModel,
    ObjectCountMultiplierModel,
    ServiceCategoryModel,
    ServiceModel,
    ServiceOptionModel,
)
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.files.infrastructure import FileModel, SqlAlchemyFileRepository
from backend.modules.performers.infrastructure import PerformerModel

from ._shared import (
    UUID,
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
    @staticmethod
    def _audit_change_value(value: Any) -> Any:
        if value is None or isinstance(value, bool | int | float | str):
            return value
        return str(value)

    async def create_violation(
        self,
        *,
        account_type: str,
        customer_id: UUID | None,
        performer_id: UUID | None,
        order_id: UUID | None,
        case_type: str | None,
        case_id: UUID | None,
        violation_type: str,
        action: str,
        reason: str,
        admin_id: UUID,
    ) -> dict[str, Any]:
        if account_type not in {"customer", "performer"}:
            raise ValidationError("Account type is invalid")
        if action not in {"warning", "block"}:
            raise ValidationError("Violation action is invalid")
        if account_type == "customer" and customer_id is None:
            raise ValidationError("Customer ID is required")
        if account_type == "performer" and performer_id is None:
            raise ValidationError("Performer ID is required")
        async with self._uow() as uow:
            account: Any
            if account_type == "customer":
                account_id = customer_id
                account = await uow.session.get(
                    CustomerModel,
                    customer_id,
                    with_for_update=True,
                )
            else:
                account_id = performer_id
                account = await uow.session.get(
                    PerformerModel,
                    performer_id,
                    with_for_update=True,
                )
            if account is None:
                raise NotFoundError("Account not found")
            violation = AdminViolationModel(
                account_type=account_type,
                customer_id=customer_id,
                performer_id=performer_id,
                order_id=order_id,
                case_type=case_type,
                case_id=case_id,
                violation_type=violation_type,
                action=action,
                reason=reason,
                status="open",
                created_by_admin_id=admin_id,
            )
            uow.session.add(violation)
            if action == "block":
                account.status = "blocked"
                account.blocked_reason = reason
                if account_type == "performer":
                    account.is_accepting_orders = False
                account.updated_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="create_admin_violation",
                entity_type="admin_violation",
                entity_id=violation.id,
                reason=reason,
                audit_metadata={
                    "account_type": account_type,
                    "account_id": str(account_id),
                    "action": action,
                    "case_type": case_type,
                },
            )
            await uow.commit()
            return {
                "id": str(violation.id),
                "status": violation.status,
                "action": action,
            }

    async def resolve_violation(
        self,
        *,
        violation_id: UUID,
        comment: str,
        admin_id: UUID,
    ) -> dict[str, Any]:
        async with self._uow() as uow:
            violation = await uow.session.get(
                AdminViolationModel,
                violation_id,
                with_for_update=True,
            )
            if violation is None:
                raise NotFoundError("Violation not found")
            violation.resolve()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="resolve_admin_violation",
                entity_type="admin_violation",
                entity_id=violation_id,
                reason=comment,
            )
            await uow.commit()
            return {"id": str(violation.id), "status": violation.status}

    async def block_customer(
        self, *, customer_id: UUID, reason: str, comment: str, admin_id: UUID
    ) -> dict[str, Any]:
        async with self._uow() as uow:
            customer = await uow.session.get(
                CustomerModel, customer_id, with_for_update=True
            )
            if customer is None:
                raise NotFoundError("Customer not found")
            customer.status = "blocked"
            customer.blocked_reason = reason
            customer.updated_at = utc_now()
            violation = AdminViolationModel(
                account_type="customer",
                customer_id=customer_id,
                performer_id=None,
                order_id=None,
                case_type=None,
                case_id=None,
                violation_type="admin_block",
                action="block",
                reason=reason,
                created_by_admin_id=admin_id,
            )
            uow.session.add(violation)
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="block_customer",
                entity_type="customer",
                entity_id=customer_id,
                reason=comment,
                audit_metadata={"violation_id": str(violation.id), "reason": reason},
            )
            await uow.commit()
            return {"id": str(customer.id), "status": customer.status}

    async def unblock_customer(
        self, *, customer_id: UUID, comment: str, admin_id: UUID
    ) -> dict[str, Any]:
        async with self._uow() as uow:
            customer = await uow.session.get(
                CustomerModel, customer_id, with_for_update=True
            )
            if customer is None:
                raise NotFoundError("Customer not found")
            if customer.status != "blocked":
                raise ValidationError("Customer is not blocked")
            customer.status = "active"
            customer.blocked_reason = None
            customer.updated_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="unblock_customer",
                entity_type="customer",
                entity_id=customer_id,
                reason=comment,
            )
            await uow.commit()
            return {"id": str(customer.id), "status": customer.status}

    async def update_catalog_service(
        self,
        *,
        service_id: UUID,
        changes: dict[str, Any],
        admin_id: UUID,
        reason: str,
    ) -> dict[str, Any]:
        async with self._uow() as uow:
            service = await uow.session.get(
                ServiceModel, service_id, with_for_update=True
            )
            if service is None:
                raise NotFoundError("Service not found")
            changed: dict[str, Any] = {}
            for key, new_value in changes.items():
                if new_value is None or key == "comment":
                    continue
                old_value = getattr(service, key)
                if old_value != new_value:
                    setattr(service, key, new_value)
                    changed[key] = {
                        "old": self._audit_change_value(old_value),
                        "new": self._audit_change_value(new_value),
                    }
            if "min_duration_minutes" in changes and "max_duration_minutes" in changes:
                minimum = changes["min_duration_minutes"]
                maximum = changes["max_duration_minutes"]
                if minimum is not None and maximum is not None and minimum > maximum:
                    raise ValidationError(
                        "Minimum duration cannot exceed maximum duration"
                    )
            service.updated_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="update_catalog_service",
                entity_type="service",
                entity_id=service_id,
                reason=reason,
                audit_metadata={"changed": changed},
            )
            await uow.commit()
            return {"id": str(service.id), "changed": changed}

    async def update_catalog_service_option(
        self,
        *,
        option_id: UUID,
        changes: dict[str, Any],
        admin_id: UUID,
        reason: str,
    ) -> dict[str, Any]:
        async with self._uow() as uow:
            option = await uow.session.get(
                ServiceOptionModel, option_id, with_for_update=True
            )
            if option is None:
                raise NotFoundError("Service option not found")
            changed: dict[str, Any] = {}
            for key, new_value in changes.items():
                if new_value is None or key == "comment":
                    continue
                old_value = getattr(option, key)
                if old_value != new_value:
                    setattr(option, key, new_value)
                    changed[key] = {
                        "old": self._audit_change_value(old_value),
                        "new": self._audit_change_value(new_value),
                    }
            option.updated_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="update_catalog_service_option",
                entity_type="service_option",
                entity_id=option_id,
                reason=reason,
                audit_metadata={"changed": changed},
            )
            await uow.commit()
            return {"id": str(option.id), "changed": changed}

    async def update_catalog_city(
        self,
        *,
        city_id: UUID,
        changes: dict[str, Any],
        admin_id: UUID,
        reason: str,
    ) -> dict[str, Any]:
        async with self._uow() as uow:
            city = await uow.session.get(CityModel, city_id, with_for_update=True)
            if city is None:
                raise NotFoundError("City not found")
            changed: dict[str, Any] = {}
            for key, new_value in changes.items():
                if new_value is None or key == "comment":
                    continue
                old_value = getattr(city, key)
                if old_value != new_value:
                    setattr(city, key, new_value)
                    changed[key] = {
                        "old": self._audit_change_value(old_value),
                        "new": self._audit_change_value(new_value),
                    }
            city.updated_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="update_catalog_city",
                entity_type="city",
                entity_id=city_id,
                reason=reason,
                audit_metadata={"changed": changed},
            )
            await uow.commit()
            return {"id": str(city.id), "changed": changed}

    async def get_ui_dashboard(self, *, admin_id: UUID | None = None) -> dict[str, Any]:
        async with self._uow() as uow:
            return await SqlAlchemyAdminQueryService(uow.session).dashboard(
                admin_id=admin_id
            )

    async def get_ui_work_queue(self, queue: str, *, limit: int = 50) -> dict[str, Any]:
        async with self._uow() as uow:
            return await SqlAlchemyAdminQueryService(uow.session).work_queue(
                queue,
                limit=limit,
            )

    async def list_ui_resource(
        self,
        resource: str,
        *,
        page: int,
        page_size: int,
        query: str | None = None,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        async with self._uow() as uow:
            return await SqlAlchemyAdminQueryService(uow.session).list_resources(
                resource,
                page=page,
                page_size=page_size,
                query=query,
                status=status,
            )

    async def get_ui_resource(self, resource: str, entity_id: UUID) -> dict[str, Any]:
        async with self._uow() as uow:
            return await SqlAlchemyAdminQueryService(uow.session).get(
                resource, entity_id
            )

    async def hide_file(self, file_id: UUID, *, admin_id: UUID) -> None:
        async with self._uow() as uow:
            await SqlAlchemyFileRepository(uow.session).mark_deleted(file_id)
            uow.session.add(
                AdminAuditLogModel(
                    admin_id=admin_id,
                    action="hide_file",
                    entity_type="file",
                    entity_id=file_id,
                    audit_metadata={},
                ),
            )
            await uow.commit()

    async def get_file_download_url(
        self, file_id: UUID, *, admin_id: UUID
    ) -> dict[str, Any]:
        async with self._uow() as uow:
            file = await uow.session.get(FileModel, file_id)
            if file is None or file.status == "deleted" or not file.storage_key:
                raise NotFoundError("File is not available")
            url = await self._storage().create_download_url(file.storage_key)
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="view_admin_file",
                entity_type="file",
                entity_id=file_id,
                audit_metadata={"purpose": "operator_review"},
            )
            await uow.commit()
            return {
                "id": str(file.id),
                "url": url,
                "expires_in": self.context.settings.s3_signed_url_ttl_seconds,
                "mime_type": file.mime_type,
                "original_name": file.original_name,
            }

    async def update_catalog_resource(
        self,
        *,
        resource: str,
        entity_id: UUID,
        changes: dict[str, Any],
        admin_id: UUID,
        reason: str,
    ) -> dict[str, Any]:
        models: dict[str, type[Any]] = {
            "cities": CityModel,
            "districts": DistrictModel,
            "service-categories": ServiceCategoryModel,
            "services": ServiceModel,
            "service-options": ServiceOptionModel,
            "multipliers": ObjectCountMultiplierModel,
            "legal-documents": LegalDocumentModel,
        }
        editable_fields = {
            "cities": {"name", "timezone", "is_active"},
            "districts": {"city_id", "name", "is_active"},
            "service-categories": {
                "name",
                "care_object_type",
                "max_objects_per_order",
                "is_active",
                "sort_order",
            },
            "services": {
                "category_id",
                "name",
                "description",
                "price_type",
                "base_price",
                "location_policy",
                "photo_policy",
                "schedule_policy",
                "allows_multiday",
                "min_duration_minutes",
                "max_duration_minutes",
                "duration_step_minutes",
                "is_active",
                "sort_order",
            },
            "service-options": {
                "service_id",
                "name",
                "value_type",
                "is_required",
                "is_active",
                "sort_order",
            },
            "multipliers": {"category_id", "objects_count", "multiplier", "is_active"},
            "legal-documents": {"document_type", "version", "content_url", "is_active"},
        }
        if resource not in models:
            raise ValidationError("Catalog resource is not editable")
        unknown = set(changes) - editable_fields[resource] - {"comment"}
        if unknown:
            raise ValidationError("Catalog field is not editable")
        async with self._uow() as uow:
            entity = await uow.session.get(
                models[resource], entity_id, with_for_update=True
            )
            if entity is None:
                raise NotFoundError("Catalog record not found")
            minimum = changes.get(
                "min_duration_minutes", getattr(entity, "min_duration_minutes", None)
            )
            maximum = changes.get(
                "max_duration_minutes", getattr(entity, "max_duration_minutes", None)
            )
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValidationError("Minimum duration cannot exceed maximum duration")
            changed: dict[str, Any] = {}
            for key in editable_fields[resource]:
                if key not in changes or changes[key] is None:
                    continue
                old_value = getattr(entity, key)
                new_value = changes[key]
                if key.endswith("_id") and isinstance(new_value, str):
                    try:
                        new_value = UUID(new_value)
                    except ValueError as exc:
                        raise ValidationError(f"Invalid UUID for {key}") from exc
                if key in {"max_objects_per_order", "objects_count", "sort_order"} and (
                    not isinstance(new_value, int) or new_value < 0
                ):
                    raise ValidationError(f"Invalid non-negative integer for {key}")
                if old_value != new_value:
                    setattr(entity, key, new_value)
                    changed[key] = {
                        "old": self._audit_change_value(old_value),
                        "new": self._audit_change_value(new_value),
                    }
            if hasattr(entity, "updated_at"):
                entity.updated_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="update_catalog_resource",
                entity_type=resource,
                entity_id=entity_id,
                reason=reason,
                audit_metadata={"changed": changed},
            )
            await uow.commit()
            return {"id": str(entity_id), "resource": resource, "changed": changed}

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

    async def retry_admin_notification(
        self, notification_id: UUID, *, admin_id: UUID
    ) -> dict[str, Any]:
        async with self._uow() as uow:
            notification = await uow.session.get(
                NotificationModel, notification_id, with_for_update=True
            )
            if notification is None or notification.recipient_type != "admin":
                raise NotFoundError("Admin notification not found")
            if notification.status not in {"failed", "dead"}:
                raise ValidationError("Only failed notifications can be retried")
            if notification.admin_retry_count >= 1:
                raise ValidationError("Manual notification retry limit reached")
            notification.status = "pending"
            notification.attempts = 0
            notification.admin_retry_count += 1
            notification.last_error = None
            notification.claimed_at = None
            notification.scheduled_at = utc_now()
            await SqlAlchemyAdminAuditRepository(uow.session).add(
                admin_id=admin_id,
                action="retry_admin_notification",
                entity_type="notification",
                entity_id=notification_id,
                audit_metadata={"admin_retry_count": notification.admin_retry_count},
            )
            await uow.commit()
            return {"id": str(notification.id), "status": notification.status}

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
