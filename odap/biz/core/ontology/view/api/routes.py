"""Object View - FastAPI 路由 (T411)

前缀: /api/ontology/views
端点:
- POST   /                       创建视图
- GET    /                       列出视图（query: base_type, role）
- GET    /{view_id}              获取视图
- PUT    /{view_id}              更新视图
- DELETE /{view_id}              删除视图
- POST   /{view_id}/query        查询（body: {user_id, ws_id, role}）
- POST   /{view_id}/permissions  添加/更新权限
- GET    /{view_id}/permissions  列出权限
- DELETE /permissions/{perm_id}  删除权限
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services import ViewService
from .schemas import (
    AttachPermissionRequest,
    CreateViewRequest,
    ListPermissionsResponse,
    ListViewsResponse,
    QueryViewRequest,
    QueryViewResponse,
    UpdateViewRequest,
    ViewResponse,
)


router = APIRouter(prefix="/api/ontology/views", tags=["object-views"])

# 模块级单例
view_service = ViewService()


@router.post("", response_model=ViewResponse)
async def create_view(request: CreateViewRequest):
    """创建视图"""
    try:
        result = view_service.create_view(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ListViewsResponse)
async def list_views(
    base_type: Optional[str] = Query(None, description="按 base_type_id 过滤"),
    role: Optional[str] = Query(None, description="按角色名过滤"),
):
    """列出视图"""
    try:
        result = view_service.list_views(base_type=base_type, role=role)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{view_id}", response_model=ViewResponse)
async def get_view(view_id: str):
    """获取单条视图"""
    try:
        result = view_service.get_view(view_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{view_id}", response_model=ViewResponse)
async def update_view(view_id: str, request: UpdateViewRequest):
    """更新视图（部分字段）"""
    try:
        payload = {k: v for k, v in request.model_dump().items() if v is not None}
        result = view_service.update_view(view_id, payload)
        if result.get("status") == "error":
            status_code = 404 if "not found" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{view_id}")
async def delete_view(view_id: str):
    """删除视图"""
    try:
        result = view_service.delete_view(view_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{view_id}/query", response_model=QueryViewResponse)
async def query_view(view_id: str, request: QueryViewRequest):
    """执行视图查询"""
    try:
        result = view_service.query_view(view_id, request.model_dump())
        if result.get("status") == "error":
            message = result["message"]
            if "denied" in message.lower() or "opa" in message.lower():
                raise HTTPException(status_code=403, detail=message)
            if "not found" in message:
                raise HTTPException(status_code=404, detail=message)
            raise HTTPException(status_code=400, detail=message)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{view_id}/permissions", response_model=ListPermissionsResponse
)
async def attach_permission(
    view_id: str, request: AttachPermissionRequest
):
    """添加/更新视图角色权限（含 redaction_rules）"""
    try:
        result = view_service.attach_permission(view_id, request.model_dump())
        if result.get("status") == "error":
            status_code = 404 if "not found" in result["message"] else 400
            raise HTTPException(status_code=status_code, detail=result["message"])
        perms = view_service.get_permissions(view_id)
        return perms
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{view_id}/permissions", response_model=ListPermissionsResponse
)
async def list_permissions(view_id: str):
    """列出视图的全部权限"""
    try:
        result = view_service.get_permissions(view_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/permissions/{perm_id}")
async def detach_permission(perm_id: str):
    """删除权限"""
    try:
        result = view_service.detach_permission(perm_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
