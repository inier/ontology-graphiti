"""core.agent 唯一对外公共 API 门面 (Public Facade)。

背景（ADR-080 / C3 同类契约）：
    `core/agent` 内部有 impl / services / models / interfaces 等子包，
    跨域消费者若直接深插内部路径，内部重构会打断外部。

    本模块为 agent 域提供**唯一稳定对外面**：

        from odap.biz.core.agent.public import get_domain_swarm

设计要点：
    1. PEP 562 惰性 `__getattr__`：导入本模块零级联开销，规避循环导入
       （`swarm_orchestrator` 反向依赖 `agent_factory`）。
    2. `get_domain_swarm()` 返回进程内单例 —— 群体编排器持有 Agent 实例表，
       每次容错重启都新建会导致「找不到 Agent」的假阴性。

W0-4（SPEC-v2 §2.1）：`infra.resilience.fault_tolerance` 经
`odap.biz.providers_bootstrap` 注册的工厂调用本门面，从而消除 infra→biz 直接边。
"""

from __future__ import annotations

import importlib
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - 仅供类型检查器
    from odap.biz.core.agent.swarm_orchestrator import DomainSwarm


_PUBLIC_MAP: dict[str, tuple[str, str]] = {
    "DomainSwarm": ("odap.biz.core.agent.swarm_orchestrator", "DomainSwarm"),
    "AgentState": ("odap.biz.core.agent.agent_factory", "AgentState"),
    "AgentType": ("odap.biz.core.agent.agent_factory", "AgentType"),
}

_swarm_singleton: Any = None
_swarm_lock = threading.Lock()


def get_domain_swarm() -> "DomainSwarm":
    """获取进程内 DomainSwarm 单例（首次调用时构造）。"""
    global _swarm_singleton
    if _swarm_singleton is None:
        with _swarm_lock:
            if _swarm_singleton is None:
                cls = _load("DomainSwarm")
                _swarm_singleton = cls()
    return _swarm_singleton


def reset_domain_swarm() -> None:
    """清空单例（仅测试隔离用）。"""
    global _swarm_singleton
    with _swarm_lock:
        _swarm_singleton = None


def _load(symbol: str) -> Any:
    module_path, attr = _PUBLIC_MAP[symbol]
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def __getattr__(name: str) -> Any:  # PEP 562
    if name in _PUBLIC_MAP:
        return _load(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["get_domain_swarm", "reset_domain_swarm", "DomainSwarm", "AgentState", "AgentType"]
