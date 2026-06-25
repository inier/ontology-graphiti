"""Ontology API 路由�?
遵循 AGENTS.md 规则�?- 路由前缀统一 /api/ontologies
- except HTTPException: raise 必须透传
- 服务层返�?Dict，路由层翻译错误�?HTTPException
- 类型定义写入操作代理�?TypeRegistry 统一入口，确�?OMS 缓存同步
- 所有路由操作均记录审计日志
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Response
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.security.audit_helper import audit, extract_user_id
from odap.infra.security.audit_helper import audit, extract_user_id
from typing import Optional

from ..services import OntologyService

router = APIRouter(prefix="/api/ontologies", tags=["ontology-api"])
service = OntologyService()

# TypeRegistry 延迟加载（避免循环导入）
_type_registry = None

def _get_type_registry():
    global _type_registry
    if _type_registry is None:
        from odap.biz.core.ontology.registry import get_type_registry
        _type_registry = get_type_registry()
    return _type_registry

# 写入操作弃用提示
_REGISTRY_HINT = "X-Registry-Recommended"
_REGISTRY_MSG = "建议使用 /api/ontology/registry/object-types 统一入口，确�?OMS 缓存同步"


def extract_user_id(user) -> str:
    """�?JWT user 对象提取用户标识"""
    return user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"


def audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "ontology", workspace_id: str = "default"):
    """本体审计便捷函数"""
    try:
        from odap.infra.security.unified_audit import log_audit
        logaudit(
            action=action,
            resource="ontology",
            user=user_id,
            service=service,
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


# ===== Ontology CRUD =====
@router.get("")
async def list_ontologies(
    workspace_id: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    uid = extract_user_id(user)
    try:
        return service.list_ontologies(workspace_id=workspace_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_list_failed", uid, "failure", str(e),
               details={"workspace_id": workspace_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ontology_id}")
async def get_ontology(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        result = service.get_ontology(ontology_id)
        if result.get("status") == "error":
            audit("ontology_get_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_get_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_ontology(data: dict, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    ws_id = data.get("workspace_id", "default")
    try:
        result = service.create_ontology(
            name=data.get("name", ""),
            description=data.get("description", ""),
            workspace_id=data.get("workspace_id", ""),
            scenario_id=data.get("scenario_id"),
        )
        if result.get("status") == "error":
            audit("ontology_create_failed", uid, "failure", result.get("message", ""),
                   details={"name": data.get("name")}, workspace_id=ws_id)
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_create", uid, "success", "Ontology created",
               details={"ontology_id": result.get("ontology_id"), "name": data.get("name")},
               workspace_id=ws_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_create_failed", uid, "failure", str(e),
               details={"name": data.get("name")}, workspace_id=ws_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{ontology_id}")
async def update_ontology(ontology_id: str, data: dict, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        result = service.update_ontology(ontology_id, data)
        if result.get("status") == "error":
            audit("ontology_update_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_update", uid, "success", "Ontology updated",
               details={"ontology_id": ontology_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_update_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{ontology_id}")
async def delete_ontology(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        result = service.delete_ontology(ontology_id)
        if result.get("status") == "error":
            audit("ontology_delete_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_delete", uid, "success", "Ontology deleted",
               details={"ontology_id": ontology_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_delete_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== Schema Version Management =====
@router.post("/{ontology_id}/commit")
async def commit_schema_version(ontology_id: str, data: dict, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        result = service.commit_schema_version(
            ontology_id=ontology_id,
            changelog=data.get("changelog", ""),
        )
        if result.get("status") == "error":
            audit("ontology_commit_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_commit", uid, "success", "Schema version committed",
               details={"ontology_id": ontology_id, "version_id": result.get("version_id")})
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_commit_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ontology_id}/versions")
async def list_schema_versions(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        return service.list_schema_versions(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_list_versions_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ontology_id}/diff")
async def diff_schema_versions(
    ontology_id: str,
    version_id_a: str = Query(...),
    version_id_b: str = Query(...),
    user=Depends(get_current_user),
):
    uid = extract_user_id(user)
    try:
        result = service.diff_schema_versions(ontology_id, version_id_a, version_id_b)
        if result.get("status") == "error":
            audit("ontology_diff_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "version_id_a": version_id_a, "version_id_b": version_id_b})
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_diff_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "version_id_a": version_id_a, "version_id_b": version_id_b})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/rollback")
async def rollback_schema_version(ontology_id: str, data: dict, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    target_version_id = data.get("target_version_id", "")
    try:
        result = service.rollback_schema_version(
            ontology_id=ontology_id,
            target_version_id=target_version_id,
        )
        if result.get("status") == "error":
            audit("ontology_rollback_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "target_version_id": target_version_id})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_rollback", uid, "success", "Schema version rolled back",
               details={"ontology_id": ontology_id, "target_version_id": target_version_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_rollback_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "target_version_id": target_version_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== ObjectType CRUD =====
@router.get("/{ontology_id}/object-types")
async def list_object_types(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        return service.list_object_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_object_type_list_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/object-types")
async def create_object_type(ontology_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        # 通过 TypeRegistry 统一写入，确�?OMS 缓存同步
        registry = _get_type_registry()
        result = registry.create_object_type(ontology_id, data)
        if result.get("status") == "error":
            audit("ontology_object_type_create_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "name": data.get("name")})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_object_type_create", uid, "success", "Object type created",
               details={"ontology_id": ontology_id, "type_id": result.get("type_id"), "name": data.get("name")})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_object_type_create_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "name": data.get("name")})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/object-types/{type_id}")
async def update_object_type(type_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        # 通过 TypeRegistry 统一更新，确�?OMS 缓存同步
        registry = _get_type_registry()
        result = registry.update_object_type(type_id, data)
        if result.get("status") == "error":
            audit("ontology_object_type_update_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_object_type_update", uid, "success", "Object type updated",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_object_type_update_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/object-types/{type_id}")
async def delete_object_type(type_id: str, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        # 通过 TypeRegistry 统一删除，确�?OMS 缓存同步
        registry = _get_type_registry()
        result = registry.delete_object_type(type_id)
        if result.get("status") == "error":
            audit("ontology_object_type_delete_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_object_type_delete", uid, "success", "Object type deleted",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_object_type_delete_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== LinkType CRUD =====
@router.get("/{ontology_id}/link-types")
async def list_link_types(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        return service.list_link_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_link_type_list_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/link-types")
async def create_link_type(ontology_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        # 通过 TypeRegistry 统一写入，确�?OMS 缓存同步
        registry = _get_type_registry()
        result = registry.create_link_type(ontology_id, data)
        if result.get("status") == "error":
            audit("ontology_link_type_create_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "name": data.get("name")})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_link_type_create", uid, "success", "Link type created",
               details={"ontology_id": ontology_id, "type_id": result.get("type_id"), "name": data.get("name")})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_link_type_create_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "name": data.get("name")})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/link-types/{link_id}")
async def update_link_type(link_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        # 通过 TypeRegistry 统一更新，确�?OMS 缓存同步
        registry = _get_type_registry()
        result = registry.update_link_type(link_id, data)
        if result.get("status") == "error":
            audit("ontology_link_type_update_failed", uid, "failure", result.get("message", ""),
                   details={"link_id": link_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_link_type_update", uid, "success", "Link type updated",
               details={"link_id": link_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_link_type_update_failed", uid, "failure", str(e),
               details={"link_id": link_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/link-types/{link_id}")
async def delete_link_type(link_id: str, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        # 通过 TypeRegistry 统一删除，确�?OMS 缓存同步
        registry = _get_type_registry()
        result = registry.delete_link_type(link_id)
        if result.get("status") == "error":
            audit("ontology_link_type_delete_failed", uid, "failure", result.get("message", ""),
                   details={"link_id": link_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_link_type_delete", uid, "success", "Link type deleted",
               details={"link_id": link_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_link_type_delete_failed", uid, "failure", str(e),
               details={"link_id": link_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== ActionType CRUD =====
@router.get("/{ontology_id}/action-types")
async def list_action_types(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        return service.list_action_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_action_type_list_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/action-types")
async def create_action_type(ontology_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        # 通过 TypeRegistry 统一写入，确�?OMS 缓存同步
        registry = _get_type_registry()
        result = registry.create_action_type(ontology_id, data)
        if result.get("status") == "error":
            audit("ontology_action_type_create_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "name": data.get("name")})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_action_type_create", uid, "success", "Action type created",
               details={"ontology_id": ontology_id, "type_id": result.get("type_id"), "name": data.get("name")})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_action_type_create_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "name": data.get("name")})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/action-types/{action_type_id}")
async def update_action_type(action_type_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        # 通过 TypeRegistry 统一更新，确�?OMS 缓存同步
        registry = _get_type_registry()
        result = registry.update_action_type(action_type_id, data)
        if result.get("status") == "error":
            audit("ontology_action_type_update_failed", uid, "failure", result.get("message", ""),
                   details={"action_type_id": action_type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_action_type_update", uid, "success", "Action type updated",
               details={"action_type_id": action_type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_action_type_update_failed", uid, "failure", str(e),
               details={"action_type_id": action_type_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/action-types/{action_type_id}")
async def delete_action_type(action_type_id: str, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        # 通过 TypeRegistry 统一删除，确�?OMS 缓存同步
        registry = _get_type_registry()
        result = registry.delete_action_type(action_type_id)
        if result.get("status") == "error":
            audit("ontology_action_type_delete_failed", uid, "failure", result.get("message", ""),
                   details={"action_type_id": action_type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_action_type_delete", uid, "success", "Action type deleted",
               details={"action_type_id": action_type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_action_type_delete_failed", uid, "failure", str(e),
               details={"action_type_id": action_type_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== ProcessType CRUD =====
@router.get("/{ontology_id}/process-types")
async def list_process_types(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        return service.list_process_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_process_type_list_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/process-types")
async def create_process_type(ontology_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.create_process_type(ontology_id, data)
        if result.get("status") == "error":
            audit("ontology_process_type_create_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "name": data.get("name")})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_process_type_create", uid, "success", "Process type created",
               details={"ontology_id": ontology_id, "type_id": result.get("type_id"), "name": data.get("name")})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_process_type_create_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "name": data.get("name")})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/process-types/{type_id}")
async def update_process_type(type_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.update_process_type(type_id, data)
        if result.get("status") == "error":
            audit("ontology_process_type_update_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_process_type_update", uid, "success", "Process type updated",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_process_type_update_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/process-types/{type_id}")
async def delete_process_type(type_id: str, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.delete_process_type(type_id)
        if result.get("status") == "error":
            audit("ontology_process_type_delete_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_process_type_delete", uid, "success", "Process type deleted",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_process_type_delete_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== RuleType CRUD =====
@router.get("/{ontology_id}/rule-types")
async def list_rule_types(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        return service.list_rule_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_rule_type_list_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/rule-types")
async def create_rule_type(ontology_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.create_rule_type(ontology_id, data)
        if result.get("status") == "error":
            audit("ontology_rule_type_create_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "name": data.get("name")})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_rule_type_create", uid, "success", "Rule type created",
               details={"ontology_id": ontology_id, "type_id": result.get("type_id"), "name": data.get("name")})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_rule_type_create_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "name": data.get("name")})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rule-types/{type_id}")
async def update_rule_type(type_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.update_rule_type(type_id, data)
        if result.get("status") == "error":
            audit("ontology_rule_type_update_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_rule_type_update", uid, "success", "Rule type updated",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_rule_type_update_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rule-types/{type_id}")
async def delete_rule_type(type_id: str, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.delete_rule_type(type_id)
        if result.get("status") == "error":
            audit("ontology_rule_type_delete_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_rule_type_delete", uid, "success", "Rule type deleted",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_rule_type_delete_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== FunctionType CRUD =====
@router.get("/{ontology_id}/function-types")
async def list_function_types(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        return service.list_function_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_function_type_list_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/function-types")
async def create_function_type(ontology_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.create_function_type(ontology_id, data)
        if result.get("status") == "error":
            audit("ontology_function_type_create_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "name": data.get("name")})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_function_type_create", uid, "success", "Function type created",
               details={"ontology_id": ontology_id, "type_id": result.get("type_id"), "name": data.get("name")})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_function_type_create_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "name": data.get("name")})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/function-types/{type_id}")
async def update_function_type(type_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.update_function_type(type_id, data)
        if result.get("status") == "error":
            audit("ontology_function_type_update_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_function_type_update", uid, "success", "Function type updated",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_function_type_update_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/function-types/{type_id}")
async def delete_function_type(type_id: str, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.delete_function_type(type_id)
        if result.get("status") == "error":
            audit("ontology_function_type_delete_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_function_type_delete", uid, "success", "Function type deleted",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_function_type_delete_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== IndicatorType CRUD =====
@router.get("/{ontology_id}/indicator-types")
async def list_indicator_types(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        return service.list_indicator_types(ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_indicator_type_list_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{ontology_id}/indicator-types")
async def create_indicator_type(ontology_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.create_indicator_type(ontology_id, data)
        if result.get("status") == "error":
            audit("ontology_indicator_type_create_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "name": data.get("name")})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_indicator_type_create", uid, "success", "Indicator type created",
               details={"ontology_id": ontology_id, "type_id": result.get("type_id"), "name": data.get("name")})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_indicator_type_create_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "name": data.get("name")})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/indicator-types/{type_id}")
async def update_indicator_type(type_id: str, data: dict, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.update_indicator_type(type_id, data)
        if result.get("status") == "error":
            audit("ontology_indicator_type_update_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_indicator_type_update", uid, "success", "Indicator type updated",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_indicator_type_update_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/indicator-types/{type_id}")
async def delete_indicator_type(type_id: str, response: Response, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        registry = _get_type_registry()
        result = registry.delete_indicator_type(type_id)
        if result.get("status") == "error":
            audit("ontology_indicator_type_delete_failed", uid, "failure", result.get("message", ""),
                   details={"type_id": type_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_indicator_type_delete", uid, "success", "Indicator type deleted",
               details={"type_id": type_id})
        response.headers[_REGISTRY_HINT] = _REGISTRY_MSG
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_indicator_type_delete_failed", uid, "failure", str(e),
               details={"type_id": type_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== Graph Data =====
@router.get("/{ontology_id}/graph")
async def get_ontology_graph(ontology_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        result = service.get_ontology_graph(ontology_id)
        if result.get("status") == "error":
            audit("ontology_graph_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_graph", uid, "success", "Ontology graph retrieved",
               details={"ontology_id": ontology_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_graph_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== Database Connection =====
@router.get("/database-connections")
async def list_database_connections(
    workspace_id: str = Query(...),
    user=Depends(get_current_user),
):
    uid = extract_user_id(user)
    try:
        return service.list_database_connections(workspace_id)
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_db_connection_list_failed", uid, "failure", str(e),
               details={"workspace_id": workspace_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/database-connections")
async def save_database_connection(data: dict, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    ws_id = data.get("workspace_id", "default")
    try:
        result = service.save_database_connection(data)
        if result.get("status") == "error":
            audit("ontology_db_connection_save_failed", uid, "failure", result.get("message", ""),
                   details={"name": data.get("name")}, workspace_id=ws_id)
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_db_connection_save", uid, "success", "Database connection saved",
               details={"connection_id": result.get("connection_id"), "name": data.get("name")},
               workspace_id=ws_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_db_connection_save_failed", uid, "failure", str(e),
               details={"name": data.get("name")}, workspace_id=ws_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/database-connections/{connection_id}")
async def delete_database_connection(connection_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        result = service.delete_database_connection(connection_id)
        if result.get("status") == "error":
            audit("ontology_db_connection_delete_failed", uid, "failure", result.get("message", ""),
                   details={"connection_id": connection_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_db_connection_delete", uid, "success", "Database connection deleted",
               details={"connection_id": connection_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_db_connection_delete_failed", uid, "failure", str(e),
               details={"connection_id": connection_id})
        raise HTTPException(status_code=500, detail=str(e))


# ===== Extraction Session =====
@router.post("/{ontology_id}/extraction-sessions")
async def create_extraction_session(ontology_id: str, data: dict, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        result = service.create_extraction_session(
            ontology_id=ontology_id,
            extraction_type=data.get("extraction_type", ""),
            input_data=data.get("input_data", {}),
        )
        if result.get("status") == "error":
            audit("ontology_extraction_create_failed", uid, "failure", result.get("message", ""),
                   details={"ontology_id": ontology_id, "extraction_type": data.get("extraction_type")})
            raise HTTPException(status_code=400, detail=result.get("message"))
        audit("ontology_extraction_create", uid, "success", "Extraction session created",
               details={"ontology_id": ontology_id, "session_id": result.get("session_id"),
                         "extraction_type": data.get("extraction_type")})
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_extraction_create_failed", uid, "failure", str(e),
               details={"ontology_id": ontology_id, "extraction_type": data.get("extraction_type")})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/extraction-sessions/{session_id}")
async def get_extraction_session(session_id: str, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        result = service.get_extraction_session(session_id)
        if result.get("status") == "error":
            audit("ontology_extraction_get_failed", uid, "failure", result.get("message", ""),
                   details={"session_id": session_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_extraction_get_failed", uid, "failure", str(e),
               details={"session_id": session_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/extraction-sessions/{session_id}")
async def update_extraction_session(session_id: str, data: dict, user=Depends(get_current_user)):
    uid = extract_user_id(user)
    try:
        result = service.update_extraction_session(session_id, data)
        if result.get("status") == "error":
            audit("ontology_extraction_update_failed", uid, "failure", result.get("message", ""),
                   details={"session_id": session_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        audit("ontology_extraction_update", uid, "success", "Extraction session updated",
               details={"session_id": session_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        audit("ontology_extraction_update_failed", uid, "failure", str(e),
               details={"session_id": session_id})
        raise HTTPException(status_code=500, detail=str(e))

