from ._shared import (
    UUID,
    Any,
    CalculatePricePreviewCommand,
    CalculatePricePreviewUseCase,
    CancelOrderCommand,
    CancelOrderUseCase,
    ConfirmReportCommand,
    ConfirmReportUseCase,
    CreateDirectOrderCommand,
    CreateDirectOrderUseCase,
    CreatePoolOrderCommand,
    CreatePoolOrderUseCase,
    FinishOrderCommand,
    FinishOrderUseCase,
    OrderReportDetailDTO,
    OrderReportFileDTO,
    SqlAlchemyAvailabilityRepository,
    SqlAlchemyFileRepository,
    SqlAlchemyMatchingRepository,
    SqlAlchemyMyOrdersQueryService,
    SqlAlchemyOrderRepository,
    SqlAlchemyPricingRepository,
    StartOrderCommand,
    StartOrderUseCase,
    SubmitOrderReportCommand,
    SubmitOrderReportUseCase,
    ValidationError,
    to_utc,
)
from .context import Service, ServiceContext
from .payments import PaymentServices


class OrderServices(Service):
    def __init__(self, context: ServiceContext, payments: PaymentServices) -> None:
        super().__init__(context)
        self.payments = payments

    async def create_pool_order(self, command: CreatePoolOrderCommand) -> Any:
        async with self._uow() as uow:
            order = await CreatePoolOrderUseCase(
                SqlAlchemyOrderRepository(uow.session),
                SqlAlchemyPricingRepository(uow.session),
            ).execute(command)
            await uow.commit()
            return order

    async def confirm_customer_report(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            order = await ConfirmReportUseCase(
                SqlAlchemyOrderRepository(uow.session),
                SqlAlchemyPricingRepository(uow.session),
            ).execute(
                ConfirmReportCommand(
                    order_id=order_id,
                    customer_id=customer_id,
                ),
            )
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

    async def invite_direct_performer(
        self,
        *,
        order_id: UUID,
        customer_id: UUID,
        performer_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            match = await SqlAlchemyMatchingRepository(
                uow.session,
            ).invite_direct_performer(
                order_id=order_id,
                customer_id=customer_id,
                performer_id=performer_id,
            )
            await uow.commit()
            return match

    async def publish_pool_order(self, *, order_id: UUID, customer_id: UUID) -> Any:
        async with self._uow() as uow:
            order = await SqlAlchemyMatchingRepository(uow.session).publish_pool(
                order_id=order_id,
                customer_id=customer_id,
            )
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
                self._storage(),
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

    async def get_order_report(
        self,
        *,
        order_id: UUID,
        customer_id: UUID | None = None,
        performer_id: UUID | None = None,
    ) -> OrderReportDetailDTO | None:
        async with self._uow() as uow:
            result = await SqlAlchemyMyOrdersQueryService(
                uow.session,
            ).get_order_report(
                order_id=order_id,
                customer_id=customer_id,
                performer_id=performer_id,
            )
            if result is None:
                return None
            report, files = result
            report_files: list[OrderReportFileDTO] = []
            for file in files:
                if file.storage_key is None:
                    continue
                report_files.append(
                    OrderReportFileDTO(
                        id=file.id,
                        original_name=file.original_name,
                        mime_type=file.mime_type,
                        signed_url=await self._storage().create_download_url(
                            file.storage_key,
                        ),
                    ),
                )
            return OrderReportDetailDTO(
                id=report.id,
                order_id=report.order_id,
                performer_id=report.performer_id,
                completed_work=report.completed_work,
                comment=report.comment,
                problem_flag=report.problem_flag,
                problem_description=report.problem_description,
                submitted_at=report.submitted_at,
                files=tuple(report_files),
            )

    async def cancel_order(
        self,
        *,
        order_id: UUID,
        actor_type: str,
        actor_id: UUID,
        comment: str | None = None,
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
                    reason="admin_decision" if actor_type == "admin" else None,
                    comment=comment,
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
        category_code: str | None = None,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMyOrdersQueryService(
                uow.session
            ).list_customer_orders(
                customer_id=customer_id,
                group=group,
                page=page,
                page_size=page_size,
                category_code=category_code,
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

    async def get_customer_cancellation_preview(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMyOrdersQueryService(
                uow.session,
            ).get_customer_cancellation_preview(
                customer_id=customer_id,
                order_id=order_id,
            )

    async def get_customer_order_location(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMyOrdersQueryService(
                uow.session,
            ).get_order_location(
                order_id=order_id,
                customer_id=customer_id,
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

    async def get_performer_order_location(
        self,
        *,
        performer_id: UUID,
        order_id: UUID,
    ) -> Any:
        async with self._uow() as uow:
            return await SqlAlchemyMyOrdersQueryService(
                uow.session,
            ).get_order_location(
                order_id=order_id,
                performer_id=performer_id,
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
            await self.payments.initialize_payment(result.payment.payment_id)
            return await self.payments.with_payment_prompt(result)
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
            await self.payments.initialize_payment(result.payment.payment_id)
            return await self.payments.with_payment_prompt(result)
        return result
