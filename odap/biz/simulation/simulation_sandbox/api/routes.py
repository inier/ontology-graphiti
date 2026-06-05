from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any, Optional

from ..services.sandbox_service import SandboxService

router = APIRouter(prefix="/api/simulation/sandbox", tags=["simulation-sandbox"])

sandbox_service = SandboxService()


@router.post("")
async def create_sandbox(config: Dict[str, Any] = None,
    user=Depends(get_current_user)):
    try:
        result = sandbox_service.create_sandbox(config or {})
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sandbox_id}/run")
async def run_simulation(sandbox_id: str, params: Dict[str, Any] = None,
    user=Depends(get_current_user)):
    try:
        result = await sandbox_service.run_simulation(sandbox_id, params or {})
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        if result.get("status") == "timeout":
            return result
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sandbox_id}/status")
async def get_sandbox_status(sandbox_id: str,
    user=Depends(get_current_user)):
    try:
        result = sandbox_service.get_sandbox_status(sandbox_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{sandbox_id}/results")
async def get_sandbox_results(sandbox_id: str,
    user=Depends(get_current_user)):
    try:
        result = sandbox_service.get_sandbox_results(sandbox_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{sandbox_id}")
async def destroy_sandbox(sandbox_id: str,
    user=Depends(get_current_user)):
    try:
        result = sandbox_service.destroy_sandbox(sandbox_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{sandbox_id}/export")
async def export_results(sandbox_id: str, body: Optional[Dict[str, Any]] = None,
    user=Depends(get_current_user)):
    try:
        approved_by = (body or {}).get("approved_by", "")
        result = sandbox_service.export_results(sandbox_id, approved_by)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_sandboxes(workspace_id: str = None,
    user=Depends(get_current_user)):
    try:
        return {"sandboxes": sandbox_service.list_sandboxes(workspace_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
