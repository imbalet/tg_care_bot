__all__: list[str] = []
from .fallback import router as fallback_router
from .registration import router as registration_router
from .start import router as start_router

__all__ = ["fallback_router", "registration_router", "start_router"]
