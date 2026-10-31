"""Agent 基础类型 —— common 叶子层。

W0-4（SPEC-v2 §2.1 / §11）：`infra/resilience/fault_tolerance.py` 原先在模块级
`from odap.biz.core.agent.swarm_orchestrator import AgentState`，构成 infra→biz 的
顶层反向依赖（违反 C4）。按「类型下沉 common」方案，把纯枚举搬到叶子层：

    common(叶子) ← infra ← biz ← web

- common 只依赖标准库（C1 严格契约保持绿）。
- `biz.core.agent.agent_factory` 改为从本模块再导出，旧导入路径继续可用。
- infra 侧（fault_tolerance）改指本模块，直接边消除。

禁止在本模块引入任何 biz / infra / web 依赖。
"""

from enum import Enum


class AgentType(str, Enum):
    """Agent 类型（与 biz.core.agent.agent_factory.AgentType 同源）。"""

    DIRECTOR = "director"
    INTELLIGENCE = "intelligence"
    OPERATIONS = "operations"


class AgentState(str, Enum):
    """Agent 运行状态（与 biz.core.agent.agent_factory.AgentState 同源）。"""

    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    SUSPENDED = "suspended"


__all__ = ["AgentType", "AgentState"]
