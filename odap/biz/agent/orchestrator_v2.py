"""
Swarm 编排器 v2 - OODA 循环 + 故障恢复 + 状态持久化

功能：
- OODA 循环（Observe-Orient-Decide-Act）
- 故障恢复机制
- 状态持久化
- 多 Agent 协同
"""

import sys
import os
import json
import time
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import deque

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.base_v2 import get_registry_v2, SkillExecutorV2

try:
    from opa_service_v2 import OPAManagerV2
    OPA_AVAILABLE = True
except ImportError:
    OPA_AVAILABLE = False


class AgentState(Enum):
    """Agent 状态"""
    IDLE = "idle"
    OBSERVING = "observing"
    ORIENTING = "orienting"
    DECIDING = "deciding"
    ACTING = "acting"
    WAITING = "waiting"
    FAILED = "failed"
    RECOVERING = "recovering"


class RecoveryStrategy(Enum):
    """恢复策略"""
    RETRY = "retry"
    FALLBACK = "fallback"
    ESCALATE = "escalate"
    ABORT = "abort"


@dataclass
class OODACycle:
    """OODA 循环状态"""
    observe_result: Dict[str, Any] = field(default_factory=dict)
    orient_result: Dict[str, Any] = field(default_factory=dict)
    decide_result: Dict[str, Any] = field(default_factory=dict)
    act_result: Dict[str, Any] = field(default_factory=dict)
    cycle_id: str = ""
    started_at: str = ""
    completed_at: Optional[str] = None
    duration_ms: float = 0


@dataclass
class AgentRecovery:
    """Agent 恢复信息"""
    attempt: int
    strategy: str
    error: str
    timestamp: str
    success: bool


