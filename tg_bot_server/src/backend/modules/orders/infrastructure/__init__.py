from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .persistence import (
        OrderAddressSnapshotModel,
        OrderCareObjectModel,
        OrderMatchModel,
        OrderModel,
        OrderOptionValueModel,
        OrderReportModel,
        OrderStatusHistoryModel,
        SqlAlchemyMatchingRepository,
        SqlAlchemyMyOrdersQueryService,
        SqlAlchemyOrderRepository,
        SqlAlchemyPricingRepository,
    )


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
    if name in __all__:
        from . import persistence

        return getattr(persistence, name)
    raise AttributeError(name)
