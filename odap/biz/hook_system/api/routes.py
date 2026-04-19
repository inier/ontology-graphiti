"""API路由"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from ..services.hook_service import HookService
from ..models.hook import HookType

router = APIRouter(prefix="/api/hook", tags=["hook"])

hook_service = HookService()


@router.post("/hooks")
async def register_hook(
    name: str,
    hook_type: str,
    script: str,
    description: str = "",
    language: str = "python"
):
    """注册Hook"""
    try:
        return hook_service.register_hook(
            name=name,
            hook_type=HookType(hook_type),
            script=script,
            description=description,
            language=language
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hooks/{hook_id}")
async def get_hook(hook_id: str):
    """获取Hook"""
    try:
        result = hook_service.get_hook(hook_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hooks/{hook_id}/execute")
async def execute_hook(hook_id: str, context: Optional[Dict[str, Any]] = None):
    """执行Hook"""
    try:
        return hook_service.execute_hook(hook_id, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hooks")
async def list_hooks(
    page: int = 1,
    page_size: int = 10,
    hook_type: Optional[str] = None
):
    """列出Hooks"""
    try:
        filters = {}
        if hook_type:
            filters["type"] = hook_type
        return hook_service.list_hooks(filters, page, page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
