"""API路由"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from ..services.skill_service import SkillService
from ..services.hotplug_service import HotplugService
from ..models.skill import SkillType, SkillStatus

router = APIRouter(prefix="/api/skill", tags=["skill"])

skill_service = SkillService()
hotplug_service = HotplugService()


@router.post("/skills")
async def register_skill(
    name: str,
    skill_type: str,
    description: str = "",
    category: str = "general",
    tags: Optional[List[str]] = None
):
    """注册Skill"""
    try:
        return skill_service.register_skill(
            name=name,
            skill_type=SkillType(skill_type),
            description=description,
            category=category,
            tags=tags
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
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


@router.get("/skills")
async def list_skills(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    skill_type: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None
):
    """列出Skills"""
    try:
        filters = {}
        if skill_type:
            filters["type"] = skill_type
        if status:
            filters["status"] = status
        if category:
            filters["category"] = category
        
        return skill_service.list_skills(filters, page, page_size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/versions")
async def add_version(
    skill_id: str,
    version: str,
    implementation: str,
    schema: Optional[Dict[str, Any]] = None,
    changelog: str = ""
):
    """添加版本"""
    try:
        return skill_service.add_version(skill_id, version, implementation, schema, changelog)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/activate")
async def activate_skill(skill_id: str):
    """激活Skill"""
    try:
        return skill_service.activate_skill(skill_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/deactivate")
async def deactivate_skill(skill_id: str):
    """停用Skill"""
    try:
        return skill_service.deactivate_skill(skill_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/load")
async def load_skill(skill_id: str, version: Optional[str] = None):
    """加载Skill"""
    try:
        return hotplug_service.load_skill(skill_id, version)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/{skill_id}/unload")
async def unload_skill(skill_id: str):
    """卸载Skill"""
    try:
        return hotplug_service.unload_skill(skill_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/loaded")
async def get_loaded_skills():
    """获取已加载的Skills"""
    try:
        return {"skills": hotplug_service.get_loaded_skills()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
