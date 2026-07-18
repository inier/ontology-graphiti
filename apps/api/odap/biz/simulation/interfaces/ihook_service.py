"""IHookService — 事件传播抽象接口

ADR-065: 舱壁先行。simulation 通过此接口传播反馈事件，
而非直接依赖 integration 层的 HookAdapter。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class IHookService(ABC):
    """事件传播抽象接口"""

    @abstractmethod
    def emit_event(self, event_type: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """发布事件到系统其他模块"""
        ...
