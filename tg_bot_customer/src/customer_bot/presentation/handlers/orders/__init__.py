from aiogram import Router

from .additions import router as additions_router
from .create import router as create_router
from .matches import router as matches_router
from .objects_options import router as objects_options_router
from .publish import router as publish_router

router = Router(name="orders")
router.include_router(additions_router)
router.include_router(create_router)
router.include_router(objects_options_router)
router.include_router(publish_router)
router.include_router(matches_router)

__all__ = ["router"]
