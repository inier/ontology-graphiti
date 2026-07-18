"""IDecisionOMSService — 决策域 OMS 抽象接口

ADR-065: 舱壁先行。decision 通过此接口依赖 core 层的 OMS 服务。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IDecisionOMSService(ABC):
    """决策域本体管理抽象接口"""

    @abstractmethod
    def get_action_type(self, action_type_id: str) -> Optional[Dict[str, Any]]:
        """获取动作类型定义"""
        ...

    @abstractmethod
    def list_action_types(self, target_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出可用动作类型"""
        ...
