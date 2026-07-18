__all__: list[str] = []
from .addresses import router as addresses_router
from .avatar import router as avatar_router
from .category import router as category_router
from .fallback import router as fallback_router
from .registration import router as registration_router
from .services_calendar import router as services_calendar_router
from .start import router as start_router

__all__ = [
    "addresses_router",
    "avatar_router",
    "category_router",
    "fallback_router",
    "registration_router",
    "services_calendar_router",
    "start_router",
]
