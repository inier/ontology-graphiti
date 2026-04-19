"""Skill注册表实现"""

from typing import Dict, Any, List, Optional, Callable
from ..interfaces.registry import ISkillRegistry


class SkillRegistry(ISkillRegistry):
    """Skill注册表实现"""
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
    
    def register(self, skill_id: str, handler: Callable) -> bool:
        """注册Skill处理器"""
        self._handlers[skill_id] = handler
        return True
    
    def unregister(self, skill_id: str) -> bool:
        """取消注册"""
        if skill_id in self._handlers:
            del self._handlers[skill_id]
            return True
        return False
    
    def get_handler(self, skill_id: str) -> Optional[Callable]:
        """获取处理器"""
        return self._handlers.get(skill_id)
    
    def list_registered(self) -> List[str]:
        """列出已注册的Skills"""
        return list(self._handlers.keys())
    
    def is_registered(self, skill_id: str) -> bool:
        """检查是否已注册"""
        return skill_id in self._handlers
