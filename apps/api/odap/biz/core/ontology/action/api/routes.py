"""Action Type - FastAPI 路由 (T384)

前缀: /api/ontology/actions
端点：
- POST   /                        创建 ActionType
- GET    /                        列出 (query: enabled_only, object_type)
- GET    /{action_type_id}        获取
- PUT    /{action_type_id}        更新
- DELETE /{action_type_id}        删除
- POST   /{action_type_id}/execute  执行
- GET    /{action_type_id}/executions  执行历史
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services import ActionService
from .schemas import (
    CreateActionTypeRequest,
    ExecuteActionRequest,
    ListActionTypesResponse,
    ListExecutionsResponse,
    UpdateActionTypeRequest,
)


router = APIRouter(prefix="/api/ontology/actions", tags=["actions"])

# 模块级单例
action_service = ActionService()


@router.post("", response_model=ListActionTypesResponse)
async def create_action_type(request: CreateActionTypeRequest):
    """创建 ActionType"""
    try:
        result = action_service.create_action_type(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return {"action_types": [result], "count": 1}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ListActionTypesResponse)
async def list_action_types(
    enabled_only: bool = Query(False, description="仅返回启用的"),
    object_type: Optional[str] = Query(None, description="按适用 ObjectType 过滤"),
):
    """列出 ActionType"""
    try:
        result = action_service.list_action_types(
            enabled_only=enabled_only, object_type=object_type
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{action_type_id}")
async def get_action_type(action_type_id: str):
    """获取单条 ActionType"""
    try:
        result = action_service.get_action_type(action_type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{action_type_id}")
async def update_action_type(
    action_type_id: str, request: UpdateActionTypeRequest
):
    """更新 ActionType（部分字段）"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = action_service.update_action_type(action_type_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "not found" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{action_type_id}")
async def delete_action_type(action_type_id: str):
    """删除 ActionType"""
    try:
        result = action_service.delete_action_type(action_type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{action_type_id}/execute")
async def execute_action(
    action_type_id: str, request: ExecuteActionRequest
):
    """执行 ActionType"""
    try:
        result = action_service.execute_action(
            action_type_id=action_type_id,
            parameters=request.parameters,
            user_context=request.user_context,
        )
        if result.get("status") == "error":
            status_code = 404 if "not found" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{action_type_id}/executions", response_model=ListExecutionsResponse
)
async def list_executions(
    action_type_id: str,
    limit: int = Query(50, ge=1, le=500),
):
    """列出某 ActionType 的执行历史"""
    try:
        result = action_service.list_executions(action_type_id, limit=limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
