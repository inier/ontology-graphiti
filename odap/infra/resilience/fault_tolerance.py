"""
故障恢复管理器模块
实现 Agent 故障检测、分类、恢复策略

Phase 2 扩展: 故障恢复与状态管理

集成 CircuitBreaker（circuit_breaker.py），不再重复实现断路器逻辑。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Callable

from odap.biz.core.agent.swarm_orchestrator import AgentState
from odap.infra.resilience.circuit_breaker import CircuitBreaker, get_circuit_breaker, CircuitOpenError

logger = logging.getLogger("fault_tolerance")


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
    """故障恢复管理器

    集成 CircuitBreaker（来自 circuit_breaker.py），不再自行实现断路器逻辑。
    """

    _instance: Optional['FaultRecoveryManager'] = None

    def __init__(self):
        self.agent_states: Dict[str, AgentState] = {}
        self.failure_history: List[FailureRecord] = []
        self.failure_count: Dict[str, int] = {}
        self._cache: Dict[str, Any] = {}
        self.recovery_strategies: Dict[FailureType, str] = {
            FailureType.AGENT_TIMEOUT: "retry_with_backoff",
            FailureType.OPA_DENIAL: "escalate_to_commander",
            FailureType.GRAPHITI_UNAVAILABLE: "use_cache_fallback",
            FailureType.NETWORK_ERROR: "retry_with_backoff",
            FailureType.TOOL_EXECUTION_ERROR: "try_alternative_tool",
            FailureType.UNEXPECTED_EXCEPTION: "restart_agent"
        }
        self.max_retries = 3
        # 使用 CircuitBreaker 替代自实现的断路器
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

    def _get_circuit_breaker(self, agent_id: str) -> CircuitBreaker:
        """获取或创建指定 agent 的 CircuitBreaker"""
        if agent_id not in self._circuit_breakers:
            self._circuit_breakers[agent_id] = get_circuit_breaker(
                f"fault_recovery_{agent_id}",
                failure_threshold_pct=0.5,
            )
        return self._circuit_breakers[agent_id]

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

        # 使用 CircuitBreaker 检查熔断状态
        cb = self._get_circuit_breaker(agent_id)
        try:
            cb._pre_call_check()
        except CircuitOpenError:
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
                                record: FailureRecord,
                                func: Optional[Callable] = None) -> Dict[str, Any]:
        """指数退避重试

        如果提供了 func，则真正重试原始函数；
        否则返回重试指示，由调用方决定是否重试。
        """
        attempt = record.recovery_attempts + 1

        if attempt > self.max_retries:
            # 超过重试上限，触发熔断并降级
            cb = self._get_circuit_breaker(agent_id)
            cb._finish_call(record.timestamp.timestamp(), False, str(error))
            return await self._activate_degraded_mode(agent_id, error, record)

        delay = 2 ** (attempt - 1)
        logger.info(f"Agent {agent_id} 重试尝试 {attempt}/{self.max_retries}，延迟 {delay}秒")

        await asyncio.sleep(delay)
        record.recovery_attempts = attempt

        # 如果提供了原始函数，真正执行重试
        if func is not None:
            try:
                result = await func() if asyncio.iscoroutinefunction(func) else func()
                # 重试成功，记录成功并返回
                cb = self._get_circuit_breaker(agent_id)
                cb._finish_call(record.timestamp.timestamp(), True, None)
                record.resolved = True
                return {"action": "retry_succeeded", "attempt": attempt, "result": result}
            except Exception as retry_error:
                # 重试失败，递归重试
                record.error_message = str(retry_error)
                return await self._retry_with_backoff(agent_id, retry_error, record, func)

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

        cached_data = self._cache.get(agent_id)
        cached_available = cached_data is not None

        if cached_available:
            logger.info(f"Agent {agent_id} 缓存命中，使用缓存数据回退")
        else:
            logger.warning(f"Agent {agent_id} 无可用缓存数据")

        return {
            "action": "fallback",
            "fallback_type": "cache",
            "cached_data_available": cached_available,
            "cached_data": cached_data if cached_available else None,
            "agent_state": "degraded",
            "circuit_breaker_state": "half_open"
        }

    async def _try_alternative_tool(self, agent_id: str, error: Exception,
                                  record: FailureRecord) -> Dict[str, Any]:
        """尝试替代工具"""
        logger.warning(f"Agent {agent_id} 工具执行失败，尝试替代工具")
        error_tool = self._extract_tool_name(error)

        if error_tool:
            alternative_tools = self._find_alternative_tools(error_tool)

            if alternative_tools:
                recommended = alternative_tools[0]
                logger.info(f"Agent {agent_id} 找到替代工具: {recommended['name']}")
                return {
                    "action": "alternative_tool",
                    "status": "alternative_found",
                    "failed_tool": error_tool,
                    "alternative_tools": alternative_tools,
                    "recommended_tool": recommended,
                    "circuit_breaker_state": "closed"
                }
            else:
                logger.warning(f"Agent {agent_id} 未找到工具 '{error_tool}' 的替代工具")
                return {
                    "action": "alternative_tool",
                    "status": "no_alternative",
                    "failed_tool": error_tool,
                    "alternative_tools": [],
                    "recommended_tool": None,
                    "circuit_breaker_state": "half_open"
                }
        return await self._activate_degraded_mode(agent_id, error, record)

    def _find_alternative_tools(self, failed_tool: str) -> List[Dict[str, Any]]:
        """从 SkillRegistry 中搜索具有相同或相似功能的替代技能"""
        alternatives = []
        try:
            from odap.tools import get_registry
            registry = get_registry()
            all_skills = registry.list_skills()

            # 按类别匹配：查找与失败工具同类别的其他工具
            failed_skill = registry.get(failed_tool)
            if failed_skill is not None:
                failed_category = failed_skill.metadata.category
                for skill_info in all_skills:
                    if skill_info["name"] != failed_tool and skill_info.get("category") == failed_category:
                        alternatives.append({
                            "name": skill_info["name"],
                            "description": skill_info.get("description", ""),
                            "category": skill_info.get("category", ""),
                            "match_reason": "same_category"
                        })

            # 按名称关键词匹配：查找名称中包含相似关键词的工具
            failed_keywords = set(failed_tool.lower().replace("_", " ").split())
            for skill_info in all_skills:
                name = skill_info["name"]
                if name == failed_tool or any(alt["name"] == name for alt in alternatives):
                    continue
                skill_keywords = set(name.lower().replace("_", " ").split())
                if failed_keywords & skill_keywords:
                    alternatives.append({
                        "name": name,
                        "description": skill_info.get("description", ""),
                        "category": skill_info.get("category", ""),
                        "match_reason": "keyword_overlap"
                    })
        except Exception as e:
            logger.debug(f"搜索替代工具时出错: {e}")

        return alternatives

    async def _restart_agent(self, agent_id: str, error: Exception,
                           record: FailureRecord) -> Dict[str, Any]:
        """重启 Agent"""
        logger.warning(f"Agent {agent_id} 发生意外异常，尝试重启")
        self.agent_states[agent_id] = AgentState.RECOVERING

        restart_successful = False
        restart_method = None

        # 尝试从 DomainSwarm 获取 Agent 实例并调用其重置方法
        try:
            from odap.biz.core.agent.swarm_orchestrator import DomainSwarm
            swarm = DomainSwarm()
            agent = swarm.agents.get(agent_id)
            if agent is not None:
                if hasattr(agent, 'reset') and callable(getattr(agent, 'reset')):
                    await agent.reset() if asyncio.iscoroutinefunction(agent.reset) else agent.reset()
                    restart_successful = True
                    restart_method = "reset"
                    logger.info(f"Agent {agent_id} 通过 reset() 重启成功")
                elif hasattr(agent, 'initialize') and callable(getattr(agent, 'initialize')):
                    await agent.initialize() if asyncio.iscoroutinefunction(agent.initialize) else agent.initialize()
                    restart_successful = True
                    restart_method = "initialize"
                    logger.info(f"Agent {agent_id} 通过 initialize() 重启成功")
                else:
                    logger.warning(f"Agent {agent_id} 没有 reset() 或 initialize() 方法，无法真正重启")
            else:
                logger.warning(f"Agent {agent_id} 未在 DomainSwarm 中找到，无法真正重启")
        except Exception as e:
            logger.warning(f"Agent {agent_id} 重启过程中发生异常: {e}")

        if restart_successful:
            self.agent_states[agent_id] = AgentState.IDLE
            record.resolved = True
        else:
            self.agent_states[agent_id] = AgentState.DEGRADED
            record.resolved = False

        return {
            "action": "restart",
            "restart_successful": restart_successful,
            "restart_method": restart_method,
            "agent_state": self.agent_states[agent_id].value,
            "circuit_breaker_state": "closed" if restart_successful else "half_open"
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

    async def _handle_circuit_breaker_open(self, agent_id: str) -> Dict[str, Any]:
        """处理 CircuitBreaker 打开状态（熔断）"""
        cb = self._get_circuit_breaker(agent_id)
        state = cb.get_state()

        return {
            "action": "circuit_breaker_open",
            "state": state.value if hasattr(state, 'value') else str(state),
            "failure_count": self.failure_count.get(agent_id, 0),
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

    def cache_result(self, agent_id: str, result: Any):
        """缓存 Agent 执行结果，供故障时回退使用"""
        self._cache[agent_id] = result
        logger.debug(f"Agent {agent_id} 结果已缓存")

    async def execute_with_tolerance(self, agent_id: str, func, *args, **kwargs) -> Dict[str, Any]:
        """带容错执行的包装方法：成功时缓存结果，失败时触发故障处理并自动重试"""
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self.cache_result(agent_id, result)
            return {"status": "success", "result": result}
        except Exception as e:
            failure_type = self._classify_failure(e)
            recovery_action = self.recovery_strategies.get(failure_type, "retry_with_backoff")

            # 对于重试策略，传入原始函数以实现真正重试
            if recovery_action == "retry_with_backoff":
                record = FailureRecord(
                    timestamp=datetime.now(),
                    agent_id=agent_id,
                    failure_type=failure_type,
                    error_message=str(e),
                )
                self.failure_history.append(record)
                self.failure_count[agent_id] = self.failure_count.get(agent_id, 0) + 1

                retry_fn = lambda: func(*args, **kwargs)
                retry_result = await self._retry_with_backoff(agent_id, e, record, func=retry_fn)
                if retry_result.get("action") == "retry_succeeded":
                    return {"status": "success", "result": retry_result["result"]}
                return retry_result

            return await self.handle_failure(agent_id, e, failure_type)

    def get_failure_summary(self) -> Dict[str, Any]:
        """获取故障汇总"""
        open_cbs = []
        for aid, cb in self._circuit_breakers.items():
            state = cb.get_state()
            state_value = state.get("state", "closed") if isinstance(state, dict) else getattr(state, "value", str(state))
            if state_value == "open":
                open_cbs.append(aid)

        return {
            "total_failures": len(self.failure_history),
            "agent_states": {k: v.value if hasattr(v, 'value') else str(v) for k, v in self.agent_states.items()},
            "failure_count": self.failure_count,
            "open_circuit_breakers": open_cbs
        }