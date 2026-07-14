from aiogram import Router

from .create import router as create_router
from .publish import router as publish_router

router = Router(name="orders")
router.include_router(create_router)
router.include_router(publish_router)

__all__ = ["router"]
