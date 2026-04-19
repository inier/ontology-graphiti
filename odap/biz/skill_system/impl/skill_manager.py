"""Skill管理器实现"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.skill_manager import ISkillManager
from ..models.skill import Skill, SkillStatus, SkillType, SkillVersion


class SkillManager(ISkillManager):
    """Skill管理器实现"""
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
    
    def register_skill(self, name: str, skill_type: SkillType, 
                      description: str = "", category: str = "general",
                      tags: List[str] = None) -> Skill:
        """注册Skill"""
        skill = Skill(
            name=name,
            type=skill_type,
            description=description,
            category=category,
            tags=tags or [],
            status=SkillStatus.DRAFT
        )
        
        self._skills[skill.id] = skill
        return skill
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取Skill"""
        return self._skills.get(skill_id)
    
    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> Skill:
        """更新Skill"""
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError("Skill not found")
        
        for key, value in updates.items():
            if hasattr(skill, key):
                setattr(skill, key, value)
        
        skill.updated_at = datetime.now()
        return skill
    
    def delete_skill(self, skill_id: str) -> bool:
        """删除Skill"""
        if skill_id in self._skills:
            del self._skills[skill_id]
            return True
        return False
    
    def list_skills(self, filters: Dict[str, Any] = None, 
                   page: int = 1, page_size: int = 10) -> List[Skill]:
        """列出Skills"""
        filters = filters or {}
        skills = list(self._skills.values())
        
        if "type" in filters:
            skills = [s for s in skills if s.type.value == filters["type"]]
        if "status" in filters:
            skills = [s for s in skills if s.status.value == filters["status"]]
        if "category" in filters:
            skills = [s for s in skills if s.category == filters["category"]]
        
        start = (page - 1) * page_size
        end = start + page_size
        return skills[start:end]
    
    def add_version(self, skill_id: str, version: str, implementation: str, 
                   schema: Dict[str, Any] = None, changelog: str = "") -> SkillVersion:
        """添加版本"""
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError("Skill not found")
        
        skill_version = SkillVersion(
            skill_id=skill_id,
            version=version,
            implementation=implementation,
            schema=schema or {},
            changelog=changelog
        )
        
        skill.versions.append(skill_version)
        skill.current_version = version
        skill.updated_at = datetime.now()
        
        return skill_version
    
    def activate_skill(self, skill_id: str) -> Skill:
        """激活Skill"""
        return self.update_skill(skill_id, {"status": SkillStatus.ACTIVE})
    
    def deactivate_skill(self, skill_id: str) -> Skill:
        """停用Skill"""
        return self.update_skill(skill_id, {"status": SkillStatus.INACTIVE})
