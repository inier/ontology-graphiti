"""TypeRegistry API 路由

统一类型定义读写入口，所有写入经 TypeRegistry → OntologyService → OMS 同步。
读取可从 OntologyService（本体作用域）或 OMS（平台作用域）获取。

路由前缀: /api/ontology/registry
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional

from odap.infra.security.jwt_auth import get_current_user
from ..type_registry import get_type_registry
from .schemas import (
    RegistryObjectTypeCreate, RegistryObjectTypeUpdate,
    RegistryActionTypeCreate, RegistryActionTypeUpdate,
    RegistryLinkTypeCreate, RegistryLinkTypeUpdate,
    RegistryCommitVersion,
)

router = APIRouter(prefix="/api/ontology/registry", tags=["ontology-registry"])


# ── Object Type ──

@router.post("/object-types")
async def create_object_type(
    data: RegistryObjectTypeCreate,
    user=Depends(get_current_user),
):
    """创建对象类型定义（经 TypeRegistry → OntologyService + OMS 同步）"""
    registry = get_type_registry()
    type_data = data.model_dump(exclude={"ontology_id"})
    result = registry.create_object_type(data.ontology_id, type_data)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))
    return result


@router.get("/ontologies/{ontology_id}/object-types")
async def list_object_types(
    ontology_id: str,
    user=Depends(get_current_user),
):
    """列出本体下的对象类型定义"""
    registry = get_type_registry()
    result = registry.list_object_types(ontology_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "查询失败"))
    return result


@router.get("/object-types/{type_id}")
async def get_object_type(
    type_id: str,
    user=Depends(get_current_user),
):
    """获取对象类型定义"""
    registry = get_type_registry()
    result = registry.get_object_type(type_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "未找到"))
    return result


@router.put("/object-types/{type_id}")
async def update_object_type(
    type_id: str,
    data: RegistryObjectTypeUpdate,
    user=Depends(get_current_user),
):
    """更新对象类型定义（经 TypeRegistry → OntologyService + OMS 同步）"""
    registry = get_type_registry()
    result = registry.update_object_type(type_id, data.model_dump(exclude_none=True))
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "更新失败"))
    return result


@router.delete("/object-types/{type_id}")
async def delete_object_type(
    type_id: str,
    user=Depends(get_current_user),
):
    """删除对象类型定义（经 TypeRegistry → OntologyService + OMS 同步）"""
    registry = get_type_registry()
    result = registry.delete_object_type(type_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "删除失败"))
    return result


# ── Link Type ──

@router.post("/link-types")
async def create_link_type(
    data: RegistryLinkTypeCreate,
    user=Depends(get_current_user),
):
    """创建关系类型定义"""
    registry = get_type_registry()
    link_data = data.model_dump(exclude={"ontology_id"})
    result = registry.create_link_type(data.ontology_id, link_data)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))
    return result


@router.get("/ontologies/{ontology_id}/link-types")
async def list_link_types(
    ontology_id: str,
    user=Depends(get_current_user),
):
    """列出本体下的关系类型定义"""
    registry = get_type_registry()
    result = registry.list_link_types(ontology_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "查询失败"))
    return result


@router.put("/link-types/{link_id}")
async def update_link_type(
    link_id: str,
    data: RegistryLinkTypeUpdate,
    user=Depends(get_current_user),
):
    """更新关系类型定义"""
    registry = get_type_registry()
    result = registry.update_link_type(link_id, data.model_dump(exclude_none=True))
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "更新失败"))
    return result


@router.delete("/link-types/{link_id}")
async def delete_link_type(
    link_id: str,
    user=Depends(get_current_user),
):
    """删除关系类型定义"""
    registry = get_type_registry()
    result = registry.delete_link_type(link_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "删除失败"))
    return result


# ── Action Type ──

@router.post("/action-types")
async def create_action_type(
    data: RegistryActionTypeCreate,
    user=Depends(get_current_user),
):
    """创建动作类型定义（经 TypeRegistry → OntologyService + OMS 同步）"""
    registry = get_type_registry()
    action_data = data.model_dump(exclude={"ontology_id"})
    result = registry.create_action_type(data.ontology_id, action_data)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "创建失败"))
    return result


@router.get("/ontologies/{ontology_id}/action-types")
async def list_action_types(
    ontology_id: str,
    user=Depends(get_current_user),
):
    """列出本体下的动作类型定义"""
    registry = get_type_registry()
    result = registry.list_action_types(ontology_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "查询失败"))
    return result


@router.put("/action-types/{action_type_id}")
async def update_action_type(
    action_type_id: str,
    data: RegistryActionTypeUpdate,
    user=Depends(get_current_user),
):
    """更新动作类型定义（经 TypeRegistry → OntologyService + OMS 同步）"""
    registry = get_type_registry()
    result = registry.update_action_type(action_type_id, data.model_dump(exclude_none=True))
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "更新失败"))
    return result


@router.delete("/action-types/{action_type_id}")
async def delete_action_type(
    action_type_id: str,
    user=Depends(get_current_user),
):
    """删除动作类型定义（经 TypeRegistry → OntologyService + OMS 同步）"""
    registry = get_type_registry()
    result = registry.delete_action_type(action_type_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message", "删除失败"))
    return result


# ── OMS 只读代理（平台作用域查询） ──

@router.get("/oms/object-types")
async def list_oms_object_types(
    active_only: bool = Query(True),
    user=Depends(get_current_user),
):
    """列出 OMS 缓存中的所有对象类型（平台作用域，只读）"""
    registry = get_type_registry()
    return registry.list_oms_object_types(active_only=active_only)


@router.get("/oms/object-types/{type_id}")
async def get_oms_object_type(
    type_id: str,
    user=Depends(get_current_user),
):
    """获取 OMS 缓存中的对象类型（只读）"""
    registry = get_type_registry()
    result = registry.get_oms_object_type(type_id)
    if not result:
        raise HTTPException(status_code=404, detail="对象类型不存在")
    return result


@router.get("/oms/action-types")
async def list_oms_action_types(
    target_type: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """列出 OMS 缓存中的所有动作类型（平台作用域，只读）"""
    registry = get_type_registry()
    return registry.list_oms_action_types(target_type=target_type)


@router.get("/oms/action-types/{action_type_id}")
async def get_oms_action_type(
    action_type_id: str,
    user=Depends(get_current_user),
):
    """获取 OMS 缓存中的动作类型（只读）"""
    registry = get_type_registry()
    result = registry.get_oms_action_type(action_type_id)
    if not result:
        raise HTTPException(status_code=404, detail="动作类型不存在")
    return result


# ── Schema Version ──

@router.post("/ontologies/{ontology_id}/commit")
async def commit_schema_version(
    ontology_id: str,
    data: RegistryCommitVersion,
    user=Depends(get_current_user),
):
    """提交 Schema 版本快照"""
    registry = get_type_registry()
    result = registry.commit_schema_version(ontology_id, data.changelog)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "提交失败"))
    return result


# ── 一致性验证 ──

@router.get("/ontologies/{ontology_id}/validate")
async def validate_consistency(
    ontology_id: str,
    user=Depends(get_current_user),
):
    """验证语义层与本体类型定义的一致性

    检查维度：
    - 本体存在性
    - 类型引用完整性（link_type / action_type 引用的类型是否已定义）
    - OMS 缓存与 OntologyService 数据一致性
    """
    registry = get_type_registry()
    result = registry.validate_consistency(ontology_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("issues", ["验证失败"]))
    return result
