"""热插拔服务"""

from typing import Dict, Any, List
from ..impl.hotplug import HotplugManager


class HotplugService:
    """热插拔服务"""
    
    def __init__(self):
        self.manager = HotplugManager()
    
    def load_skill(self, skill_id: str, version: str = None) -> Dict[str, Any]:
        """加载Skill"""
        success = self.manager.load_skill(skill_id, version)
        return {
            "status": "success" if success else "error",
            "skill_id": skill_id,
            "version": version
        }
    
    def unload_skill(self, skill_id: str) -> Dict[str, Any]:
        """卸载Skill"""
        success = self.manager.unload_skill(skill_id)
        return {
            "status": "success" if success else "error",
            "skill_id": skill_id
        }
    
    def reload_skill(self, skill_id: str) -> Dict[str, Any]:
        """重新加载Skill"""
        success = self.manager.reload_skill(skill_id)
        return {
            "status": "success" if success else "error",
            "skill_id": skill_id
        }
    
    def get_loaded_skills(self) -> List[str]:
        """获取已加载的Skills"""
        return self.manager.get_loaded_skills()
    
    def is_loaded(self, skill_id: str) -> bool:
        """检查Skill是否已加载"""
        return self.manager.is_loaded(skill_id)
    
    def get_skill_status(self, skill_id: str) -> Dict[str, Any]:
        """获取Skill状态"""
        return self.manager.get_skill_status(skill_id)
    
    def get_all_status(self) -> Dict[str, Any]:
        """获取所有Skill状态"""
        loaded = self.manager.get_loaded_skills()
        return {
            "total_loaded": len(loaded),
            "loaded_skills": loaded
        }
