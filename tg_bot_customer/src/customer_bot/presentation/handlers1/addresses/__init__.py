from aiogram import Router

from .create import router as create_router
from .list import router as list_router

router = Router(name="addresses")
router.include_router(list_router)
router.include_router(create_router)

__all__ = ["router"]
