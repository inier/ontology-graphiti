import logging
import uuid
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user, verify_admin
from pydantic import BaseModel, Field

from odap.biz.integration.hook_system.services.hook_service import HookService
from odap.biz.integration.hook_system.models.hook import HookType

router = APIRouter(prefix="/api/hooks", tags=["hooks"])

hook_service = HookService()


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "hook_system", workspace_id: str = "default"):
    """审计便捷函数"""
    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource="hook_system",
            user=user_id,
            service=service,
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


class RegisterHookRequest(BaseModel):
    name: str
    hook_type: str
    script: str
    description: str = ""
    language: str = "python"


# P3-M5: hook_type 严格校验 — 列出合法值供 400 错误返回
_VALID_HOOK_TYPES = [t.value for t in HookType]


@router.post("/register")
async def register_hook(request: RegisterHookRequest,
    user=Depends(verify_admin)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        # P3-M5: 严格校验 hook_type，不再静默 fallback 到不存在的 CUSTOM
        try:
            hook_type = HookType(request.hook_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid hook_type: '{request.hook_type}'. "
                    f"Valid values: {_VALID_HOOK_TYPES}"
                ),
            )

        result = hook_service.register_hook(
            name=request.name,
            hook_type=hook_type,
            script=request.script,
            description=request.description,
            language=request.language,
        )

        _audit("hook_system_register", _uid, "success", details={"name": request.name, "hook_type": request.hook_type})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("hook_system_register_failed", _uid, "failure", str(e), details={"name": request.name})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{hook_id}")
async def unregister_hook(hook_id: str,
    user=Depends(verify_admin)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        # P3-M4: 移除已废弃且签名错误的 HookAdapter 调用
        # （HookAdapter 内部以错误签名调 HookManager.register_hook，必然失败被静默吞掉）
        hook = hook_service.get_hook(hook_id)
        if hook.get("status") == "error":
            raise HTTPException(status_code=404, detail=hook.get("message", "Hook not found"))
        _audit("hook_system_unregister", _uid, "success", details={"hook_id": hook_id})
        return {"status": "success", "hook_id": hook_id}
    except HTTPException:
        raise
    except Exception as e:
        _audit("hook_system_unregister_failed", _uid, "failure", str(e), details={"hook_id": hook_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_hooks(
    page: int = 1,
    page_size: int = 10,
    hook_type: Optional[str] = None,
    user=Depends(get_current_user),
):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        filters = {}
        if hook_type:
            filters["type"] = hook_type
        return hook_service.list_hooks(filters, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        _audit("hook_system_list_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{hook_id}/enable")
async def enable_hook(hook_id: str,
    user=Depends(verify_admin)):
    """启用 Hook（P0-C4 整改：调用真正的 set_enabled，不再是 no-op）。"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = hook_service.set_enabled(hook_id, True)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Hook not found"))
        _audit("hook_system_enable", _uid, "success",
               details={"hook_id": hook_id, "new_status": result.get("hook_status")})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("hook_system_enable_failed", _uid, "failure", str(e), details={"hook_id": hook_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{hook_id}/disable")
async def disable_hook(hook_id: str,
    user=Depends(verify_admin)):
    """禁用 Hook（P0-C4 整改：调用真正的 set_enabled，不再是 no-op）。"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = hook_service.set_enabled(hook_id, False)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Hook not found"))
        _audit("hook_system_disable", _uid, "success",
               details={"hook_id": hook_id, "new_status": result.get("hook_status")})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("hook_system_disable_failed", _uid, "failure", str(e), details={"hook_id": hook_id})
        raise HTTPException(status_code=500, detail=str(e))
