"""Skill管理器接口"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from ..models.skill import Skill, SkillStatus, SkillType, SkillVersion


class ISkillManager(ABC):
    """Skill管理器接口"""
    
    @abstractmethod
    def register_skill(self, name: str, skill_type: SkillType, 
                      description: str = "", category: str = "general",
                      tags: List[str] = None) -> Skill:
        """注册Skill
        
        Args:
            name: Skill名称
            skill_type: Skill类型
            description: 描述
            category: 分类
            tags: 标签
            
        Returns:
            创建的Skill
        """
        pass
    
    @abstractmethod
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取Skill
        
        Args:
            skill_id: Skill ID
            
        Returns:
            Skill对象
        """
        pass
    
    @abstractmethod
    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> Skill:
        """更新Skill
        
        Args:
            skill_id: Skill ID
            updates: 更新内容
            
        Returns:
            更新后的Skill
        """
        pass
    
    @abstractmethod
    def delete_skill(self, skill_id: str) -> bool:
        """删除Skill
        
        Args:
            skill_id: Skill ID
            
        Returns:
            是否删除成功
        """
        pass
    
    @abstractmethod
    def list_skills(self, filters: Dict[str, Any] = None, 
                   page: int = 1, page_size: int = 10) -> List[Skill]:
        """列出Skills
        
        Args:
            filters: 过滤条件
            page: 页码
            page_size: 每页数量
            
        Returns:
            Skill列表
        """
        pass
    
    @abstractmethod
    def add_version(self, skill_id: str, version: str, implementation: str, 
                   schema: Dict[str, Any] = None, changelog: str = "") -> SkillVersion:
        """添加版本
        
        Args:
            skill_id: Skill ID
            version: 版本号
            implementation: 实现代码
            schema: schema定义
            changelog: 变更日志
            
        Returns:
            创建的版本
        """
        pass
    
    @abstractmethod
    def activate_skill(self, skill_id: str) -> Skill:
        """激活Skill
        
        Args:
            skill_id: Skill ID
            
        Returns:
            激活后的Skill
        """
        pass
    
    @abstractmethod
    def deactivate_skill(self, skill_id: str) -> Skill:
        """停用Skill
        
        Args:
            skill_id: Skill ID
            
        Returns:
            停用后的Skill
        """
        pass
