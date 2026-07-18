"""IOMSService — OMS 服务抽象接口

ADR-065: 舱壁先行。simulation 通过此接口依赖 core 层的 OMS 服务，
而非直接导入具体实现类。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IOMSService(ABC):
    """本体管理服务抽象接口"""

    @abstractmethod
    def get_object_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        """获取对象类型定义"""
        ...

    @abstractmethod
    def get_action_type(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        """获取动作类型定义"""
        ...

    @abstractmethod
    def list_action_types(self, target_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出所有动作类型"""
        ...
