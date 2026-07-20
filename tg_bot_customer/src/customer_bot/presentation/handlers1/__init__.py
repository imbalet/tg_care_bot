from .addresses import router as addresses_router
from .care_objects import router as care_objects_router
from .category import router as category_router
from .menu import router as fallback_router
from .orders import router as orders_router
from .registration import router as registration_router
from .start import router as start_router

__all__ = [
    "care_objects_router",
    "category_router",
    "addresses_router",
    "fallback_router",
    "orders_router",
    "registration_router",
    "start_router",
]
