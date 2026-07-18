from fastapi import APIRouter

from .routes import router as warehouse_router

router = APIRouter()
router.include_router(warehouse_router)
