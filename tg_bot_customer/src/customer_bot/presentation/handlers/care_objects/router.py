from aiogram import Router

from .create import router as create_router
from .edit import router as edit_router
from .list import router as list_router

router = Router(name="care_objects")
router.include_router(list_router)
router.include_router(create_router)
router.include_router(edit_router)

__all__ = ["router"]
