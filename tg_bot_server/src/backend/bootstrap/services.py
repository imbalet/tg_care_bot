from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any
from uuid import UUID

from backend.common.application import to_utc, utc_now
from backend.common.domain import NotFoundError, ValidationError
from backend.common.infrastructure import S3ObjectStorage
from backend.common.infrastructure.database import SqlAlchemyUnitOfWork
from backend.modules.addresses.application import (
    CreateCustomerAddressUseCase,
    CreateOwnerAddressCommand,
    CreatePerformerAddressUseCase,
    DeleteCustomerAddressUseCase,
    DeletePerformerAddressUseCase,
    SetPerformerCurrentAddressUseCase,
    SuggestAddressCommand,
    SuggestAddressesUseCase,
)
from backend.modules.addresses.infrastructure import SqlAlchemyAddressRepository
from backend.modules.admin.application import (
    BootstrapAdminCommand,
    BootstrapAdminUseCase,
    GetCurrentAdminUseCase,
    LoginAdminCommand,
    LoginAdminUseCase,
    LogoutAdminUseCase,
)
from backend.modules.admin.infrastructure import (
    AdminAuditLogModel,
    Argon2PasswordHasher,
    RedisAdminSessionStore,
    SqlAlchemyAdminAuditRepository,
    SqlAlchemyAdminRepository,
)
from backend.modules.admin.presentation.api.schemas import BusinessSettingResponse
from backend.modules.availability.application import (
    AddCalendarOverrideCommand,
    AddCalendarOverrideUseCase,
    CheckPerformerAvailabilityCommand,
    CheckPerformerAvailabilityUseCase,
    FindSuitablePerformersCommand,
    FindSuitablePerformersUseCase,
    GetPerformerCalendarUseCase,
    SetPerformerScheduleCommand,
    SetPerformerScheduleUseCase,
)
from backend.modules.availability.infrastructure import SqlAlchemyAvailabilityRepository
from backend.modules.care_objects.application import (
    CreateCustomerCareObjectCommand,
    CreateCustomerCareObjectUseCase,
    DeleteCustomerCareObjectUseCase,
    ListCustomerCareObjectsUseCase,
    UpdateCustomerCareObjectCommand,
    UpdateCustomerCareObjectUseCase,
)
from backend.modules.care_objects.infrastructure import SqlAlchemyCareObjectRepository
from backend.modules.catalog.infrastructure import (
    SqlAlchemyBusinessSettingRepository,
    SqlAlchemyCatalogQueryService,
)
from backend.modules.customers.application import (
    GetCustomerProfileUseCase,
    RegisterCustomerCommand,
    RegisterCustomerUseCase,
    UpdateCustomerUsernameCommand,
    UpdateCustomerUsernameUseCase,
)
from backend.modules.customers.infrastructure import SqlAlchemyCustomerRepository
from backend.modules.files.application import (
    UploadPerformerAvatarCommand,
    UploadPerformerAvatarUseCase,
)
from backend.modules.files.infrastructure import SqlAlchemyFileRepository
from backend.modules.geo.infrastructure import DaDataGeocoder
from backend.modules.notifications.infrastructure import NotificationModel
from backend.modules.orders.application import (
    CalculatePricePreviewCommand,
    CalculatePricePreviewUseCase,
    CancelOrderCommand,
    CancelOrderUseCase,
    CreateDirectOrderCommand,
    CreateDirectOrderUseCase,
    CreatePoolOrderCommand,
    CreatePoolOrderUseCase,
    FinishOrderCommand,
    FinishOrderUseCase,
    StartOrderCommand,
    StartOrderUseCase,
    SubmitOrderReportCommand,
    SubmitOrderReportUseCase,
)
from backend.modules.orders.infrastructure import (
    SqlAlchemyMatchingRepository,
    SqlAlchemyMyOrdersQueryService,
    SqlAlchemyOrderRepository,
    SqlAlchemyPricingRepository,
)
from backend.modules.payments.application import (
    ApplyPaymentWebhookUseCase,
    CreateManualRefundCommand,
    CreateManualRefundUseCase,
    GetCustomerPaymentStatusCommand,
    GetCustomerPaymentStatusUseCase,
    PaymentGatewayInitCommand,
    PaymentGatewayRefundCommand,
    PaymentWebhookCommand,
    RetryPaymentOperationCommand,
    RetryPaymentOperationUseCase,
)
from backend.modules.payments.infrastructure import (
    SqlAlchemyPaymentRepository,
    TBankPaymentGateway,
    TBankReceiptSettings,
)
from backend.modules.performers.application import (
    ActivatePerformerUseCase,
    ApprovePerformerServiceCommand,
    ApprovePerformerServiceUseCase,
    CreateInvitationCommand,
    CreateInvitationUseCase,
    GetRegistrationStateUseCase,
    ListPerformerServicesUseCase,
    RegisterPerformerCommand,
    RegisterPerformerUseCase,
    SetPerformerAcceptingOrdersCommand,
    SetPerformerAcceptingOrdersUseCase,
    SetPerformerServiceEnabledCommand,
    SetPerformerServiceEnabledUseCase,
    SetPerformerServiceMaxObjectsCommand,
    SetPerformerServiceMaxObjectsUseCase,
    UpdatePerformerUsernameCommand,
    UpdatePerformerUsernameUseCase,
)
from backend.modules.performers.infrastructure import (
    PerformerModel,
    SqlAlchemyPerformerRepository,
)
from backend.modules.system_checks.application import (
    CreateSystemCheckCommand,
    CreateSystemCheckUseCase,
)

