#!/usr/bin/env python3
"""
OpenHarness 工具执行 OPA 守卫

白皮书 §2.1: OpenHarness Agent 内置 OPA 守卫，工具执行前调用 OPA。
白皮书 §4: OpenHarness Agent 通过环境变量 OPA_URL 与策略引擎通信。

将 OpenHarness 的工具执行权限检查桥接到 ODAP OPA + PEP。
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OpenHarnessOPAGuard:
    """OpenHarness 工具执行前的 OPA 守卫

    用法:
        guard = OpenHarnessOPAGuard(pep=get_pep_instance())
        result = guard.check_tool_execution(
            agent_id="agent-1",
            tool_name="read_file",
            tool_input={"path": "/data/doc.txt"},
            subject={"id": "user1", "roles": ["analyst"]},
            environment={"time": "...", "ip": "..."},
            trace_id="trace-001",
        )
        if not result["allowed"]:
            # 阻止工具执行
    """

    def __init__(self, pep=None):
        self.pep = pep

    def check_tool_execution(
        self,
        agent_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        subject: Dict[str, Any],
        environment: Optional[Dict[str, Any]] = None,
        trace_id: str = "",
    ) -> Dict[str, Any]:
        """
        工具执行前检查（白名单 → OPA ABAC → 返回决策）

        Returns:
            {"allowed": bool, "reason": str, "stage": str, "blocked_at": str|None}
        """
        if self.pep is None:
            logger.warning("PEP 未配置，fail-close 拒绝工具执行")
            return {
                "allowed": False,
                "reason": "PEP not configured (fail-close)",
                "stage": "guard",
                "blocked_at": "guard",
            }

        from odap.infra.opa.pep import EnforcementRequest

        req = EnforcementRequest(
            agent_id=agent_id,
            tool_name=tool_name,
            action=tool_name,  # 工具名即 action
            resource={"type": "tool", "id": tool_name, "input": tool_input},
            subject=subject,
            environment=environment or {},
            input_context=tool_input,
            trace_id=trace_id,
        )

        result = self.pep.evaluate(req)
        return {
            "allowed": result.allowed,
            "reason": result.reason,
            "stage": result.stage,
            "blocked_at": result.blocked_at,
            "opa_decision": result.opa_decision,
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_guard_instance: Optional[OpenHarnessOPAGuard] = None


def get_opa_guard() -> OpenHarnessOPAGuard:
    """获取 OPA 守卫全局单例"""
    global _guard_instance
    if _guard_instance is None:
        from odap.infra.opa.pep import get_pep_instance
        _guard_instance = OpenHarnessOPAGuard(pep=get_pep_instance())
    return _guard_instance


def reset_opa_guard():
    """重置单例（测试用）"""
    global _guard_instance
    _guard_instance = None


__all__ = [
    "OpenHarnessOPAGuard",
    "get_opa_guard",
    "reset_opa_guard",
]
