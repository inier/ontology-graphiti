"""API路由"""

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any, List, Optional
from ..services import get_skill_service, get_hotplug_service
from ..models.skill import SkillType, SkillStatus

router = APIRouter(prefix="/api/skill", tags=["skill"])

skill_service = get_skill_service()
hotplug_service = get_hotplug_service()


@router.post("/skills")
async def register_skill(
    name: str,
    skill_type: str,
    description: str = "",
    category: str = "general",
    tags: Optional[List[str]] = None,
    user=Depends(get_current_user)):
    """注册Skill"""
    try:
        return skill_service.register_skill(
            name=name,
            skill_type=SkillType(skill_type),
            description=description,
            category=category,
            tags=tags
        )
    except HTTPException:
        raise
    except Exception as e:
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

        return skill_service.list_skills(filters, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/loaded")
async def get_loaded_skills(user=Depends(get_current_user)):
    """获取已加载的Skills"""
    try:
        return {"skills": hotplug_service.get_loaded_skills()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/by-name/{skill_name}")
async def get_skill_by_name(skill_name: str,
    user=Depends(get_current_user)):
    """通过名称获取Skill"""
    try:
        result = skill_service.get_skill_by_name(skill_name)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str,
    user=Depends(get_current_user)):
    """获取Skill"""
    try:
        result = skill_service.get_skill(skill_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
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
    try:
        return skill_service.add_version(skill_id, version, implementation, schema, changelog)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/activate")
async def activate_skill(skill_id: str,
    user=Depends(get_current_user)):
    """激活Skill"""
    try:
        return skill_service.activate_skill(skill_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/deactivate")
async def deactivate_skill(skill_id: str,
    user=Depends(get_current_user)):
    """停用Skill"""
    try:
        return skill_service.deactivate_skill(skill_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/load")
async def load_skill(skill_id: str, version: Optional[str] = None,
    user=Depends(get_current_user)):
    """加载Skill"""
    try:
        return hotplug_service.load_skill(skill_id, version)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/unload")
async def unload_skill(skill_id: str,
    user=Depends(get_current_user)):
    """卸载Skill"""
    try:
        return hotplug_service.unload_skill(skill_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog")
async def get_catalog_info(user=Depends(get_current_user)):
    """获取 SKILL_CATALOG 同步信息"""
    try:
        return skill_service.get_catalog_info()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_from_catalog(user=Depends(get_current_user)):
    """手动触发从 SKILL_CATALOG 同步"""
    try:
        return skill_service.sync_from_catalog()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register")
async def register_skill_hotplug(
    name: str,
    skill_type: str,
    description: str = "",
    category: str = "general",
    tags: Optional[List[str]] = None,
    user=Depends(get_current_user)):
    try:
        return skill_service.register_skill_hotplug(
            name=name,
            skill_type=SkillType(skill_type),
            description=description,
            category=category,
            tags=tags,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{skill_id}")
async def unregister_skill(skill_id: str,
    user=Depends(get_current_user)):
    try:
        result = skill_service.unregister_skill(skill_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/discover")
async def discover_skills(q: Optional[str] = None,
    user=Depends(get_current_user)):
    try:
        return skill_service.discover_skills(query=q)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{skill_id}/status")
async def get_skill_lifecycle_status(skill_id: str,
    user=Depends(get_current_user)):
    try:
        result = skill_service.get_skill(skill_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return {
            "skill_id": result.get("skill_id"),
            "name": result.get("name"),
            "status": result.get("status"),
            "type": result.get("type"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{skill_id}/lifecycle")
async def transition_lifecycle(skill_id: str, target_status: str,
    user=Depends(get_current_user)):
    try:
        result = skill_service.transition_lifecycle(skill_id, target_status)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_skill(
    request: Dict[str, Any],
    user=Depends(get_current_user)):
    """执行指定技能（通过 SkillManager.call_skill 调用）

    Body: {"skill_name": "xxx", "parameters": {...}}
    """
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
            raise HTTPException(status_code=status_code, detail=result.get("message"))

        # 统一输出格式
        is_placeholder = result.get("status") == "placeholder"
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
        raise HTTPException(status_code=500, detail=str(e))
