"""
Agent Factory + TraceSpan + RoleManager - 对齐 docs/03-modules/agent/DESIGN.md

功能:
- AgentFactory: Agent 生命周期管理 (工厂模式)
- TraceSpan: Agent 执行追踪 (分布式追踪)
- RoleManager: 角色能力管理
"""

import sys
import os
import uuid
import time
import json
import threading
from typing import Dict, Any, List, Optional, Type, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict, deque

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from odap.biz.core.agent.swarm_orchestrator import AgentType, AgentState, AgentConfig
except ImportError:
    class AgentType(str, Enum):
        COMMANDER = "commander"
        INTELLIGENCE = "intelligence"
        OPERATIONS = "operations"

    class AgentState(str, Enum):
        IDLE = "idle"
        RUNNING = "running"
        FAILED = "failed"

    @dataclass
    class AgentConfig:
        name: str
        agent_type: str
        model: str
        role: str
        tools: List[str] = field(default_factory=list)
        permission_level: str = "normal"


class TracePhase(str, Enum):
    """追踪阶段"""
    INPUT = "input"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DECISION = "decision"
    OUTPUT = "output"
    ERROR = "error"


class TraceStatus(str, Enum):
    """追踪状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class Capability(str, Enum):
    """Agent 能力枚举"""
    SITUATION_AWARENESS = "situation_awareness"
    TARGET_DETECTION = "target_detection"
    THREAT_ANALYSIS = "threat_analysis"
    GRAPH_SEARCH = "graph_search"
    DECISION_MAKING = "decision_making"
    MISSION_PLANNING = "mission_planning"
    RESOURCE_ALLOCATION = "resource_allocation"
    TASK_EXECUTION = "task_execution"
    REPORT_GENERATION = "report_generation"
    EXPLANATION = "explanation"


@dataclass
class TraceSpan:
    """追踪跨度 - 单步执行记录"""
    span_id: str
    parent_span_id: Optional[str]
    phase: TracePhase
    agent_type: str
    status: TraceStatus
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    start_time: str = ""
    end_time: Optional[str] = None
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self, status: TraceStatus, output: Dict = None, error: str = None):
        self.status = status
        self.output_data = output or {}
        self.error_message = error
        self.end_time = datetime.now(timezone.utc).isoformat()
        if self.start_time:
            start_ts = datetime.fromisoformat(self.start_time.replace('Z', '+00:00'))
            self.duration_ms = (datetime.now(timezone.utc) - start_ts).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "phase": self.phase.value,
            "agent_type": self.agent_type,
            "status": self.status.value,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class Trace:
    """执行追踪 - 完整一次 Agent 执行"""
    trace_id: str
    agent_id: str
    agent_type: str
    mission_id: Optional[str] = None
    spans: List[TraceSpan] = field(default_factory=list)
    root_span_id: Optional[str] = None
    status: TraceStatus = TraceStatus.PENDING
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    total_duration_ms: float = 0.0

    def create_span(self, phase: TracePhase, parent_span_id: str = None,
                    input_data: Dict = None) -> TraceSpan:
        span = TraceSpan(
            span_id=str(uuid.uuid4())[:16],
            parent_span_id=parent_span_id or self.root_span_id,
            phase=phase,
            agent_type=self.agent_type,
            status=TraceStatus.RUNNING,
            input_data=input_data or {},
            start_time=datetime.now(timezone.utc).isoformat(),
        )
        if not self.root_span_id:
            self.root_span_id = span.span_id
        self.spans.append(span)
        return span

    def complete(self, status: TraceStatus):
        self.status = status
        self.end_time = datetime.now(timezone.utc).isoformat()
        self.total_duration_ms = (datetime.now(timezone.utc) - datetime.fromisoformat(
            self.start_time.replace('Z', '+00:00')
        )).total_seconds() * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "mission_id": self.mission_id,
            "spans": [s.to_dict() for s in self.spans],
            "root_span_id": self.root_span_id,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": round(self.total_duration_ms, 2),
        }


class TraceCollector:
    """追踪收集器"""

    MAX_TRACES = 1000

    def __init__(self):
        self._traces: deque[Trace] = deque(maxlen=self.MAX_TRACES)
        self._lock = threading.Lock()

    def start_trace(self, agent_id: str, agent_type: str,
                    mission_id: str = None) -> Trace:
        trace = Trace(
            trace_id=str(uuid.uuid4())[:16],
            agent_id=agent_id,
            agent_type=agent_type,
            mission_id=mission_id,
        )
        with self._lock:
            self._traces.append(trace)
        return trace

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        for t in self._traces:
            if t.trace_id == trace_id:
                return t
        return None

    def get_agent_traces(self, agent_id: str, limit: int = 10) -> List[Trace]:
        result = []
        for t in reversed(self._traces):
            if t.agent_id == agent_id:
                result.append(t)
                if len(result) >= limit:
                    break
        return result

    def get_recent_traces(self, limit: int = 20) -> List[Trace]:
        return list(reversed(self._traces))[:limit]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            traces = list(self._traces)
        if not traces:
            return {"total": 0}

        success = sum(1 for t in traces if t.status == TraceStatus.SUCCESS)
        failed = sum(1 for t in traces if t.status == TraceStatus.FAILED)

        by_agent = defaultdict(int)
        for t in traces:
            by_agent[t.agent_type] += 1

        durations = [t.total_duration_ms for t in traces if t.total_duration_ms > 0]

        return {
            "total": len(traces),
            "success": success,
            "failed": failed,
            "success_rate": round(success / len(traces) * 100, 1) if traces else 0,
            "by_agent": dict(by_agent),
            "avg_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0,
            "max_duration_ms": round(max(durations), 2) if durations else 0,
        }


@dataclass
class RoleCapability:
    """角色能力"""
    capability: Capability
    enabled: bool = True
    max_depth: int = 3
    requires_approval: bool = False
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleConfig:
    """角色配置"""
    role_name: str
    agent_type: str
    description: str = ""
    default_model: str = "gpt-4"
    capabilities: List[RoleCapability] = field(default_factory=list)
    priority: int = 0
    auto_escalate: bool = False


class RoleManager:
    """角色管理器"""

    def __init__(self):
        self._roles: Dict[str, RoleConfig] = {}
        self._init_default_roles()

    def _init_default_roles(self):
        commander = RoleConfig(
            role_name="Commander",
            agent_type=AgentType.COMMANDER.value,
            description="全局决策中枢，负责态势理解与决策制定",
            default_model="gpt-4",
            capabilities=[
                RoleCapability(Capability.SITUATION_AWARENESS, max_depth=5),
                RoleCapability(Capability.DECISION_MAKING, requires_approval=True),
                RoleCapability(Capability.MISSION_PLANNING, max_depth=5),
                RoleCapability(Capability.RESOURCE_ALLOCATION, requires_approval=True),
            ],
            priority=10,
        )
        self._roles["commander"] = commander

        intelligence = RoleConfig(
            role_name="Intelligence",
            agent_type=AgentType.INTELLIGENCE.value,
            description="情报分析中枢，负责数据收集与威胁分析",
            default_model="gpt-4",
            capabilities=[
                RoleCapability(Capability.TARGET_DETECTION, max_depth=5),
                RoleCapability(Capability.THREAT_ANALYSIS, max_depth=5),
                RoleCapability(Capability.GRAPH_SEARCH, max_depth=3),
                RoleCapability(Capability.REPORT_GENERATION),
            ],
            priority=8,
        )
        self._roles["intelligence"] = intelligence

        operations = RoleConfig(
            role_name="Operations",
            agent_type=AgentType.OPERATIONS.value,
            description="任务执行中枢，负责资源调度与任务执行",
            default_model="gpt-4",
            capabilities=[
                RoleCapability(Capability.TASK_EXECUTION, max_depth=5),
                RoleCapability(Capability.RESOURCE_ALLOCATION, max_depth=3),
                RoleCapability(Capability.MISSION_PLANNING, max_depth=3),
            ],
            priority=6,
        )
        self._roles["operations"] = operations

    def get_role(self, role_name: str) -> Optional[RoleConfig]:
        return self._roles.get(role_name.lower())

    def get_capabilities(self, role_name: str) -> List[RoleCapability]:
        role = self.get_role(role_name)
        return role.capabilities if role else []

    def has_capability(self, role_name: str, capability: Capability) -> bool:
        role = self.get_role(role_name)
        if not role:
            return False
        return any(c.capability == capability and c.enabled for c in role.capabilities)

    def get_all_roles(self) -> List[RoleConfig]:
        return list(self._roles.values())

    def register_role(self, config: RoleConfig) -> RoleConfig:
        self._roles[config.role_name.lower()] = config
        return config


class AgentFactory:
    """Agent 工厂 - 管理 Agent 生命周期"""

    def __init__(self):
        self._agent_registry: Dict[str, Type] = {}
        self._agent_instances: Dict[str, Any] = {}
        self._agent_configs: Dict[str, AgentConfig] = {}
        self._trace_collector = TraceCollector()
        self._role_manager = RoleManager()
        self._lock = threading.RLock()

    def register_agent_class(self, agent_type: str, agent_class: Type):
        """注册 Agent 类"""
        self._agent_registry[agent_type] = agent_class

    def create_agent(self, name: str, agent_type: str, model: str = "gpt-4",
                     role: str = None, tools: List[str] = None,
                     opa_manager=None, graph_manager=None) -> Any:
        agent_class = self._agent_registry.get(agent_type)
        if not agent_class:
            raise ValueError(f"Unknown agent type: {agent_type}")

        config = AgentConfig(
            name=name,
            agent_type=agent_type,
            model=model,
            role=role or self._resolve_role(agent_type).role_name if hasattr(self._resolve_role(agent_type), 'role_name') else agent_type,
            tools=tools or [],
        )

        role_config = self._role_manager.get_role(agent_type)
        if role_config:
            config.role = role_config.role_name

        agent_id = str(uuid.uuid4())[:8]

        agent = agent_class(config, opa_manager, graph_manager)
        agent._agent_id = agent_id

        with self._lock:
            self._agent_instances[agent_id] = agent
            self._agent_configs[agent_id] = config

        return agent

    def get_agent(self, agent_id: str) -> Optional[Any]:
        return self._agent_instances.get(agent_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"agent_id": aid, "name": cfg.name, "type": cfg.agent_type, "role": cfg.role}
                for aid, cfg in self._agent_configs.items()
            ]

    def destroy_agent(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id in self._agent_instances:
                del self._agent_instances[agent_id]
                del self._agent_configs[agent_id]
                return True
        return False

    def _resolve_role(self, agent_type: str):
        return self._role_manager.get_role(agent_type)

    def start_trace(self, agent_id: str, mission_id: str = None) -> Optional[Trace]:
        agent = self._agent_instances.get(agent_id)
        if not agent:
            return None
        agent_type = self._agent_configs[agent_id].agent_type if agent_id in self._agent_configs else "unknown"
        return self._trace_collector.start_trace(agent_id, agent_type, mission_id)

    def get_trace_stats(self) -> Dict[str, Any]:
        return self._trace_collector.get_stats()

    def get_traces(self, agent_id: str = None, limit: int = 10) -> List[Dict]:
        if agent_id:
            traces = self._trace_collector.get_agent_traces(agent_id, limit)
        else:
            traces = self._trace_collector.get_recent_traces(limit)
        return [t.to_dict() for t in traces]

    def get_role_manager(self) -> RoleManager:
        return self._role_manager


_global_agent_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    global _global_agent_factory
    if _global_agent_factory is None:
        _global_agent_factory = AgentFactory()
        try:
            from odap.biz.core.agent.swarm_orchestrator import CommanderAgent, IntelligenceAgent, OperationsAgent
            _global_agent_factory.register_agent_class("commander", CommanderAgent)
            _global_agent_factory.register_agent_class("intelligence", IntelligenceAgent)
            _global_agent_factory.register_agent_class("operations", OperationsAgent)
        except ImportError:
            pass
    return _global_agent_factory
