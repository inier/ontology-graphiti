"""Skill注册表接口"""

from typing import Dict, Any, List, Optional, Callable


class ISkillRegistry:
    """Skill注册表接口"""

    def register(self, skill_id: str, handler: Callable) -> bool:
        """注册Skill处理器

        Args:
            skill_id: Skill ID
            handler: 处理函数

        Returns:
            是否注册成功
        """
        raise NotImplementedError

    def unregister(self, skill_id: str) -> bool:
        """取消注册

        Args:
            skill_id: Skill ID

        Returns:
            是否取消注册成功
        """
        raise NotImplementedError

    def get_handler(self, skill_id: str) -> Optional[Callable]:
        """获取处理器

        Args:
            skill_id: Skill ID

        Returns:
            处理函数
        """
        raise NotImplementedError

    def list_registered(self) -> List[str]:
        """列出已注册的Skills

        Returns:
            已注册的Skill ID列表
        """
        raise NotImplementedError

    def is_registered(self, skill_id: str) -> bool:
        """检查是否已注册

        Args:
            skill_id: Skill ID

        Returns:
            是否已注册
        """
        raise NotImplementedError