@dataclass
class AgentContext:
    """Agent 执行上下文"""
    task_id: str
    user_id: str
    user_role: str
    query: str
    intent: str
    entities: List[str] = field(default_factory=list)
    state: AgentState = AgentState.IDLE
    current_cycle: Optional[OODACycle] = None
    previous_cycles: List[OODACycle] = field(default_factory=list)
    recovery_info: List[AgentRecovery] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DomainSwarmV2:
    """
    DomainSwarm 编排器 v2

    实现 OODA 循环、多 Agent 协同、故障恢复
    """

    def __init__(self, user_role: str = "pilot", use_opa: bool = True):
        self.user_role = user_role
        self.skill_registry = get_registry_v2()
        self.skill_executor = self.skill_registry.get_executor()

        if use_opa and OPA_AVAILABLE:
            self.opa_manager = OPAManagerV2()
        else:
            self.opa_manager = None

        self._active_tasks: Dict[str, AgentContext] = {}
        self._task_history: List[AgentContext] = []
        self._lock = threading.RLock()
        self._max_history = 100
        self._recovery_config = {
            "max_attempts": 3,
            "retry_delay_ms": 500,
            "fallback_enabled": True,
            "escalation_timeout_ms": 30000
        }

    async def run_task(self, query: str, user_id: str = "system",
                      context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        运行任务（异步 OODA 循环）

        Args:
            query: 用户查询
            user_id: 用户 ID
            context: 额外上下文

        Returns:
            执行结果
        """
        import uuid
        task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"

        agent_context = AgentContext(
            task_id=task_id,
            user_id=user_id,
            user_role=self.user_role,
            query=query,
            intent="",
            metadata=context or {}
        )

        with self._lock:
            self._active_tasks[task_id] = agent_context

        try:
            observe_result = await self._observe(agent_context)
            agent_context.state = AgentState.ORIENTING

            orient_result = await self._orient(agent_context, observe_result)
            agent_context.state = AgentState.DECIDING

            decide_result = await self._decide(agent_context, orient_result)
            agent_context.state = AgentState.ACTING

            act_result = await self._act(agent_context, decide_result)

            agent_context.state = AgentState.IDLE
            return {
                "task_id": task_id,
                "success": True,
                "result": act_result,
                "cycle": {
                    "observe": observe_result,
                    "orient": orient_result,
                    "decide": decide_result,
                    "act": act_result
                }
            }

        except Exception as e:
            agent_context.state = AgentState.FAILED
            return {
                "task_id": task_id,
                "success": False,
                "error": str(e),
                "state": agent_context.state.value
            }

        finally:
            with self._lock:
                if task_id in self._active_tasks:
                    del self._active_tasks[task_id]
                self._task_history.append(agent_context)
                if len(self._task_history) > self._max_history:
                    self._task_history.pop(0)

    async def _observe(self, context: AgentContext) -> Dict[str, Any]:
        """OODA - Observe（观察）"""
        context.state = AgentState.OBSERVING

        query = context.query.lower()

        entities = []
        if "雷达" in query:
            entities.append("radar")
        if "坦克" in query:
            entities.append("tank")
        if "医院" in query:
            entities.append("hospital")
        if "部队" in query or "单位" in query:
            entities.append("unit")

        context.entities = entities

        return {
            "query": context.query,
            "entities": entities,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": {
                "user_role": context.user_role,
                "user_id": context.user_id
            }
        }

    async def _orient(self, context: AgentContext, observe_result: Dict[str, Any]) -> Dict[str, Any]:
        """OODA - Orient（定向）"""
        query = context.query.lower()

        intent = "unknown"
        required_skills = []

        if any(kw in query for kw in ["搜索", "查找", "看看"]):
            if "雷达" in query:
                intent = "search_radar"
                required_skills = ["search_radar"]
            elif "医院" in query:
                intent = "search_hospital"
                required_skills = ["search_hospital"]

        elif any(kw in query for kw in ["分析", "态势"]):
            intent = "analyze_domain"
            required_skills = ["analyze_domain"]

        elif any(kw in query for kw in ["打击", "攻击", "目标"]):
            intent = "recommend_strike"
            required_skills = ["recommend_strike_targets", "attack_target"]

        elif any(kw in query for kw in ["力量", "对比"]):
            intent = "analyze_force"
            required_skills = ["analyze_force_comparison"]

        elif any(kw in query for kw in ["指挥", "命令"]):
            intent = "command"
            required_skills = ["command_unit"]

        context.intent = intent

        return {
            "intent": intent,
            "required_skills": required_skills,
            "confidence": 0.85,
            "reasoning": f"基于查询 '{context.query}' 识别为 {intent}"
        }

    async def _decide(self, context: AgentContext, orient_result: Dict[str, Any]) -> Dict[str, Any]:
        """OODA - Decide（决策）"""
        intent = orient_result.get("intent", "unknown")
        required_skills = orient_result.get("required_skills", [])

        action_plan = {
            "intent": intent,
            "steps": [],
            "expected_outcome": ""
        }

        if intent == "search_radar":
            import re
            area_match = re.search(r'([A-E])\s*区', context.query)
            area = area_match.group(1) if area_match else None
            action_plan["steps"] = [
                {"skill": "search_radar", "params": {"area": area}}
            ]
            action_plan["expected_outcome"] = "返回雷达位置列表"

        elif intent == "analyze_domain":
            action_plan["steps"] = [
                {"skill": "analyze_domain", "params": {}}
            ]
            action_plan["expected_outcome"] = "返回领域态势分析"

        elif intent == "recommend_strike":
            action_plan["steps"] = [
                {"skill": "recommend_strike_targets", "params": {"user_role": context.user_role}},
                {"skill": "attack_target", "params": {"user_role": context.user_role}}
            ]
            action_plan["expected_outcome"] = "返回打击目标推荐或执行结果"

        elif intent == "analyze_force":
            action_plan["steps"] = [
                {"skill": "analyze_force_comparison", "params": {}}
            ]
            action_plan["expected_outcome"] = "返回力量对比分析"

        return action_plan

    async def _act(self, context: AgentContext, decide_result: Dict[str, Any]) -> Dict[str, Any]:
        """OODA - Act（行动）"""
        steps = decide_result.get("steps", [])
        results = []

        for step in steps:
            skill_name = step.get("skill")
            params = step.get("params", {})

            if self.opa_manager and context.user_role:
                allowed = self.opa_manager.check_permission(
                    context.user_role, skill_name, {"type": "skill"}
                )
                if not allowed:
                    results.append({
                        "skill": skill_name,
                        "success": False,
                        "error": f"Permission denied for role {context.user_role}"
                    })
                    continue

            retry_count = 0
            max_retries = self._recovery_config["max_attempts"]
            last_error = None

            while retry_count < max_retries:
                try:
                    result = await self._execute_skill_with_recovery(
                        context, skill_name, params, retry_count
                    )
                    if result.success:
                        results.append({
                            "skill": skill_name,
                            "success": True,
                            "data": result.data
                        })
                        break
                    else:
                        last_error = result.error
                        retry_count += 1
                        if retry_count < max_retries:
                            await asyncio.sleep(self._recovery_config["retry_delay_ms"] / 1000)

                except Exception as e:
                    last_error = str(e)
                    retry_count += 1
                    if retry_count < max_retries:
                        await asyncio.sleep(self._recovery_config["retry_delay_ms"] / 1000)

            if retry_count >= max_retries:
                results.append({
                    "skill": skill_name,
                    "success": False,
                    "error": f"Failed after {max_retries} attempts: {last_error}"
                })

        return {
            "action_plan": decide_result,
            "step_results": results,
            "overall_success": all(r.get("success", False) for r in results)
        }

    async def _execute_skill_with_recovery(self, context: AgentContext,
                                         skill_name: str, params: Dict,
                                         attempt: int) -> Any:
        """带恢复的 Skill 执行"""
        try:
            result = self.skill_executor.execute(
                skill_name, params, user={"role": context.user_role}
            )
            return result
        except Exception as e:
            context.recovery_info.append(AgentRecovery(
                attempt=attempt,
                strategy=RecoveryStrategy.RETRY.value,
                error=str(e),
                timestamp=datetime.now(timezone.utc).isoformat(),
                success=False
            ))
            raise

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        with self._lock:
            for task in self._task_history:
                if task.task_id == task_id:
                    return {
                        "task_id": task.task_id,
                        "state": task.state.value,
                        "intent": task.intent,
                        "recovery_attempts": len(task.recovery_info)
                    }

            if task_id in self._active_tasks:
                task = self._active_tasks[task_id]
                return {
                    "task_id": task.task_id,
                    "state": task.state.value,
                    "intent": task.intent
                }

        return None

    def get_task_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取任务历史"""
        with self._lock:
            history = self._task_history[-limit:]
            return [{
                "task_id": t.task_id,
                "user_id": t.user_id,
                "user_role": t.user_role,
                "query": t.query,
                "intent": t.intent,
                "state": t.state.value,
                "recovery_count": len(t.recovery_info)
            } for t in reversed(history)]

    def get_active_tasks(self) -> List[str]:
        """获取活跃任务 ID"""
        with self._lock:
            return list(self._active_tasks.keys())


class SelfCorrectingOrchestratorV2:
    """
    自校正编排器 v2

    基于 DomainSwarmV2 的高级封装，支持：
    - 同步接口
    - 错误恢复
    - 状态跟踪
    """

    def __init__(self, user_role: str = "pilot"):
        self.user_role = user_role
        self.swarm = DomainSwarmV2(user_role=user_role)

    def run(self, query: str, user_id: str = "system") -> Dict[str, Any]:
        """同步运行查询"""
        return asyncio.run(self.swarm.run_task(query, user_id))

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self.swarm.get_task_status(task_id)


if __name__ == "__main__":
    print("Swarm 编排器 v2 测试")

    print("\n=== 测试自校正编排器 ===")
    orchestrator = SelfCorrectingOrchestratorV2(user_role="commander")

    print("\n1. 测试雷达搜索:")
    result = orchestrator.run("帮我看看 B 区有没有雷达")
    print(f"  任务 ID: {result.get('task_id')}")
    print(f"  成功: {result.get('success')}")
    if result.get('cycle'):
        print(f"  意图: {result['cycle']['orient'].get('intent')}")

    print("\n2. 测试领域分析:")
    result = orchestrator.run("分析当前领域态势")
    print(f"  任务 ID: {result.get('task_id')}")
    print(f"  成功: {result.get('success')}")

    print("\n3. 测试打击推荐:")
    result = orchestrator.run("我想打击 A 区的雷达目标")
    print(f"  任务 ID: {result.get('task_id')}")
    print(f"  成功: {result.get('success')}")

    print("\n4. 测试任务历史:")
    history = orchestrator.swarm.get_task_history(limit=10)
    print(f"  历史任务数: {len(history)}")

    print("\n5. 测试活跃任务:")
    active = orchestrator.swarm.get_active_tasks()
    print(f"  活跃任务数: {len(active)}")
