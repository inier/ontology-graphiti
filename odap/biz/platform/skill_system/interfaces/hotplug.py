"""热插拔管理接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class IHotplugManager(ABC):
    """热插拔管理器接口"""
    
    @abstractmethod
    def load_skill(self, skill_id: str, version: str = None) -> bool:
        """加载Skill
        
        Args:
            skill_id: Skill ID
            version: 版本号
            
        Returns:
            是否加载成功
        """
        pass
    
    @abstractmethod
    def unload_skill(self, skill_id: str) -> bool:
        """卸载Skill
        
        Args:
            skill_id: Skill ID
            
        Returns:
            是否卸载成功
        """
        pass
    
    @abstractmethod
    def reload_skill(self, skill_id: str) -> bool:
        """重新加载Skill
        
        Args:
            skill_id: Skill ID
            
        Returns:
            是否重新加载成功
        """
        pass
    
    @abstractmethod
    def get_loaded_skills(self) -> List[str]:
        """获取已加载的Skills
        
        Returns:
            已加载的Skill ID列表
        """
        pass
    
    @abstractmethod
    def is_loaded(self, skill_id: str) -> bool:
        """检查Skill是否已加载
        
        Args:
            skill_id: Skill ID
            
        Returns:
            是否已加载
        """
        pass
    
    @abstractmethod
    def get_skill_status(self, skill_id: str) -> Dict[str, Any]:
        """获取Skill状态
        
        Args:
            skill_id: Skill ID
            
        Returns:
            Skill状态信息
        """
        pass
