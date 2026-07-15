"""API路由"""

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any, List, Optional
from ..services import get_skill_service, get_hotplug_service
from ..models.skill import SkillType, SkillStatus

router = APIRouter(prefix="/api/skill", tags=["skill"])

skill_service = get_skill_service()
hotplug_service = get_hotplug_service()


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "skill", workspace_id: str = "default"):
    """技能审计便捷函数"""
    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource="skill",
            user=user_id,
            service=service,
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


@router.post("/skills")
async def register_skill(
    name: str,
    skill_type: str,
    description: str = "",
    category: str = "general",
    tags: Optional[List[str]] = None,
    user=Depends(get_current_user)):
    """注册Skill"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.register_skill(
            name=name,
            skill_type=SkillType(skill_type),
            description=description,
            category=category,
            tags=tags
        )
        _audit("skill_register", _uid, "success", details={"name": name, "skill_type": skill_type})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_register_failed", _uid, "failure", str(e), details={"name": name, "skill_type": skill_type})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills")
async def list_skills(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    skill_type: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    name: Optional[str] = None,
    user=Depends(get_current_user)):
    """列出Skills（自动从 SKILL_CATALOG 同步）"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        filters = {}
        if skill_type:
            filters["type"] = skill_type
        if status:
            filters["status"] = status
        if category:
            filters["category"] = category
        if name:
            filters["name"] = name

        result = skill_service.list_skills(filters, page, page_size)
        _audit("skill_list", _uid, "success")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_list_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/loaded")
async def get_loaded_skills(user=Depends(get_current_user)):
    """获取已加载的Skills"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = {"skills": hotplug_service.get_loaded_skills()}
        _audit("skill_list_loaded", _uid, "success")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_list_loaded_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/by-name/{skill_name}")
async def get_skill_by_name(skill_name: str,
    user=Depends(get_current_user)):
    """通过名称获取Skill"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.get_skill_by_name(skill_name)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        _audit("skill_get_by_name", _uid, "success", details={"skill_name": skill_name})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_get_by_name_failed", _uid, "failure", str(e), details={"skill_name": skill_name})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str,
    user=Depends(get_current_user)):
    """获取Skill"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.get_skill(skill_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        _audit("skill_get", _uid, "success", details={"skill_id": skill_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_get_failed", _uid, "failure", str(e), details={"skill_id": skill_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/versions")
async def add_version(
    skill_id: str,
    version: str,
    implementation: str,
    schema: Optional[Dict[str, Any]] = None,
    changelog: str = "",
    user=Depends(get_current_user)):
    """添加版本"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.add_version(skill_id, version, implementation, schema, changelog)
        _audit("skill_add_version", _uid, "success", details={"skill_id": skill_id, "version": version})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_add_version_failed", _uid, "failure", str(e), details={"skill_id": skill_id, "version": version})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/activate")