if TYPE_CHECKING:
    from backend.bootstrap.container import Container


@dataclass(frozen=True)
class ApplicationServices:
    container: Container

    def _uow(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.container.session_factory)

    def _session_store(self) -> RedisAdminSessionStore:
        return RedisAdminSessionStore(
            redis=self.container.redis,
            ttl_seconds=self.container.settings.admin_session_ttl_seconds,
        )

    def _geocoder(self) -> DaDataGeocoder:
        settings = self.container.settings
        return DaDataGeocoder(
            api_key=settings.dadata_api_key,
            secret_key=settings.dadata_secret_key,
            base_url=settings.dadata_base_url,
            timeout_seconds=settings.dadata_timeout_seconds,
            retry_count=settings.dadata_retry_count,
        )

    def _storage(self) -> S3ObjectStorage:
        settings = self.container.settings
        return S3ObjectStorage(
            endpoint_url=settings.s3_endpoint_url,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            bucket=settings.s3_bucket,
            region=settings.s3_region,
            signed_url_ttl_seconds=settings.s3_signed_url_ttl_seconds,
        )

    def _payment_gateway(self) -> TBankPaymentGateway:
        settings = self.container.settings
        if not settings.tbank_terminal_key or not settings.tbank_password:
            raise ValidationError("T-Bank payment credentials are not configured")
        if (
            settings.environment == "production"
            and settings.payment_receipt_defaults_allowed
        ):
            raise ValidationError(
                "Production payment receipt settings must be explicit"
            )
        return TBankPaymentGateway(
            base_url=settings.tbank_base_url,
            terminal_key=settings.tbank_terminal_key,
            password=settings.tbank_password,
            notification_url=settings.tbank_notification_url or None,
            receipt=TBankReceiptSettings(
                taxation=settings.payment_receipt_taxation,
                tax=settings.payment_receipt_tax,
                payment_method=settings.payment_receipt_method,
                payment_object=settings.payment_receipt_object,
            ),
            timeout_seconds=settings.tbank_timeout_seconds,
        )

    async def list_cities(self, *, active_only: bool) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyCatalogQueryService(uow.session).list_cities(
                active_only=active_only,
            )

    async def get_catalog(self, *, active_only: bool) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyCatalogQueryService(uow.session).get_catalog(
                active_only=active_only,
            )

    async def get_support_contact(self) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyCatalogQueryService(
                uow.session
            ).get_support_contact()

    async def list_legal_documents(self, *, active_only: bool) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyCatalogQueryService(
                uow.session,
            ).list_legal_documents(active_only=active_only)

    async def suggest_addresses(self, command: SuggestAddressCommand) -> Any:
        async with self._uow() as uow:
            return await SuggestAddressesUseCase(
                SqlAlchemyAddressRepository(uow.session),
                self._geocoder(),
            ).execute(command)

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

    async def create_pool_order(self, command: CreatePoolOrderCommand) -> Any:
        async with self._uow() as uow:
            order = await CreatePoolOrderUseCase(
                SqlAlchemyOrderRepository(uow.session),
                SqlAlchemyPricingRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return order

    async def create_direct_order(self, command: CreateDirectOrderCommand) -> Any:
        async with self._uow() as uow:
            order = await CreateDirectOrderUseCase(
                SqlAlchemyOrderRepository(uow.session),
                SqlAlchemyPricingRepository(uow.session),
                SqlAlchemyAvailabilityRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return order

    async def start_order(self, *, order_id: UUID, performer_id: UUID) -> Any:
        async with self._uow() as uow:
            order = await StartOrderUseCase(
                SqlAlchemyOrderRepository(uow.session),
            ).execute(
                StartOrderCommand(order_id=order_id, performer_id=performer_id),
            )
            await uow.commit()
            return order

    async def finish_order(self, *, order_id: UUID, performer_id: UUID) -> Any:
        async with self._uow() as uow:
            order = await FinishOrderUseCase(
                SqlAlchemyOrderRepository(uow.session),
                SqlAlchemyPricingRepository(uow.session),
            ).execute(
                FinishOrderCommand(order_id=order_id, performer_id=performer_id),
            )
            await uow.commit()
            return order

    async def submit_order_report(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
        completed_work: str,
        comment: str | None,
        problem_flag: bool,
        problem_description: str | None,
        file_ids: tuple[UUID, ...],
    ) -> Any:
        async with self._uow() as uow:
            report = await SubmitOrderReportUseCase(
                SqlAlchemyOrderRepository(uow.session),
                SqlAlchemyFileRepository(uow.session),
            ).execute(
                SubmitOrderReportCommand(
                    order_id=order_id,
                    performer_id=performer_id,
                    completed_work=completed_work,
                    comment=comment,
                    problem_flag=problem_flag,
                    problem_description=problem_description,
                    file_ids=file_ids,
                ),
            )
            await uow.commit()
            return report

    async def cancel_order(
        self,
        *,
        order_id: UUID,
        actor_type: str,
        actor_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            order = await CancelOrderUseCase(
                SqlAlchemyOrderRepository(uow.session),
                SqlAlchemyPricingRepository(uow.session),
            ).execute(
                CancelOrderCommand(
                    order_id=order_id,
                    actor_type=actor_type,
                    actor_id=actor_id,
                ),
            )
            await uow.commit()
            return order

    async def calculate_price_preview(
        self,
        command: CalculatePricePreviewCommand,
    ) -> Any:
        async with self._uow() as uow:
            timezone = await SqlAlchemyOrderRepository(
                uow.session,
            ).get_customer_timezone(command.customer_id)
            if timezone is None:
                raise ValidationError("Customer is inactive or unknown")
            return await CalculatePricePreviewUseCase(
                SqlAlchemyPricingRepository(uow.session),
            ).execute(
                CalculatePricePreviewCommand(
                    customer_id=command.customer_id,
                    service_id=command.service_id,
                    start_at=to_utc(command.start_at, timezone),
                    end_at=to_utc(command.end_at, timezone),
                    objects_count=command.objects_count,
                ),
            )

    async def list_available_pool_orders(
        self,
        *,
        performer_id: UUID,
        limit: int,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMatchingRepository(
                uow.session,
            ).list_available_pool_orders(performer_id=performer_id, limit=limit)

    async def list_customer_my_orders(
        self,
        *,
        customer_id: UUID,
        group: str,
        page: int,
        page_size: int,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMyOrdersQueryService(
                uow.session
            ).list_customer_orders(
                customer_id=customer_id,
                group=group,
                page=page,
                page_size=page_size,
            )

    async def get_customer_my_order(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMyOrdersQueryService(
                uow.session,
            ).get_customer_order_card(
                customer_id=customer_id,
                order_id=order_id,
            )

    async def list_performer_my_orders(
        self,
        *,
        performer_id: UUID,
        group: str,
        page: int,
        page_size: int,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMyOrdersQueryService(
                uow.session,
            ).list_performer_orders(
                performer_id=performer_id,
                group=group,
                page=page,
                page_size=page_size,
            )

    async def get_performer_my_order(
        self,
        *,
        performer_id: UUID,
        order_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMyOrdersQueryService(
                uow.session,
            ).get_performer_order_card(
                performer_id=performer_id,
                order_id=order_id,
            )

    async def create_pool_response(
        self,
        *,
        order_id: UUID,
        performer_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            match = await SqlAlchemyMatchingRepository(
                uow.session,
            ).create_pool_response(order_id=order_id, performer_id=performer_id)
            await uow.commit()
            return match

    async def list_order_matches(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMatchingRepository(uow.session).list_order_matches(
                order_id=order_id,
                customer_id=customer_id,
            )

    async def reject_pool_response(
        self,
        *,
        match_id: UUID,
        customer_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            match = await SqlAlchemyMatchingRepository(
                uow.session,
            ).reject_pool_response(match_id=match_id, customer_id=customer_id)
            await uow.commit()
            return match

    async def accept_direct_match(
        self,
        *,
        match_id: UUID,
        performer_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            result = await SqlAlchemyMatchingRepository(uow.session).accept_direct(
                match_id=match_id,
                performer_id=performer_id,
            )
            await uow.commit()
        if result.payment is not None:
            await self._initialize_payment(result.payment.payment_id)
            return await self._with_payment_prompt(result)
        return result

    async def reject_direct_match(
        self,
        *,
        match_id: UUID,
        performer_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            match = await SqlAlchemyMatchingRepository(uow.session).reject_direct(
                match_id=match_id,
                performer_id=performer_id,
            )
            await uow.commit()
            return match

    async def select_pool_response(
        self,
        *,
        match_id: UUID,
        customer_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            result = await SqlAlchemyMatchingRepository(
                uow.session,
            ).select_pool_response(match_id=match_id, customer_id=customer_id)
            await uow.commit()
        if result.payment is not None:
            await self._initialize_payment(result.payment.payment_id)
            return await self._with_payment_prompt(result)
        return result

    async def _initialize_payment(self, payment_id: UUID) -> None:
        async with self._uow() as uow:
            repository = SqlAlchemyPaymentRepository(uow.session)
            data = await repository.get_initialization_data(payment_id)
        if data is None:
            raise NotFoundError("Payment not found")
        if data.payment.status != "created":
            return
        gateway = self._payment_gateway()
        description = f"Оплата заказа {data.payment.order_id} ({data.service_name})"
        try:
            result = await gateway.create_payment(
                PaymentGatewayInitCommand(
                    payment_id=data.payment.id,
                    order_id=data.payment.order_id,
                    idempotency_key=data.payment.idempotency_key,
                    amount=data.payment.amount,
                    description=description,
                    customer_phone=data.customer_phone,
                    customer_name=data.customer_name,
                ),
            )
        except Exception:
            async with self._uow() as uow:
                await SqlAlchemyPaymentRepository(
                    uow.session,
                ).mark_provider_initialization_failed(
                    payment_id=data.payment.id,
                    failure_code="provider_init_failed",
                )
                await uow.commit()
            raise
        async with self._uow() as uow:
            await SqlAlchemyPaymentRepository(uow.session).mark_provider_initialized(
                payment_id=data.payment.id,
                provider_payment_id=result.provider_payment_id,
                provider_deal_id=result.provider_deal_id,
                confirmation_url=result.confirmation_url,
            )
            await uow.commit()

    async def _with_payment_prompt(self, result: Any) -> Any:
        async with self._uow() as uow:
            data = await SqlAlchemyPaymentRepository(
                uow.session,
            ).get_initialization_data(result.payment.payment_id)
        if data is None:
            return result
        return type(result)(
            order=result.order,
            match=result.match,
            payment=type(result.payment)(
                payment_id=data.payment.id,
                confirmation_url=data.payment.confirmation_url,
                expires_at=data.payment.expires_at,
                timezone=result.payment.timezone,
            ),
        )

    async def apply_payment_webhook(self, command: PaymentWebhookCommand) -> Any:
        async with self._uow() as uow:
            result = await ApplyPaymentWebhookUseCase(
                SqlAlchemyPaymentRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return result

    async def create_manual_refund(
        self,
        command: CreateManualRefundCommand,
    ) -> Any:
        async with self._uow() as uow:
            repository = SqlAlchemyPaymentRepository(uow.session)
            refund = await CreateManualRefundUseCase(repository).execute(command)
            data = await repository.get_initialization_data(refund.payment_id)
            if data is None or data.payment.provider_payment_id is None:
                raise ValidationError("Provider payment id is not available")
            uow.session.add(
                AdminAuditLogModel(
                    admin_id=command.admin_id,
                    action="manual_refund_created",
                    entity_type="refund",
                    entity_id=refund.id,
                    reason=command.reason,
                    audit_metadata={
                        "payment_id": str(command.payment_id),
                        "amount": str(command.amount),
                    },
                ),
            )
            await uow.commit()
            provider_payment_id = data.payment.provider_payment_id
        if refund.status != "pending":
            return refund
        gateway = self._payment_gateway()
        try:
            result = await gateway.create_refund(
                PaymentGatewayRefundCommand(
                    refund_id=refund.id,
                    payment_id=refund.payment_id,
                    provider_payment_id=provider_payment_id,
                    idempotency_key=refund.idempotency_key,
                    amount=refund.amount,
                ),
            )
        except Exception:
            async with self._uow() as uow:
                await SqlAlchemyPaymentRepository(uow.session).mark_refund_failed(
                    refund_id=refund.id,
                )
                await uow.commit()
            raise
        async with self._uow() as uow:
            await SqlAlchemyPaymentRepository(uow.session).mark_refund_succeeded(
                refund_id=refund.id,
                provider_refund_id=result.provider_refund_id,
            )
            await uow.commit()
        return refund

    async def get_customer_payment_status(
        self,
        command: GetCustomerPaymentStatusCommand,
    ) -> Any:
        async with self._uow() as uow:
            return await GetCustomerPaymentStatusUseCase(
                SqlAlchemyPaymentRepository(uow.session),
            ).execute(command)

    async def retry_payment_operation(
        self,
        *,
        command: RetryPaymentOperationCommand,
        admin_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            result = await RetryPaymentOperationUseCase(
                SqlAlchemyPaymentRepository(uow.session),
                self._payment_gateway(),
            ).execute(command)
            uow.session.add(
                AdminAuditLogModel(
                    admin_id=admin_id,
                    action="retry_payment_operation",
                    entity_type="payment",
                    entity_id=command.payment_id,
                    reason=None,
                    audit_metadata={
                        "applied": result.applied if result is not None else False,
                        "status": result.status if result is not None else None,
                    },
                ),
            )
            await uow.commit()
            return result

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
            return await GetRegistrationStateUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute(telegram_id)

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

    async def list_performer_services_by_id(self, performer_id: UUID) -> Any:
        async with self._uow() as uow:
            return await ListPerformerServicesUseCase(
                SqlAlchemyPerformerRepository(uow.session),
            ).execute_for_performer(performer_id)

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
            new_value = _validated_setting_value(setting.value_type, value)
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

    async def create_system_check(self, command: CreateSystemCheckCommand) -> Any:
        return await CreateSystemCheckUseCase(self._uow()).execute(command)


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
