"""IRuntimeService — 本体运行时服务抽象接口

ADR-065: 舱壁先行。simulation 通过此接口依赖 core 层的运行时服务。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class IRuntimeService(ABC):
    """本体运行时抽象接口"""

    @abstractmethod
    def get_contract_by_action(self, action_type_id: str) -> Dict[str, Any]:
        """获取动作合约（含副作用传播规则）"""
        ...
