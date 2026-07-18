"""Agent 接口层 — 所有抽象定义

ADR-065 舱壁先行：此目录下的接口是 agent 对外部依赖的唯一接触点。
"""

from odap.biz.core.agent.interfaces.ooda_interface import OODAInterface, OODALifecycleHook
from odap.biz.core.agent.interfaces.iswarm_adapter import ISwarmAdapter
from odap.biz.core.agent.interfaces.isession_memory import ISessionMemory

__all__ = [
    "OODAInterface",
    "OODALifecycleHook",
    "ISwarmAdapter",
    "ISessionMemory",
]
