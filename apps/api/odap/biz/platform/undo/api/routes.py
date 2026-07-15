"""撤销/重做 API路由"""

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user

from ..services.operation_history_service import OperationHistoryService
from ..services.undo_service import UndoService

router = APIRouter(prefix="/api/undo", tags=["undo"])

# 服务实例
history_service = OperationHistoryService()
undo_service = UndoService(history_service=history_service)


@router.get("/history")
async def get_operation_history(
    workspace_id: str = Query(..., description="工作空间ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user)):
    """获取操作历史"""
    try:
        result = history_service.get_history(workspace_id, page, page_size)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{operation_id}/undo")
async def undo_operation(operation_id: str,
    user=Depends(get_current_user)):
    """撤销操作"""
    try:
        result = undo_service.undo(operation_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{operation_id}/redo")
async def redo_operation(operation_id: str,
    user=Depends(get_current_user)):
    """重做操作"""
    try:
        result = undo_service.redo(operation_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/undoable")
async def get_undoable_operations(
    workspace_id: str = Query(..., description="工作空间ID"),
    user=Depends(get_current_user)):
    """获取可撤销的操作列表"""
    try:
        result = undo_service.get_undoable_operations(workspace_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/redoable")
async def get_redoable_operations(
    workspace_id: str = Query(..., description="工作空间ID"),
    user=Depends(get_current_user)):
    """获取可重做的操作列表"""
    try:
        result = undo_service.get_redoable_operations(workspace_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_old_records(
    days: int = Query(30, ge=1, description="保留天数"),
    user=Depends(get_current_user)):
    """清理过期操作历史"""
    try:
        deleted = history_service.cleanup_old_records(days)
        return {"status": "success", "deleted_count": deleted}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
