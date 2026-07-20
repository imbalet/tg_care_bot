from .addresses import router as addresses_router
from .care_objects import router as care_objects_router
from .category import router as category_router
from .customer_orders import router as customer_orders_router
from .menu import router as fallback_router
from .orders import router as orders_router
from .profile import router as profile_router
from .registration import router as registration_router
from .start import router as start_router

__all__ = [
    "care_objects_router",
    "category_router",
    "customer_orders_router",
    "addresses_router",
    "fallback_router",
    "orders_router",
    "profile_router",
    "registration_router",
    "start_router",
]
