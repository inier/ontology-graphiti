"""热插拔管理实现"""

from typing import Dict, Any, List, Optional
import importlib
import sys
from ..interfaces.hotplug import IHotplugManager


class HotplugManager(IHotplugManager):
    """热插拔管理器实现"""
    
    def __init__(self):
        self._loaded_skills: Dict[str, Any] = {}
        self._skill_modules: Dict[str, str] = {}
    
    def load_skill(self, skill_id: str, version: str = None) -> bool:
        """加载Skill"""
        if skill_id in self._loaded_skills:
            return True
        
        module_name = self._skill_modules.get(skill_id)
        if not module_name:
            return False
        
        try:
            module = importlib.import_module(module_name)
            self._loaded_skills[skill_id] = module
            return True
        except Exception:
            return False
    
    def unload_skill(self, skill_id: str) -> bool:
        """卸载Skill"""
        if skill_id in self._loaded_skills:
            del self._loaded_skills[skill_id]
            return True
        return False
    
    def reload_skill(self, skill_id: str) -> bool:
        """重新加载Skill"""
        if skill_id in self._loaded_skills:
            module_name = self._skill_modules.get(skill_id)
            if not module_name:
                return False
            
            try:
                module = importlib.reload(module)
                self._loaded_skills[skill_id] = module
                return True
            except Exception:
                return False
        return False
    
    def get_loaded_skills(self) -> List[str]:
        """获取已加载的Skills"""
        return list(self._loaded_skills.keys())
    
    def is_loaded(self, skill_id: str) -> bool:
        """检查Skill是否已加载"""
        return skill_id in self._loaded_skills
    
    def get_skill_status(self, skill_id: str) -> Dict[str, Any]:
        """获取Skill状态"""
        is_loaded = self.is_loaded(skill_id)
        
        return {
            "skill_id": skill_id,
            "is_loaded": is_loaded,
            "module_name": self._skill_modules.get(skill_id)
        }
    
    def register_module(self, skill_id: str, module_name: str) -> None:
        """注册模块
        
        Args:
            skill_id: Skill ID
            module_name: 模块名称
        """
        self._skill_modules[skill_id] = module_name
