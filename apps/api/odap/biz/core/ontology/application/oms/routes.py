"""OMS 路由层

读取操作直接使用 OMS 缓存（只读），写入操作代理到 TypeRegistry。

当请求携带 ontology_id 时，写入经 TypeRegistry → OntologyService → OMS 同步。
当未携带 ontology_id 时，降级为直接写入 OMS（向后兼容，已弃用）。
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from odap.infra.security.jwt_auth import get_current_user
from typing import List, Optional

from .schemas import (
    ObjectTypeDefinition, OntologySchemaCreate, OntologySchemaUpdate,
    ActionTypeDefinition, ActionTypeCreate, ActionTypeUpdate,
)
from .services import get_oms_service

router = APIRouter(prefix="/api/ontology/oms", tags=["ontology-metadata"])

_DEPRECATION_MSG = "OMS 写入接口已弃用，请使用 /api/ontology/registry/* 端点"


def _deprecation_response(data, status_code=200):
    """添加弃用警告头的响应"""
    resp = JSONResponse(content=data, status_code=status_code)
    resp.headers["X-Deprecation-Notice"] = _DEPRECATION_MSG
    return resp


# ── Object Type 读取（OMS 只读缓存） ──

@router.get("/object-types", response_model=List[ObjectTypeDefinition])
async def list_object_types(active_only: bool = Query(True),
    user=Depends(get_current_user)):
    return get_oms_service().list_object_types(active_only=active_only)


@router.get("/object-types/{type_id}", response_model=ObjectTypeDefinition)
async def get_object_type(type_id: str,
    user=Depends(get_current_user)):
    obj = get_oms_service().get_object_type(type_id)
    if not obj:
        raise HTTPException(status_code=404, detail="对象类型不存在")
    return obj


# ── Object Type 写入（代理到 TypeRegistry） ──

@router.post("/object-types")
async def create_object_type(
    data: OntologySchemaCreate,
    ontology_id: Optional[str] = Query(None, description="所属本体 ID（推荐使用 Registry API）"),
    user=Depends(get_current_user),
):
    """创建对象类型。推荐使用 /api/ontology/registry/object-types"""
    if ontology_id:
        from odap.biz.core.ontology.registry import get_type_registry
        registry = get_type_registry()
        type_data = data.model_dump()
        result = registry.create_object_type(ontology_id, type_data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))
        return result
    # 向后兼容：直接写入 OMS（已弃用）
    result = get_oms_service().create_object_type(data.model_dump())
    return _deprecation_response(result)


@router.put("/object-types/{type_id}")
async def update_object_type(
    type_id: str,
    data: OntologySchemaUpdate,
    ontology_id: Optional[str] = Query(None, description="所属本体 ID（推荐使用 Registry API）"),
    user=Depends(get_current_user),
):
    """更新对象类型。推荐使用 /api/ontology/registry/object-types/{type_id}"""
    if ontology_id:
        from odap.biz.core.ontology.registry import get_type_registry
        registry = get_type_registry()
        result = registry.update_object_type(type_id, data.model_dump(exclude_none=True))
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "更新失败"))
        return result
    # 向后兼容
    updated = get_oms_service().update_object_type(type_id, data.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="对象类型不存在")
    return _deprecation_response(updated)


@router.delete("/object-types/{type_id}")
async def delete_object_type(
    type_id: str,
    ontology_id: Optional[str] = Query(None, description="所属本体 ID（推荐使用 Registry API）"),
    user=Depends(get_current_user),
):
    """删除对象类型。推荐使用 /api/ontology/registry/object-types/{type_id}"""
    if ontology_id:
        from odap.biz.core.ontology.registry import get_type_registry
        registry = get_type_registry()
        result = registry.delete_object_type(type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "删除失败"))
        return result
    # 向后兼容
    success = get_oms_service().delete_object_type(type_id)
    if not success:
        raise HTTPException(status_code=404, detail="对象类型不存在")
    return _deprecation_response({"message": "对象类型删除成功"})


# ── Action Type 读取（OMS 只读缓存） ──

@router.get("/action-types", response_model=List[ActionTypeDefinition])
async def list_action_types(target_type: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    return get_oms_service().list_action_types(target_type=target_type)


@router.get("/action-types/{action_type_id}", response_model=ActionTypeDefinition)
async def get_action_type(action_type_id: str,
    user=Depends(get_current_user)):
    act = get_oms_service().get_action_type(action_type_id)
    if not act:
        raise HTTPException(status_code=404, detail="动作类型不存在")
    return act


# ── Action Type 写入（代理到 TypeRegistry） ──

@router.post("/action-types")
async def create_action_type(
    data: ActionTypeCreate,
    ontology_id: Optional[str] = Query(None, description="所属本体 ID（推荐使用 Registry API）"),
    user=Depends(get_current_user),
):
    """创建动作类型。推荐使用 /api/ontology/registry/action-types"""
    if ontology_id:
        from odap.biz.core.ontology.registry import get_type_registry
        registry = get_type_registry()
        action_data = data.model_dump()
        result = registry.create_action_type(ontology_id, action_data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))
        return result
    # 向后兼容
    result = get_oms_service().create_action_type(data.model_dump())
    return _deprecation_response(result)


@router.put("/action-types/{action_type_id}")
async def update_action_type(
    action_type_id: str,
    data: ActionTypeUpdate,
    ontology_id: Optional[str] = Query(None, description="所属本体 ID（推荐使用 Registry API）"),
    user=Depends(get_current_user),
):
    """更新动作类型。推荐使用 /api/ontology/registry/action-types/{action_type_id}"""
    if ontology_id:
        from odap.biz.core.ontology.registry import get_type_registry
        registry = get_type_registry()
        result = registry.update_action_type(action_type_id, data.model_dump(exclude_none=True))
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "更新失败"))
        return result
    # 向后兼容
    updated = get_oms_service().update_action_type(action_type_id, data.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="动作类型不存在")
    return _deprecation_response(updated)


@router.delete("/action-types/{action_type_id}")
async def delete_action_type(
    action_type_id: str,
    ontology_id: Optional[str] = Query(None, description="所属本体 ID（推荐使用 Registry API）"),
    user=Depends(get_current_user),
):
    """删除动作类型。推荐使用 /api/ontology/registry/action-types/{action_type_id}"""
    if ontology_id:
        from odap.biz.core.ontology.registry import get_type_registry
        registry = get_type_registry()
        result = registry.delete_action_type(action_type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "删除失败"))
        return result
    # 向后兼容
    success = get_oms_service().delete_action_type(action_type_id)
    if not success:
        raise HTTPException(status_code=404, detail="动作类型不存在")
    return _deprecation_response({"message": "动作类型删除成功"})


# ── Binding（代理到 TypeRegistry） ──

@router.post("/object-types/{type_id}/actions/{action_type_id}")
async def bind_action(type_id: str, action_type_id: str,
    user=Depends(get_current_user)):
    success = get_oms_service().bind_action_to_object_type(type_id, action_type_id)
    if not success:
        raise HTTPException(status_code=400, detail="绑定失败，请检查对象类型和动作类型是否存在")
    return _deprecation_response({"message": "绑定成功"})


@router.delete("/object-types/{type_id}/actions/{action_type_id}")
async def unbind_action(type_id: str, action_type_id: str,
    user=Depends(get_current_user)):
    success = get_oms_service().unbind_action_from_object_type(type_id, action_type_id)
    if not success:
        raise HTTPException(status_code=400, detail="解绑失败")
    return _deprecation_response({"message": "解绑成功"})
