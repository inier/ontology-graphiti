from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.security.audit_helper import audit as _audit_shared
from typing import Dict, Any, Optional

from ..services.sandbox_service import SandboxService

router = APIRouter(prefix="/api/simulation/sandbox", tags=["simulation-sandbox"])

sandbox_service = SandboxService()


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "simulation", workspace_id: str = "default"):
    """仿真审计便捷函数 - 使用共享 helper"""
    _audit_shared(
        action=action,
        user=user_id,
        result_status=result_status,
        result_message=result_message,
        details=details,
        service=service,
        workspace_id=workspace_id,
        resource="simulation",
    )


@router.post("")
async def create_sandbox(config: Dict[str, Any] = None,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = sandbox_service.create_sandbox(config or {})
        if result.get("status") == "error":
            _audit("sandbox_create_failed", _uid, "failure", result.get("message", ""))
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        _audit("sandbox_create", _uid, "success", details={"sandbox_id": result.get("sandbox_id", "")})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("sandbox_create_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sandbox_id}/run")
async def run_simulation(sandbox_id: str, params: Dict[str, Any] = None,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = await sandbox_service.run_simulation(sandbox_id, params or {})
        if result.get("status") == "error":
            _audit("sandbox_run_failed", _uid, "failure", result.get("message", ""),
                   details={"sandbox_id": sandbox_id})
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        _audit("sandbox_run", _uid, "success", details={"sandbox_id": sandbox_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("sandbox_run_failed", _uid, "failure", str(e), details={"sandbox_id": sandbox_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sandbox_id}/status")
async def get_sandbox_status(sandbox_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = sandbox_service.get_sandbox_status(sandbox_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        _audit("sandbox_get_status", _uid, "success", details={"sandbox_id": sandbox_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("sandbox_get_status_failed", _uid, "failure", str(e), details={"sandbox_id": sandbox_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sandbox_id}/results")
async def get_sandbox_results(sandbox_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = sandbox_service.get_sandbox_results(sandbox_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        _audit("sandbox_get_results", _uid, "success", details={"sandbox_id": sandbox_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("sandbox_get_results_failed", _uid, "failure", str(e), details={"sandbox_id": sandbox_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{sandbox_id}")
async def destroy_sandbox(sandbox_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = sandbox_service.destroy_sandbox(sandbox_id)
        if result.get("status") == "error":
            _audit("sandbox_destroy_failed", _uid, "failure", result.get("message", ""),
                   details={"sandbox_id": sandbox_id})
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        _audit("sandbox_destroy", _uid, "success", details={"sandbox_id": sandbox_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("sandbox_destroy_failed", _uid, "failure", str(e), details={"sandbox_id": sandbox_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sandbox_id}/export")
async def export_results(sandbox_id: str, body: Optional[Dict[str, Any]] = None,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        approved_by = (body or {}).get("approved_by", "")
        result = sandbox_service.export_results(sandbox_id, approved_by)
        if result.get("status") == "error":
            _audit("sandbox_export_failed", _uid, "failure", result.get("message", ""),
                   details={"sandbox_id": sandbox_id})
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        _audit("sandbox_export", _uid, "success", details={"sandbox_id": sandbox_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("sandbox_export_failed", _uid, "failure", str(e), details={"sandbox_id": sandbox_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_sandboxes(workspace_id: str = None,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = {"sandboxes": sandbox_service.list_sandboxes(workspace_id)}
        _audit("sandbox_list", _uid, "success", workspace_id=workspace_id or "default")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("sandbox_list_failed", _uid, "failure", str(e), workspace_id=workspace_id or "default")
        raise HTTPException(status_code=500, detail=str(e))
