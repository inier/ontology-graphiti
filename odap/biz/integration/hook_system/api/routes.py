import logging
import uuid
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from odap.biz.integration.hook_system.services.hook_service import HookService
from odap.biz.integration.hook_system.models.hook import HookType

router = APIRouter(prefix="/api/hooks", tags=["hooks"])

hook_service = HookService()


class RegisterHookRequest(BaseModel):
    name: str
    hook_type: str
    script: str
    description: str = ""
    language: str = "python"
    phase: str = "post"
    priority: int = 100


class EnableHookRequest(BaseModel):
    hook_id: str


@router.post("/register")
async def register_hook(request: RegisterHookRequest):
    try:
        try:
            hook_type = HookType(request.hook_type)
        except ValueError:
            hook_type = HookType.CUSTOM

        result = hook_service.register_hook(
            name=request.name,
            hook_type=hook_type,
            script=request.script,
            description=request.description,
            language=request.language,
        )

        try:
            from odap.biz.integration.openharness_agent.adapter.hook_adapter import HookAdapter
            adapter = HookAdapter()
            if request.phase == "pre":
                adapter.register_pre_hook(
                    event_type=request.name,
                    handler=lambda ctx: ctx,
                    priority=request.priority,
                )
            else:
                adapter.register_post_hook(
                    event_type=request.name,
                    handler=lambda ctx: ctx,
                    priority=request.priority,
                )
        except Exception as e:
            logging.getLogger(__name__).debug("Hook adapter registration fallback: %s", e)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{hook_id}")
async def unregister_hook(hook_id: str):
    try:
        try:
            from odap.biz.integration.openharness_agent.adapter.hook_adapter import HookAdapter
            adapter = HookAdapter()
            adapter.unregister_hook(hook_id)
        except Exception:
            pass

        hook = hook_service.get_hook(hook_id)
        if hook.get("status") == "error":
            raise HTTPException(status_code=404, detail=hook.get("message", "Hook not found"))
        return {"status": "success", "hook_id": hook_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_hooks(
    page: int = 1,
    page_size: int = 10,
    hook_type: Optional[str] = None,
):
    try:
        filters = {}
        if hook_type:
            filters["type"] = hook_type
        return hook_service.list_hooks(filters, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{hook_id}/enable")
async def enable_hook(hook_id: str):
    try:
        hook = hook_service.get_hook(hook_id)
        if hook.get("status") == "error":
            raise HTTPException(status_code=404, detail=hook.get("message", "Hook not found"))
        return {"status": "success", "hook_id": hook_id, "enabled": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{hook_id}/disable")
async def disable_hook(hook_id: str):
    try:
        hook = hook_service.get_hook(hook_id)
        if hook.get("status") == "error":
            raise HTTPException(status_code=404, detail=hook.get("message", "Hook not found"))
        return {"status": "success", "hook_id": hook_id, "enabled": False}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
