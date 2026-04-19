"""Skill服务"""

from typing import Dict, Any, List, Optional
from ..impl.skill_manager import SkillManager
from ..impl.hotplug import HotplugManager
from ..models.skill import Skill, SkillType, SkillStatus


class SkillService:
    """Skill服务"""
    
    def __init__(self):
        self.manager = SkillManager()
        self.hotplug = HotplugManager()
    
    def register_skill(self, name: str, skill_type: SkillType, 
                     description: str = "", category: str = "general",
                     tags: List[str] = None) -> Dict[str, Any]:
        """注册Skill"""
        skill = self.manager.register_skill(name, skill_type, description, category, tags)
        
        return {
            "skill_id": skill.id,
            "name": skill.name,
            "type": skill.type.value,
            "status": skill.status.value,
            "created_at": skill.created_at.isoformat()
        }
    
    def get_skill(self, skill_id: str) -> Dict[str, Any]:
        """获取Skill"""
        skill = self.manager.get_skill(skill_id)
        if not skill:
            return {"status": "error", "message": "Skill not found"}
        
        return {
            "skill_id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "type": skill.type.value,
            "status": skill.status.value,
            "category": skill.category,
            "tags": skill.tags,
            "current_version": skill.current_version,
            "created_at": skill.created_at.isoformat(),
            "updated_at": skill.updated_at.isoformat()
        }
    
    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """更新Skill"""
        try:
            skill = self.manager.update_skill(skill_id, updates)
            return {
                "skill_id": skill.id,
                "name": skill.name,
                "updated_at": skill.updated_at.isoformat()
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def delete_skill(self, skill_id: str) -> Dict[str, Any]:
        """删除Skill"""
        success = self.manager.delete_skill(skill_id)
        return {
            "status": "success" if success else "error",
            "message": "Skill deleted" if success else "Skill not found"
        }
    
    def list_skills(self, filters: Dict[str, Any] = None, 
                   page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """列出Skills"""
        skills = self.manager.list_skills(filters, page, page_size)
        
        skill_list = []
        for skill in skills:
            skill_list.append({
                "skill_id": skill.id,
                "name": skill.name,
                "type": skill.type.value,
                "status": skill.status.value,
                "category": skill.category
            })
        
        return {
            "skills": skill_list,
            "page": page,
            "page_size": page_size,
            "total": len(skill_list)
        }
    
    def add_version(self, skill_id: str, version: str, implementation: str, 
                   schema: Dict[str, Any] = None, changelog: str = "") -> Dict[str, Any]:
        """添加版本"""
        try:
            skill_version = self.manager.add_version(skill_id, version, implementation, schema, changelog)
            return {
                "version_id": skill_version.id,
                "skill_id": skill_version.skill_id,
                "version": skill_version.version,
                "created_at": skill_version.created_at.isoformat()
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def activate_skill(self, skill_id: str) -> Dict[str, Any]:
        """激活Skill"""
        try:
            skill = self.manager.activate_skill(skill_id)
            return {
                "skill_id": skill.id,
                "status": skill.status.value
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def deactivate_skill(self, skill_id: str) -> Dict[str, Any]:
        """停用Skill"""
        try:
            skill = self.manager.deactivate_skill(skill_id)
            return {
                "skill_id": skill.id,
                "status": skill.status.value
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}
    
    def load_skill(self, skill_id: str, version: str = None) -> Dict[str, Any]:
        """加载Skill"""
        success = self.hotplug.load_skill(skill_id, version)
        return {
            "status": "success" if success else "error",
            "message": "Skill loaded" if success else "Failed to load skill"
        }
    
    def unload_skill(self, skill_id: str) -> Dict[str, Any]:
        """卸载Skill"""
        success = self.hotplug.unload_skill(skill_id)
        return {
            "status": "success" if success else "error",
            "message": "Skill unloaded" if success else "Skill not loaded"
        }
    
    def get_loaded_skills(self) -> List[str]:
        """获取已加载的Skills"""
        return self.hotplug.get_loaded_skills()
