from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.application import utc_now
from backend.common.domain import ValidationError
from backend.modules.catalog.infrastructure import (
    CityModel,
    ServiceCategoryModel,
    ServiceModel,
)
from backend.modules.customers.infrastructure import CustomerModel
from backend.modules.files.infrastructure import FileLinkModel, FileModel
from backend.modules.orders.application import (
    CancellationPreviewDTO,
    FullAddressSnapshotDTO,
    MyOrderCardDTO,
    MyOrdersPageDTO,
    MyOrderSummaryDTO,
    OrderLocationDTO,
    OrderReportDTO,
)
from backend.modules.orders.infrastructure.persistence.models import (
    OrderAddressSnapshotModel,
    OrderModel,
    OrderReportModel,
)
from backend.modules.payments.infrastructure import PaymentModel

ACTIVE_ORDER_STATUSES = frozenset(
    {
        "searching",
        "waiting_payment",
        "confirmed",
        "in_progress",
        "waiting_report",
        "report_submitted",
    },
)
ARCHIVE_ORDER_STATUSES = frozenset({"completed", "cancelled", "expired"})


class SqlAlchemyMyOrdersQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_customer_orders(
        self,
        *,
        customer_id: UUID,
        group: str,
        page: int,
        page_size: int,
        category_code: str | None = None,
    ) -> MyOrdersPageDTO:
        statement = self._base_statement(group, category_code=category_code).where(
            OrderModel.customer_id == customer_id,
        )
        return await self._list_orders(
            statement,
            page=page,
            page_size=page_size,
        )

    async def get_customer_cancellation_preview(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> CancellationPreviewDTO | None:
        result = await self._session.execute(
            select(OrderModel, PaymentModel.status, PaymentModel.amount)
            .outerjoin(
                PaymentModel,
                PaymentModel.id == OrderModel.active_payment_id,
            )
            .where(
                OrderModel.id == order_id,
                OrderModel.customer_id == customer_id,
            ),
        )
        row = result.one_or_none()
        if row is None:
            return None
        order, payment_status, payment_amount = row
        remaining_minutes = max(
            0,
            int((order.start_at - utc_now()).total_seconds() // 60),
        )
        can_cancel = order.status in {"searching", "waiting_payment", "confirmed"}
        if not can_cancel:
            return CancellationPreviewDTO(
                order_id=order.id,
                order_status=order.status,
                can_cancel=False,
                refund_outcome="not_available",
                refund_amount=Decimal("0.00"),
                policy_version=order.refund_policy_version_at_payment,
                partial_refund_percent=order.partial_refund_percent_at_payment,
                remaining_minutes=remaining_minutes,
            )
        if payment_status != "succeeded" or payment_amount is None:
            outcome = "none"
            amount = Decimal("0.00")
        elif remaining_minutes > 12 * 60:
            outcome = "full"
            amount = payment_amount
        elif remaining_minutes >= 6 * 60:
            outcome = "partial"
            percent = order.partial_refund_percent_at_payment or Decimal("0")
            amount = (payment_amount * percent / Decimal("100")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        else:
            outcome = "none"
            amount = Decimal("0.00")
        return CancellationPreviewDTO(
            order_id=order.id,
            order_status=order.status,
            can_cancel=True,
            refund_outcome=outcome,
            refund_amount=amount,
            policy_version=order.refund_policy_version_at_payment,
            partial_refund_percent=order.partial_refund_percent_at_payment,
            remaining_minutes=remaining_minutes,
        )

    async def get_customer_order_card(
        self,
        *,
        customer_id: UUID,
        order_id: UUID,
    ) -> MyOrderCardDTO | None:
        statement = self._base_statement().where(
            OrderModel.id == order_id,
            OrderModel.customer_id == customer_id,
        )
        return await self._get_order_card(statement, include_payment_url=True)

    async def list_performer_orders(
        self,
        *,
        performer_id: UUID,
        group: str,
        page: int,
        page_size: int,
    ) -> MyOrdersPageDTO:
        statement = self._base_statement(group).where(
            OrderModel.selected_performer_id == performer_id,
        )
        return await self._list_orders(
            statement,
            page=page,
            page_size=page_size,
        )

    async def get_performer_order_card(
        self,
        *,
        performer_id: UUID,
        order_id: UUID,
    ) -> MyOrderCardDTO | None:
        statement = self._base_statement().where(
            OrderModel.id == order_id,
            OrderModel.selected_performer_id == performer_id,
        )
        return await self._get_order_card(statement, include_payment_url=False)

    async def get_order_location(
        self,
        *,
        order_id: UUID,
        customer_id: UUID | None = None,
        performer_id: UUID | None = None,
    ) -> OrderLocationDTO | None:
        statement = (
            select(OrderModel, OrderAddressSnapshotModel, PaymentModel.status)
            .outerjoin(
                OrderAddressSnapshotModel,
                OrderAddressSnapshotModel.order_id == OrderModel.id,
            )
            .outerjoin(PaymentModel, PaymentModel.id == OrderModel.active_payment_id)
            .where(OrderModel.id == order_id)
        )
        if customer_id is not None:
            statement = statement.where(OrderModel.customer_id == customer_id)
        elif performer_id is not None:
            statement = statement.where(
                OrderModel.selected_performer_id == performer_id,
            )
        else:
            raise ValidationError("Location actor is required")
        result = await self._session.execute(statement)
        row = result.one_or_none()
        if row is None:
            return None
        _, snapshot, payment_status = row
        if snapshot is None:
            return None
        address = None
        if payment_status == "succeeded":
            address = FullAddressSnapshotDTO(
                city_name=snapshot.city_name,
                district_name=snapshot.district_name,
                address_text=snapshot.address_text,
                fias_id=snapshot.fias_id,
                latitude=snapshot.latitude,
                longitude=snapshot.longitude,
                geocoding_provider=snapshot.geocoding_provider,
                geocoding_quality=snapshot.geocoding_quality,
                entrance=snapshot.entrance,
                floor=snapshot.floor,
                apartment=snapshot.apartment,
                comment=snapshot.comment,
            )
        return OrderLocationDTO(
            order_id=order_id,
            city_name=snapshot.city_name,
            district_name=snapshot.district_name,
            address=address,
        )

    async def get_order_report(
        self,
        *,
        order_id: UUID,
        customer_id: UUID | None = None,
        performer_id: UUID | None = None,
    ) -> tuple[OrderReportDTO, tuple[FileModel, ...]] | None:
        statement = (
            select(OrderReportModel)
            .join(OrderModel, OrderModel.id == OrderReportModel.order_id)
            .where(
                OrderReportModel.order_id == order_id,
                OrderModel.status.in_(("report_submitted", "completed")),
            )
        )
        if customer_id is not None:
            statement = statement.where(OrderModel.customer_id == customer_id)
        elif performer_id is not None:
            statement = statement.where(
                OrderModel.selected_performer_id == performer_id,
                OrderReportModel.performer_id == performer_id,
            )
        else:
            raise ValidationError("Report actor is required")
        report = (await self._session.execute(statement)).scalar_one_or_none()
        if report is None:
            return None
        files_result = await self._session.execute(
            select(FileModel)
            .join(FileLinkModel, FileLinkModel.file_id == FileModel.id)
            .where(
                FileLinkModel.entity_type == "order_report",
                FileLinkModel.entity_id == report.id,
                FileLinkModel.purpose == "report_photo",
                FileModel.status == "uploaded",
            )
            .order_by(FileLinkModel.sort_order, FileLinkModel.created_at),
        )
        files = tuple(files_result.scalars())
        return (
            OrderReportDTO(
                id=report.id,
                order_id=report.order_id,
                performer_id=report.performer_id,
                completed_work=report.completed_work,
                comment=report.comment,
                problem_flag=report.problem_flag,
                problem_description=report.problem_description,
                submitted_at=report.submitted_at,
                file_ids=tuple(file.id for file in files),
            ),
            files,
        )

    def _base_statement(
        self,
        group: str | None = None,
        *,
        category_code: str | None = None,
    ) -> Select[Any]:
        statement = (
            select(OrderModel, CityModel.timezone, ServiceCategoryModel.code)
            .join(CustomerModel, CustomerModel.id == OrderModel.customer_id)
            .join(CityModel, CityModel.id == CustomerModel.city_id)
            .join(ServiceModel, ServiceModel.id == OrderModel.service_id)
            .join(
                ServiceCategoryModel,
                ServiceCategoryModel.id == ServiceModel.category_id,
            )
            .where(
                CustomerModel.status == "active",
                CustomerModel.deleted_at.is_(None),
                CityModel.is_active.is_(True),
            )
            .order_by(
                OrderModel.start_at.desc(),
                OrderModel.created_at.desc(),
            )
        )
        if group is not None:
            statement = statement.where(
                OrderModel.status.in_(_statuses_for_group(group)),
            )
        if category_code is not None:
            statement = statement.where(ServiceCategoryModel.code == category_code)
        return statement

    async def _list_orders(
        self,
        statement: Select[Any],
        *,
        page: int,
        page_size: int,
    ) -> MyOrdersPageDTO:
        total_result = await self._session.execute(
            select(func.count()).select_from(statement.order_by(None).subquery()),
        )
        total_items = int(total_result.scalar_one())
        result = await self._session.execute(
            statement.offset((page - 1) * page_size).limit(page_size),
        )
        items = tuple(
            _summary_dto(order, timezone, category_code)
            for order, timezone, category_code in result.all()
        )
        return MyOrdersPageDTO(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=(total_items + page_size - 1) // page_size,
        )

    async def _get_order_card(
        self,
        statement: Select[Any],
        *,
        include_payment_url: bool,
    ) -> MyOrderCardDTO | None:
        result = await self._session.execute(
            statement.outerjoin(
                PaymentModel,
                PaymentModel.id == OrderModel.active_payment_id,
            )
            .add_columns(
                PaymentModel.status,
                PaymentModel.confirmation_url,
                PaymentModel.expires_at,
            )
            .limit(1),
        )
        row = result.one_or_none()
        if row is None:
            return None
        (
            order,
            timezone,
            category_code,
            payment_status,
            confirmation_url,
            payment_expires_at,
        ) = row
        return MyOrderCardDTO(
            **_summary_dto(order, timezone, category_code).__dict__,
            payment_status=payment_status,
            payment_confirmation_url=confirmation_url if include_payment_url else None,
            payment_expires_at=payment_expires_at,
        )


def _statuses_for_group(group: str) -> frozenset[str]:
    if group == "active":
        return ACTIVE_ORDER_STATUSES
    if group == "archive":
        return ARCHIVE_ORDER_STATUSES
    raise ValidationError("Unknown my orders group")


def _summary_dto(
    model: OrderModel,
    timezone: str,
    category_code: str,
) -> MyOrderSummaryDTO:
    return MyOrderSummaryDTO(
        id=model.id,
        category_code=category_code,
        service_name=model.service_name,
        matching_mode=model.matching_mode,
        status=model.status,
        start_at=model.start_at,
        end_at=model.end_at,
        objects_count=model.objects_count,
        total_amount=model.total_amount,
        payment_deadline_at=model.payment_deadline_at,
        matching_deadline_at=model.matching_deadline_at,
        timezone=timezone,
    )
