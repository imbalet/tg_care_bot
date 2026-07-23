from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .matching_repositories import SqlAlchemyMatchingRepository
    from .models import (
        OrderAddressSnapshotModel,
        OrderCareObjectModel,
        OrderMatchModel,
        OrderModel,
        OrderOptionValueModel,
        OrderReportModel,
        OrderStatusHistoryModel,
    )
    from .order_queries import SqlAlchemyMyOrdersQueryService
    from .order_repositories import SqlAlchemyOrderRepository
    from .pricing_repositories import SqlAlchemyPricingRepository


__all__ = [
    "OrderCareObjectModel",
    "OrderAddressSnapshotModel",
    "OrderMatchModel",
    "OrderModel",
    "OrderOptionValueModel",
    "OrderStatusHistoryModel",
    "OrderReportModel",
    "SqlAlchemyMatchingRepository",
    "SqlAlchemyMyOrdersQueryService",
    "SqlAlchemyOrderRepository",
    "SqlAlchemyPricingRepository",
]


def __getattr__(name: str) -> Any:
    if name in {
        "OrderAddressSnapshotModel",
        "OrderCareObjectModel",
        "OrderMatchModel",
        "OrderModel",
        "OrderOptionValueModel",
        "OrderReportModel",
        "OrderStatusHistoryModel",
    }:
        from . import models

        return getattr(models, name)
    if name == "SqlAlchemyMatchingRepository":
        from .matching_repositories import SqlAlchemyMatchingRepository

        return SqlAlchemyMatchingRepository
    if name == "SqlAlchemyMyOrdersQueryService":
        from .order_queries import SqlAlchemyMyOrdersQueryService

        return SqlAlchemyMyOrdersQueryService
    if name == "SqlAlchemyOrderRepository":
        from .order_repositories import SqlAlchemyOrderRepository

        return SqlAlchemyOrderRepository
    if name == "SqlAlchemyPricingRepository":
        from .pricing_repositories import SqlAlchemyPricingRepository

        return SqlAlchemyPricingRepository
    raise AttributeError(name)
