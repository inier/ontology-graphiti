"""热插拔管理实现"""

import logging
from typing import Dict, Any, List, Optional
import importlib
import sys
from ..interfaces.hotplug import IHotplugManager

logger = logging.getLogger(__name__)


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
            logger.warning(f"HotplugManager: no module registered for skill {skill_id}")
            return False
        
        try:
            module = importlib.import_module(module_name)
            self._loaded_skills[skill_id] = module
            logger.debug(f"HotplugManager: loaded skill {skill_id} from {module_name}")
            return True
        except Exception as e:
            logger.warning(f"HotplugManager: failed to load skill {skill_id} from {module_name}: {e}")
            return False
    
    def unload_skill(self, skill_id: str) -> bool:
        """卸载Skill"""
        if skill_id not in self._loaded_skills:
            return False

        module_name = self._skill_modules.get(skill_id, '')
        self._loaded_skills.pop(skill_id, None)

        if module_name and module_name in sys.modules:
            try:
                del sys.modules[module_name]
                logger.debug(f"HotplugManager: unloaded skill {skill_id}, removed {module_name} from sys.modules")
            except Exception as e:
                logger.warning(f"HotplugManager: failed to remove {module_name} from sys.modules: {e}")

        return True
    
    def reload_skill(self, skill_id: str) -> bool:
        """重新加载Skill"""
        if skill_id not in self._loaded_skills:
            logger.warning(f"HotplugManager: cannot reload unloaded skill {skill_id}")
            return False

        module_name = self._skill_modules.get(skill_id)
        if not module_name:
            logger.warning(f"HotplugManager: no module mapping for skill {skill_id}")
            return False

        loaded_module = sys.modules.get(module_name)
        if loaded_module is None:
            try:
                loaded_module = importlib.import_module(module_name)
            except Exception as e:
                logger.warning(f"HotplugManager: failed to import {module_name} for reload: {e}")
                return False

        try:
            reloaded = importlib.reload(loaded_module)
            self._loaded_skills[skill_id] = reloaded
            logger.debug(f"HotplugManager: reloaded skill {skill_id} from {module_name}")
            return True
        except Exception as e:
            logger.warning(f"HotplugManager: failed to reload skill {skill_id} from {module_name}: {e}")
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
