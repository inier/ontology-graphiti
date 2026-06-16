"""OODA 接口与生命周期钩子抽象基类

OODAInterface — 所有 OODA 执行器（DomainSwarm / OODALoop）的统一接口
OODALifecycleHook — OODA 阶段生命周期钩子协议

支持的 OODA 阶段: observe / orient / decide / act / evaluate
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OODALifecycleHook(ABC):
    """OODA 生命周期钩子抽象基类

    在 OODA 各阶段开始和结束时触发回调。
    如果钩子抛出异常，仅记录日志并继续执行（优雅降级）。

    支持的阶段: observe / orient / decide / act / evaluate
    """

    async def on_phase_start(self, phase: str, context: Dict[str, Any]) -> None:
        """阶段开始时触发

        Args:
            phase: OODA 阶段名称 ("observe" / "orient" / "decide" / "act" / "evaluate")
            context: 当前执行上下文
        """
        pass

    async def on_phase_end(self, phase: str, result: Any, context: Dict[str, Any]) -> None:
        """阶段结束时触发

        Args:
            phase: OODA 阶段名称
            result: 该阶段的执行结果
            context: 当前执行上下文
        """
        pass


class OODAInterface(ABC):
    """OODA 执行器统一接口

    DomainSwarm 和 OODALoop 都实现此接口，
    确保两者具备一致的 OODA 执行和钩子管理能力。
    """

    @abstractmethod
    async def execute_mission(self, mission: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行完整 OODA 循环

        Args:
            mission: 任务描述或任务对象
            context: 可选的执行上下文

        Returns:
            包含执行结果的字典
        """
        ...

    @abstractmethod
    def add_lifecycle_hook(self, hook: OODALifecycleHook) -> None:
        """添加生命周期钩子

        Args:
            hook: OODALifecycleHook 实例
        """
        ...
