"""ActionExecutor 抽象接口 (T379)

执行器负责根据 ActionType + parameters 完成实际业务逻辑。
默认实现 SkillBackedExecutor 通过 linked_skill_id 委托给 Skill 系统。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from ..models import ActionExecution, ActionType


class ActionExecutor(ABC):
    """Action 执行器抽象基类

    execute() 必须返回完整的 ActionExecution（包含 status/result/error_message/duration_ms），
    实现方需自行处理：
    - 异常捕获并落到 status=FAILED
    - started_at / finished_at / duration_ms 计算
    - audit_record_id 写入（如需走统一审计）
    """

    @abstractmethod
    def execute(
        self,
        action_type: ActionType,
        parameters: Dict[str, Any],
        user_context: Dict[str, Any],
    ) -> ActionExecution:
        """执行 ActionType 并返回 ActionExecution

        Args:
            action_type: 业务接口定义
            parameters: 业务参数
            user_context: 调用上下文 {user_id, ws_id, role, ...}
        """
        raise NotImplementedError


__all__ = ["ActionExecutor"]