async def activate_skill(skill_id: str,
    user=Depends(get_current_user)):
    """激活Skill"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.activate_skill(skill_id)
        _audit("skill_activate", _uid, "success", details={"skill_id": skill_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_activate_failed", _uid, "failure", str(e), details={"skill_id": skill_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/deactivate")
async def deactivate_skill(skill_id: str,
    user=Depends(get_current_user)):
    """停用Skill"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.deactivate_skill(skill_id)
        _audit("skill_deactivate", _uid, "success", details={"skill_id": skill_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_deactivate_failed", _uid, "failure", str(e), details={"skill_id": skill_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/load")
async def load_skill(skill_id: str, version: Optional[str] = None,
    user=Depends(get_current_user)):
    """加载Skill"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = hotplug_service.load_skill(skill_id, version)
        _audit("skill_load", _uid, "success", details={"skill_id": skill_id, "version": version})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_load_failed", _uid, "failure", str(e), details={"skill_id": skill_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/unload")
async def unload_skill(skill_id: str,
    user=Depends(get_current_user)):
    """卸载Skill"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = hotplug_service.unload_skill(skill_id)
        _audit("skill_unload", _uid, "success", details={"skill_id": skill_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_unload_failed", _uid, "failure", str(e), details={"skill_id": skill_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog")
async def get_catalog_info(user=Depends(get_current_user)):
    """获取 SKILL_CATALOG 同步信息"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.get_catalog_info()
        _audit("skill_catalog_get", _uid, "success")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_catalog_get_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_from_catalog(user=Depends(get_current_user)):
    """手动触发从 SKILL_CATALOG 同步"""
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.sync_from_catalog()
        _audit("skill_sync", _uid, "success")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_sync_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register")
async def register_skill_hotplug(
    name: str,
    skill_type: str,
    description: str = "",
    category: str = "general",
    tags: Optional[List[str]] = None,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.register_skill_hotplug(
            name=name,
            skill_type=SkillType(skill_type),
            description=description,
            category=category,
            tags=tags,
        )
        _audit("skill_register_hotplug", _uid, "success", details={"name": name, "skill_type": skill_type})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_register_hotplug_failed", _uid, "failure", str(e), details={"name": name, "skill_type": skill_type})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{skill_id}")
async def unregister_skill(skill_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.unregister_skill(skill_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        _audit("skill_unregister", _uid, "success", details={"skill_id": skill_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_unregister_failed", _uid, "failure", str(e), details={"skill_id": skill_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discover")
async def discover_skills(q: Optional[str] = None,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.discover_skills(query=q)
        _audit("skill_discover", _uid, "success")
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_discover_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}/status")
async def get_skill_lifecycle_status(skill_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.get_skill(skill_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        _audit("skill_status_get", _uid, "success", details={"skill_id": skill_id})
        return {
            "skill_id": result.get("skill_id"),
            "name": result.get("name"),
            "status": result.get("status"),
            "type": result.get("type"),
        }
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_status_get_failed", _uid, "failure", str(e), details={"skill_id": skill_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{skill_id}/lifecycle")
async def transition_lifecycle(skill_id: str, target_status: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = skill_service.transition_lifecycle(skill_id, target_status)
        if result.get("status") == "error":
            _audit("skill_lifecycle_transition_failed", _uid, "failure", result.get("message", ""),
                   details={"skill_id": skill_id, "target_status": target_status})
            raise HTTPException(status_code=400, detail=result.get("message"))
        _audit("skill_lifecycle_transition", _uid, "success",
               details={"skill_id": skill_id, "target_status": target_status})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_lifecycle_transition_failed", _uid, "failure", str(e),
               details={"skill_id": skill_id, "target_status": target_status})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_skill(
    request: Dict[str, Any],
    user=Depends(get_current_user)):
    """执行指定技能（通过 SkillManager.call_skill 调用）

    Body: {"skill_name": "xxx", "parameters": {...}}
    """
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        skill_name = request.get("skill_name")
        parameters = request.get("parameters", {})
        if not skill_name:
            raise HTTPException(status_code=400, detail="skill_name is required")

        import time as _time
        start_ms = _time.time() * 1000
        result = skill_service.call_skill(skill_name, parameters)
        elapsed_ms = _time.time() * 1000 - start_ms

        if result.get("status") == "error":
            status_code = 404 if "not found" in result.get("message", "") else 400
            _audit("skill_execute_failed", _uid, "failure", result.get("message", ""),
                   details={"skill_name": skill_name})
            raise HTTPException(status_code=status_code, detail=result.get("message"))

        # 统一输出格式
        is_placeholder = result.get("status") == "placeholder"
        _audit("skill_execute", _uid, "success",
               details={"skill_name": skill_name, "elapsed_ms": round(elapsed_ms, 1)})
        return {
            "success": not is_placeholder,
            "data": result,
            "error": result.get("message") if is_placeholder else None,
            "execution_time_ms": round(elapsed_ms, 1),
            "skill_name": skill_name,
            "placeholder": is_placeholder,
        }
    except HTTPException:
        raise
    except Exception as e:
        _audit("skill_execute_failed", _uid, "failure", str(e),
               details={"skill_name": request.get("skill_name", "")})
        raise HTTPException(status_code=500, detail=str(e))
