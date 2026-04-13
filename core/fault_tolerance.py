"""
故障恢复管理器模块
实现 Agent 故障检测、分类、恢复策略和断路器模式

Phase 2 扩展: 故障恢复与状态管理
"""

import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional

logger = logging.getLogger("fault_tolerance")


class AgentState(str, Enum):
    """Agent 执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    SUSPENDED = "suspended"


class FailureType(str, Enum):
    """故障类型"""
    AGENT_TIMEOUT = "agent_timeout"
    OPA_DENIAL = "opa_denial"
    GRAPHITI_UNAVAILABLE = "graphiti_unavailable"
    NETWORK_ERROR = "network_error"
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    UNEXPECTED_EXCEPTION = "unexpected_exception"


@dataclass
class FailureRecord:
    """故障记录"""
    timestamp: datetime
    agent_id: str
    failure_type: FailureType
    error_message: str
    recovery_attempts: int = 0
    resolved: bool = False


class FaultRecoveryManager:
    """故障恢复管理器"""

    _instance: Optional['FaultRecoveryManager'] = None

    def __init__(self):
        self.agent_states: Dict[str, AgentState] = {}
        self.failure_history: List[FailureRecord] = []
        self.failure_count: Dict[str, int] = {}
        self.recovery_strategies: Dict[FailureType, str] = {
            FailureType.AGENT_TIMEOUT: "retry_with_backoff",
            FailureType.OPA_DENIAL: "escalate_to_commander",
            FailureType.GRAPHITI_UNAVAILABLE: "use_cache_fallback",
            FailureType.NETWORK_ERROR: "retry_with_backoff",
            FailureType.TOOL_EXECUTION_ERROR: "try_alternative_tool",
            FailureType.UNEXPECTED_EXCEPTION: "restart_agent"
        }
        self.max_retries = 3
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_reset_time = 300
        self.circuit_breaker_state: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> 'FaultRecoveryManager':
        if cls._instance is None:
            cls._instance = FaultRecoveryManager()
        return cls._instance

    async def handle_failure(self, agent_id: str, error: Exception,
                           failure_type: FailureType = None) -> Dict[str, Any]:
        """智能故障处理"""
        if failure_type is None:
            failure_type = self._classify_failure(error)

        record = FailureRecord(
            timestamp=datetime.now(),
            agent_id=agent_id,
            failure_type=failure_type,
            error_message=str(error)
        )
        self.failure_history.append(record)
        self.failure_count[agent_id] = self.failure_count.get(agent_id, 0) + 1

        if self._is_circuit_breaker_open(agent_id):
            return await self._handle_circuit_breaker_open(agent_id)

        recovery_action = self.recovery_strategies.get(failure_type, "retry_with_backoff")

        if recovery_action == "retry_with_backoff":
            return await self._retry_with_backoff(agent_id, error, record)
        elif recovery_action == "escalate_to_commander":
            return await self._escalate_to_commander(agent_id, error, record)
        elif recovery_action == "use_cache_fallback":
            return await self._use_cache_fallback(agent_id, error, record)
        elif recovery_action == "try_alternative_tool":
            return await self._try_alternative_tool(agent_id, error, record)
        elif recovery_action == "restart_agent":
            return await self._restart_agent(agent_id, error, record)

        return await self._activate_degraded_mode(agent_id, error, record)

    def _classify_failure(self, error: Exception) -> FailureType:
        """根据异常信息分类故障类型"""
        error_str = str(error).lower()

        if "timeout" in error_str or "timed out" in error_str:
            return FailureType.AGENT_TIMEOUT
        elif "permission denied" in error_str or "opa" in error_str:
            return FailureType.OPA_DENIAL
        elif "graphiti" in error_str or "neo4j" in error_str:
            return FailureType.GRAPHITI_UNAVAILABLE
        elif "connection" in error_str or "network" in error_str:
            return FailureType.NETWORK_ERROR
        elif "tool" in error_str or "skill" in error_str:
            return FailureType.TOOL_EXECUTION_ERROR
        else:
            return FailureType.UNEXPECTED_EXCEPTION

    async def _retry_with_backoff(self, agent_id: str, error: Exception,
                                record: FailureRecord) -> Dict[str, Any]:
        """指数退避重试"""
        attempt = record.recovery_attempts + 1

        if attempt > self.max_retries:
            self._trip_circuit_breaker(agent_id)
            return await self._activate_degraded_mode(agent_id, error, record)

        delay = 2 ** (attempt - 1)
        logger.info(f"Agent {agent_id} 重试尝试 {attempt}/{self.max_retries}，延迟 {delay}秒")

        await asyncio.sleep(delay)
        record.recovery_attempts = attempt

        return {
            "action": "retry",
            "attempt": attempt,
            "delay_seconds": delay,
            "circuit_breaker_state": "closed"
        }

    async def _escalate_to_commander(self, agent_id: str, error: Exception,
                                   record: FailureRecord) -> Dict[str, Any]:
        """升级到指挥官决策"""
        logger.warning(f"Agent {agent_id} 权限被拒绝，升级到指挥官决策")

        return {
            "action": "escalate",
            "escalated_to": "commander",
            "reason": "opa_denial",
            "circuit_breaker_state": "closed"
        }

    async def _use_cache_fallback(self, agent_id: str, error: Exception,
                                record: FailureRecord) -> Dict[str, Any]:
        """使用缓存回退"""
        logger.warning(f"Agent {agent_id} Graphiti 不可用，使用缓存回退")
        self.agent_states[agent_id] = AgentState.DEGRADED

        return {
            "action": "fallback",
            "fallback_type": "cache",
            "cached_data_available": True,
            "agent_state": "degraded",
            "circuit_breaker_state": "half_open"
        }

    async def _try_alternative_tool(self, agent_id: str, error: Exception,
                                  record: FailureRecord) -> Dict[str, Any]:
        """尝试替代工具"""
        logger.warning(f"Agent {agent_id} 工具执行失败，尝试替代工具")
        error_tool = self._extract_tool_name(error)

        if error_tool:
            return {
                "action": "alternative_tool",
                "failed_tool": error_tool,
                "alternative_tools": [],
                "recommended_tool": None,
                "circuit_breaker_state": "closed"
            }
        return await self._activate_degraded_mode(agent_id, error, record)

    async def _restart_agent(self, agent_id: str, error: Exception,
                           record: FailureRecord) -> Dict[str, Any]:
        """重启 Agent"""
        logger.warning(f"Agent {agent_id} 发生意外异常，尝试重启")
        self.agent_states[agent_id] = AgentState.RECOVERING

        await asyncio.sleep(2)
        self.agent_states[agent_id] = AgentState.IDLE
        record.resolved = True

        return {
            "action": "restart",
            "restart_successful": True,
            "agent_state": "idle",
            "circuit_breaker_state": "closed"
        }

    async def _activate_degraded_mode(self, agent_id: str, error: Exception,
                                    record: FailureRecord) -> Dict[str, Any]:
        """激活降级模式"""
        logger.error(f"Agent {agent_id} 进入降级模式")
        self.agent_states[agent_id] = AgentState.DEGRADED

        if "intelligence" in agent_id:
            return {
                "action": "degraded",
                "degraded_mode": "cached_intelligence",
                "capabilities": ["read_only_cache", "basic_analysis"],
                "limitations": ["no_real_time_data", "no_direct_queries"],
                "circuit_breaker_state": "open"
            }
        elif "operations" in agent_id:
            return {
                "action": "degraded",
                "degraded_mode": "manual_operations",
                "capabilities": ["basic_commands", "status_reporting"],
                "limitations": ["no_autonomous_actions", "no_complex_planning"],
                "circuit_breaker_state": "open"
            }
        elif "commander" in agent_id:
            return {
                "action": "degraded",
                "degraded_mode": "rule_based_commander",
                "capabilities": ["predefined_rules", "basic_decision_making"],
                "limitations": ["no_ai_analysis", "no_adaptive_strategies"],
                "circuit_breaker_state": "open"
            }
        return {
            "action": "degraded",
            "degraded_mode": "basic_functionality",
            "circuit_breaker_state": "open"
        }

    def _is_circuit_breaker_open(self, agent_id: str) -> bool:
        """检查断路器是否打开"""
        if agent_id not in self.circuit_breaker_state:
            return False

        state = self.circuit_breaker_state[agent_id]

        if state["state"] == "open":
            opened_at = state["opened_at"]
            reset_time = timedelta(seconds=self.circuit_breaker_reset_time)

            if datetime.now() - opened_at > reset_time:
                state["state"] = "half_open"
                state["test_request_sent"] = False
                return False
            return True

        return False

    def _trip_circuit_breaker(self, agent_id: str):
        """触发断路器"""
        self.circuit_breaker_state[agent_id] = {
            "state": "open",
            "opened_at": datetime.now(),
            "failure_count": self.failure_count.get(agent_id, 0),
            "last_error": self.failure_history[-1].error_message if self.failure_history else ""
        }
        logger.warning(f"断路器已触发: {agent_id}，状态: open")

    async def _handle_circuit_breaker_open(self, agent_id: str) -> Dict[str, Any]:
        """处理断路器打开状态"""
        state = self.circuit_breaker_state[agent_id]
        time_remaining = self.circuit_breaker_reset_time - (datetime.now() - state["opened_at"]).total_seconds()

        return {
            "action": "circuit_breaker_open",
            "state": "open",
            "time_remaining_seconds": max(0, time_remaining),
            "failure_count": state["failure_count"],
            "recommendation": "等待断路器重置或切换到降级模式"
        }

    def _extract_tool_name(self, error: Exception) -> Optional[str]:
        """从异常中提取工具名称"""
        import re
        error_str = str(error)

        tool_pattern = r"tool\s+['\"]([^'\"]+)['\"]"
        match = re.search(tool_pattern, error_str, re.IGNORECASE)
        if match:
            return match.group(1)

        skill_pattern = r"skill\s+['\"]([^'\"]+)['\"]"
        match = re.search(skill_pattern, error_str, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def get_agent_state(self, agent_id: str) -> AgentState:
        """获取 Agent 当前状态"""
        return self.agent_states.get(agent_id, AgentState.IDLE)

    def get_failure_summary(self) -> Dict[str, Any]:
        """获取故障汇总"""
        return {
            "total_failures": len(self.failure_history),
            "agent_states": {k: v.value for k, v in self.agent_states.items()},
            "failure_count": self.failure_count,
            "open_circuit_breakers": [
                aid for aid, state in self.circuit_breaker_state.items()
                if state.get("state") == "open"
            ]
        }