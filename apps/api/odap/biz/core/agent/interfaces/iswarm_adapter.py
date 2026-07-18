"""ISwarmAdapter — Swarm 调度适配器抽象接口

ADR-065: 舱壁先行。agent 通过此接口依赖 integration 层的 SwarmAdapter，
而非直接导入具体实现类。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ISwarmAdapter(ABC):
    """Swarm 调度适配器抽象接口

    定义 agent 对 Swarm 调度能力的需求。
    当前实现: odap.biz.integration.openharness_agent.adapter.swarm_adapter.SwarmAdapter
    """

    @abstractmethod
    def dispatch_intent(
        self, swarm_id: str, intent: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """分发意图到 Swarm 执行

        Args:
            swarm_id: Swarm 标识
            intent: 意图描述
            context: 可选的执行上下文

        Returns:
            包含 status 和 observation 的字典
        """
        ...
