"""
Swarm 编排器核心模块
基于 OpenHarness QueryEngine 的多 Agent 协同编排器，实现领域三 Agent（Director/Intelligence/Operations）的 OODA 循环协同。

核心设计：
- 三 Agent 均为 OH QueryEngine 的不同配置实例（通过 system_prompt 区分角色）
- OODA 各阶段委托给 OHSwarmAgent.run()，由 OH QueryEngine 驱动 LLM→工具选择→执行→观察→循环
- OH 不可用时降级到规则引擎逻辑
- 保留 OODA 5 阶段（Observe→Orient→Decide→Act→Evaluate）+ 条件性 Re-loop
"""

import json
import os
import uuid
import time

from odap.infra.observability.instruments import agent_span
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger("swarm_orchestrator")


from odap.biz.core.agent.agent_factory import AgentType, AgentState
from odap.biz.core.agent.interfaces.ooda_interface import OODAInterface, OODALifecycleHook
from odap.biz.core.agent.interfaces.iswarm_adapter import ISwarmAdapter


class OODAPhase(str, Enum):
    """OODA 阶段（7 阶段完整模型）"""
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"
    EVALUATE = "evaluate"


class OODAStatus(str, Enum):
    """OODA 执行状态"""
    STARTED = "started"
    COMPLETED = "completed"
    WAITING_CONFIRMATION = "waiting_confirmation"
    EXECUTING = "executing"
    CANCELLED = "cancelled"
    ERROR = "error"



@dataclass
class OODAProgress:
    """OODA 执行进度"""
    phase: OODAPhase
    status: OODAStatus
    agent: AgentType
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "status": self.status.value,
            "agent": self.agent.value,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MissionResult:
    """任务执行结果"""
    mission_id: str
    success: bool
    phases_completed: List[OODAPhase]
    final_decision: Optional[Dict[str, Any]] = None
    execution_time_ms: float = 0.0
    graphiti_episodes: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "success": self.success,
            "phases_completed": [p.value for p in self.phases_completed],
            "final_decision": self.final_decision,
            "execution_time_ms": self.execution_time_ms,
            "graphiti_episodes": self.graphiti_episodes,
            "error_message": self.error_message,
        }


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    agent_type: AgentType
    model: str
    role: str
    tools: List[str]
    permission_level: str
    memory_backend: str = "graphiti"
    requires_opa_approval: bool = False


# ---------------------------------------------------------------------------
# OHSwarmAgent — 基于 OH QueryEngine 的统一 Agent 代理
# ---------------------------------------------------------------------------

# 导入 OH 集成层
try:
    from odap.infra.openharness.engine_adapter import (
        OHQueryEngineFactory,
        OPENHARNESS_AVAILABLE,
    )
except ImportError:
    OPENHARNESS_AVAILABLE = False

# 导入韧性基础设施
try:
    from odap.infra.resilience.circuit_breaker import get_circuit_breaker, CircuitOpenError
    RESILIENCE_AVAILABLE = True
except ImportError:
    RESILIENCE_AVAILABLE = False


# Agent 角色 → system_prompt 映射
AGENT_SYSTEM_PROMPTS = {
    "intelligence": """你是领域情报分析 Agent（Intelligence Agent）。你的职责是：
1. 感知（Observe）：收集领域情报数据，包括实体状态、资源对比、威胁评估
2. 理解（Orient）：分析情报模式，结合历史数据识别威胁等级
3. 评估（Evaluate）：评估行动效果，判断是否需要持续监控

可用工具：search_sensor, analyze_domain, analyze_resource_comparison, analyze_equipment_capabilities,
analyze_public_assets, analyze_incident_events, analyze_entity_status, query_ontology

输出格式要求（JSON）：
{
  "summary": "一句话总结",
  "threat_level": "low/medium/high/critical",
  "opponent_units": [...],
  "recommendations": [...],
  "requires_monitoring": true/false
}

重要规则：
- 不要编造数据，只用工具返回的真实数据
- 如果工具返回错误，如实报告
- 最后一步必须返回 JSON 格式的报告""",

    "director": """你是决策负责 Agent（Director Agent）。你的职责是：
1. 决策（Decide）：基于情报分析结果，制定行动方案
2. 权衡风险与收益，选择最优方案
3. 在威胁等级为 critical 时，标记需要人工确认

决策输出格式要求（JSON）：
{
  "situation_summary": "态势总结",
  "threat_level": "low/medium/high/critical",
  "recommended_action": {"id": "...", "type": "engage|observe|coordinate", "description": "...", "targets": [...], "risk_level": "low|medium|high"},
  "options": [...],
  "requires_confirmation": true/false,
  "decision_time": "ISO时间戳"
}

决策原则：
- 优先选择中等风险的方案（风险可控）
- 高威胁时必须标记 requires_confirmation
- 无情报时默认选择 observe（持续监控）""",

    "operations": """你是执行操作 Agent（Operations Agent）。你的职责是：
1. 执行（Act）：根据负责人的决策，执行具体操作
2. 调用工具完成执行、监控、协调等任务
3. 报告执行结果

可用工具：search_sensor, analyze_domain, analyze_resource_comparison, query_ontology

执行输出格式要求（JSON）：
{
  "status": "completed|cancelled|failed",
  "order_type": "engage|observe|coordinate",
  "results": [...],
  "execution_time": "ISO时间戳"
}

执行规则：
- 严格按负责人的推荐行动执行
- 执行前检查权限（OPA）
- 执行失败时如实报告错误""",
}


class OHSwarmAgent:
    """基于 OpenHarness QueryEngine 的统一 Agent 代理

    每个 OHSwarmAgent 通过不同的 system_prompt 区分角色：
    - intelligence: 情报感知/理解/评估
    - director: 决策指挥
    - operations: 执行操作

    核心机制：
    - 优先通过 OHQueryEngineFactory 创建 QueryEngine 实例
    - QueryEngine 驱动 LLM→工具选择→执行→观察→循环
    - OH 不可用时降级到规则引擎逻辑
    """

    def __init__(self, role: str, agent_type: AgentType, opa_manager=None,
                 write_proxy=None, workspace_id: str = "", scenario_id: str = ""):
        self.role = role
        self.agent_type = agent_type
        self.config = AgentConfig(
            name=role.capitalize(),
            agent_type=agent_type,
            model=get_config("llm.model", "gpt-4"),
            role=role,
            tools=["*"],
            permission_level=role,
        )
        self.opa_manager = opa_manager
        self._write_proxy = write_proxy
        self.state = AgentState.IDLE
        self.workspace_id = workspace_id
        self.scenario_id = scenario_id

        # OH QueryEngine 工厂
        self._engine_factory = OHQueryEngineFactory.get_instance() if OPENHARNESS_AVAILABLE else None

        # 韧性基础设施
        self._circuit_breaker = None
        if RESILIENCE_AVAILABLE:
            self._circuit_breaker = get_circuit_breaker(f"swarm_agent_{role}", failure_threshold_pct=0.5)

        # 缓存从其他 Agent 传递的数据
        self._pending_intel_data: Optional[Dict[str, Any]] = None

    async def run(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """运行 Agent — 优先 OH QueryEngine，降级到规则引擎"""
        self.state = AgentState.RUNNING
        try:
            if self._engine_factory and self._engine_factory.is_available:
                result = await self._run_with_engine(user_input, context)
                if result is not None:
                    self.state = AgentState.IDLE
                    return result

            # 降级到规则引擎
            result = await self._run_fallback(user_input, context)
            self.state = AgentState.IDLE
            return result
        except Exception as e:
            self.state = AgentState.FAILED
            logger.error("OHSwarmAgent(%s) run failed: %s", self.role, e)
            raise

    async def _run_with_engine(self, user_input: str, context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """通过 OH QueryEngine 运行"""
        system_prompt = AGENT_SYSTEM_PROMPTS.get(self.role, AGENT_SYSTEM_PROMPTS["intelligence"])
        max_turns = (context or {}).get("max_turns", 6)

        engine = self._engine_factory.create_engine(
            system_prompt=system_prompt,
            max_turns=max_turns,
            workspace_id=self.workspace_id,
            scenario_id=self.scenario_id,
        )
        if not engine:
            return None

        try:
            if self._circuit_breaker:
                async def _submit():
                    text_parts = []
                    async for event in engine.submit_message(user_input):
                        if hasattr(event, 'text'):
                            text_parts.append(event.text)
                    return "".join(text_parts)

                response_text = await self._circuit_breaker.acall(_submit)
            else:
                text_parts = []
                async for event in engine.submit_message(user_input):
                    if hasattr(event, 'text'):
                        text_parts.append(event.text)
                response_text = "".join(text_parts)

            # 尝试解析 JSON 响应
            return self._parse_response(response_text)

        except CircuitOpenError:
            logger.warning("OHSwarmAgent(%s) circuit breaker open", self.role)
            return None
        except Exception as e:
            logger.warning("OHSwarmAgent(%s) engine failed: %s", self.role, e)
            return None

    async def _run_fallback(self, user_input: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """降级路径：规则引擎逻辑"""
        ctx = context or {}

        if self.role == "intelligence":
            return await self._fallback_intelligence(user_input, ctx)
        elif self.role == "director":
            return await self._fallback_director(user_input, ctx)
        elif self.role == "operations":
            return await self._fallback_operations(user_input, ctx)
        else:
            return {"status": "error", "message": f"Unknown role: {self.role}"}

    async def _fallback_intelligence(self, mission: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligence 降级：直接调用 SKILL_CATALOG"""
        from odap.tools import SKILL_CATALOG

        results = {}
        if "analyze_domain" in SKILL_CATALOG:
            try:
                results["domain"] = SKILL_CATALOG["analyze_domain"]["handler"]()
            except Exception as e:
                logger.warning("analyze_domain failed: %s", e)

        if "analyze_resource_comparison" in SKILL_CATALOG:
            try:
                results["resource_comparison"] = SKILL_CATALOG["analyze_resource_comparison"]["handler"]()
            except Exception as e:
                logger.warning("analyze_resource_comparison failed: %s", e)

        threat_level = "medium"
        if results.get("domain"):
            summary = str(results["domain"])
            if "high" in summary.lower() or "critical" in summary.lower():
                threat_level = "high"
            elif "low" in summary.lower():
                threat_level = "low"

        return {
            "summary": results.get("domain", {}).get("summary", "情报收集完成") if isinstance(results.get("domain"), dict) else "情报收集完成",
            "threat_level": threat_level,
            "opponent_units": results.get("resource_comparison", {}).get("opponent_units", []) if isinstance(results.get("resource_comparison"), dict) else [],
            "own_status": results.get("resource_comparison", {}).get("own_units", []) if isinstance(results.get("resource_comparison"), dict) else [],
            "public_risk": [],
            "recommendations": results.get("domain", {}).get("recommendations", []) if isinstance(results.get("domain"), dict) else [],
            "raw_data": results,
        }

    async def _fallback_director(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Director 降级：基于情报数据的规则决策"""
        intel_data = self._pending_intel_data or context.get("intel_data", {})
        self._pending_intel_data = None

        threat_level = intel_data.get("threat_level", "unknown")
        options = self._generate_options(intel_data)

        return {
            "situation_summary": intel_data.get("summary", "未知态势"),
            "threat_level": threat_level,
            "recommended_action": self._select_best_option(options),
            "options": options,
            "requires_confirmation": threat_level == "critical",
            "decision_time": datetime.now(timezone.utc).isoformat(),
        }

    async def _fallback_operations(self, user_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Operations 降级：直接执行命令"""
        order = context.get("order", {})
        order_type = order.get("type", "observe")
        targets = order.get("targets", [])

        results = []
        for target_id in targets:
            result = await self._execute_action(order_type, target_id, order)
            results.append(result)

        return {
            "status": "completed",
            "order_type": order_type,
            "results": results,
            "execution_time": datetime.now(timezone.utc).isoformat(),
        }

    def _generate_options(self, intel_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成决策选项（Director 降级逻辑）"""
        options = []
        opponent_units = intel_data.get("opponent_units", [])
        if opponent_units:
            options.append({
                "id": "option_1",
                "type": "engage",
                "description": "对对手单位实施精确执行",
                "targets": [u.get("id") for u in opponent_units[:3]],
                "risk_level": "high",
            })

        public_risk = intel_data.get("public_risk", [])
        if not public_risk:
            options.append({
                "id": "option_2",
                "type": "observe",
                "description": "保持监控，持续收集情报",
                "targets": [],
                "risk_level": "low",
            })

        recommendations = intel_data.get("recommendations", [])
        if recommendations:
            options.append({
                "id": "option_3",
                "type": "coordinate",
                "description": recommendations[0] if recommendations else "协调己方",
                "targets": [],
                "risk_level": "medium",
            })

        return options

    def _select_best_option(self, options: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """选择最佳决策选项（Director 降级逻辑）"""
        if not options:
            return None
        for opt in options:
            if opt.get("risk_level") == "medium":
                return opt
        return options[0] if options else None

    async def _execute_action(self, action_type: str, target_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个行动（Operations 降级逻辑）"""
        try:
            if action_type == "engage":
                from odap.tools import SKILL_CATALOG
                if "engage_target" in SKILL_CATALOG:
                    result = SKILL_CATALOG["engage_target"]["handler"](
                        target_id=target_id,
                        user_role=self.config.permission_level
                    )
                    return {"target_id": target_id, "status": "success", "result": result}
            return {"target_id": target_id, "status": "skipped", "reason": "no_handler"}
        except Exception as e:
            logger.error("Action failed %s/%s: %s", action_type, target_id, e)
            return {"target_id": target_id, "status": "failed", "error": str(e)}

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """尝试从 LLM 响应中解析 JSON"""
        if not response_text:
            return {"status": "error", "message": "Empty response"}

        # 尝试直接解析
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 块
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试提取花括号内容
        brace_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # 无法解析 JSON，返回原始文本
        return {"status": "completed", "raw_response": response_text}


class IntentRouter:
    _RULES: List[Dict[str, Any]] = [
        {"keywords": ["分析", "态势", "威胁", "情报", "侦察"], "agent": "intelligence", "confidence": 0.95},
        {"keywords": ["决策", "方案", "指挥", "选择", "判断"], "agent": "director", "confidence": 0.95},
        {"keywords": ["执行", "行动", "部署", "调度"], "agent": "operations", "confidence": 0.95},
        {"keywords": ["搜索", "查询", "查找", "检索", "传感器"], "agent": "intelligence", "confidence": 0.90},
        {"keywords": ["交锋", "目标", "摧毁", "执行力"], "agent": "operations", "confidence": 0.90},
        {"keywords": ["推荐", "建议", "评估", "对比"], "agent": "director", "confidence": 0.85},
        # P3-fix: 三国领域关键词路由
        {"keywords": ["三国", "演义", "曹操", "刘备", "孙权", "诸葛亮", "关羽", "张飞", "赵云", "周瑜"], "agent": "intelligence", "confidence": 0.95},
        {"keywords": ["势力", "魏", "蜀", "吴", "冲突", "赤壁", "官渡", "夷陵"], "agent": "intelligence", "confidence": 0.90},
        {"keywords": ["推演", "如果", "假设", "模拟", "历史走向"], "agent": "director", "confidence": 0.90},
        {"keywords": ["人物", "事件", "时间线", "年表", "关系"], "agent": "intelligence", "confidence": 0.85},
    ]

    def __init__(self, llm_available: Optional[bool] = None):
        self._llm_available_override = llm_available
        self._llm_available: Optional[bool] = None  # 懒加载

    @property
    def llm_available(self) -> bool:
        """懒加载检测 LLM 可用性（延迟导入 infra.security）"""
        if self._llm_available_override is not None:
            return self._llm_available_override
        if self._llm_available is None:
            try:
                from odap.infra.security import security_config
                self._llm_available = bool(security_config.OPENAI_API_KEY)
            except Exception:
                self._llm_available = False
        return self._llm_available

    def route(self, intent: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rule_result = self._rule_route(intent)
        if rule_result and rule_result["confidence"] >= 0.9:
            return rule_result

        if self.llm_available:
            llm_result = self._llm_route(intent, context)
            if llm_result:
                return llm_result

        if rule_result:
            return rule_result

        return {"agent": "intelligence", "confidence": 0.5, "source": "default"}

    def _rule_route(self, intent: str) -> Optional[Dict[str, Any]]:
        best_match = None
        best_score = 0.0
        intent_lower = intent.lower()
        for rule in self._RULES:
            score = sum(1 for kw in rule["keywords"] if kw in intent_lower)
            if score > best_score:
                best_score = score
                best_match = rule
        if best_match and best_score > 0:
            return {
                "agent": best_match["agent"],
                "confidence": min(best_match["confidence"], best_match["confidence"] * (best_score / len(best_match["keywords"]) + 0.5)),
                "source": "rule",
                "matched_keywords": [kw for kw in best_match["keywords"] if kw in intent_lower],
            }
        return None

    def _llm_route(self, intent: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        try:
            import httpx
            from odap.infra.security import security_config
            base = security_config.OPENAI_API_BASE.rstrip("/")
            if base.endswith("/chat/completions"):
                base = base[: -len("/chat/completions")]
            if not base.startswith("http://") and not base.startswith("https://"):
                base = "https://" + base
            resp = httpx.post(
                f"{base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {security_config.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": security_config.OPENAI_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是意图路由器。根据用户意图判断应分配给哪个Agent。只返回JSON: {\"agent\": \"intelligence\"|\"director\"|\"operations\", \"confidence\": 0.0-1.0}"},
                        {"role": "user", "content": intent},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 100,
                },
                timeout=10.0,
            )
            if resp.status_code == 200:
                import json as _json
                content = resp.json()["choices"][0]["message"]["content"]
                data = _json.loads(content)
                if data.get("agent") in ("intelligence", "director", "operations"):
                    return {"agent": data["agent"], "confidence": float(data.get("confidence", 0.7)), "source": "llm"}
        except Exception as e:
            logger.warning(f"LLM routing fallback: {e}")
        return None


class SubAgentPlanner:

    def plan(self, intent: str, agent: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        tasks = []
        ctx = context or {}

        if agent == "intelligence":
            tasks.append({"sub_agent": "intelligence", "action": "gather_intelligence", "params": {"mission": intent, "context": ctx}})
            tasks.append({"sub_agent": "intelligence", "action": "analyze_patterns", "params": {"mission": intent, "context": ctx}})
        elif agent == "director":
            tasks.append({"sub_agent": "intelligence", "action": "gather_intelligence", "params": {"mission": intent, "context": ctx}})
            tasks.append({"sub_agent": "director", "action": "analyze_situation", "params": {"context": ctx}})
            tasks.append({"sub_agent": "director", "action": "make_decision", "params": {"context": ctx}})
        elif agent == "operations":
            tasks.append({"sub_agent": "intelligence", "action": "gather_intelligence", "params": {"mission": intent, "context": ctx}})
            tasks.append({"sub_agent": "director", "action": "analyze_situation", "params": {"context": ctx}})
            tasks.append({"sub_agent": "operations", "action": "execute_order", "params": {"context": ctx}})

        return tasks


class DomainSwarm(OODAInterface):
    """领域多 Agent Swarm 编排器"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        opa_manager=None,
        query_service=None,
        write_proxy=None,
        fault_manager=None,
        state_manager=None,
        health_monitor=None,
    ):
        self.config = config or self._default_config()

        # 注入依赖（懒加载默认值：仅在实际需要时才导入 infra 实现）
        self.opa_manager = opa_manager if opa_manager is not None else self._default_opa_manager()
        self._query_service = query_service if query_service is not None else self._default_query_service()
        self._write_proxy = write_proxy if write_proxy is not None else self._default_write_proxy()
        self.fault_manager = fault_manager if fault_manager is not None else self._default_fault_manager()
        self.state_manager = state_manager if state_manager is not None else self._default_state_manager()
        self.health_monitor = health_monitor if health_monitor is not None else self._default_health_monitor()

        self.agents = self._initialize_agents()
        self.active_missions: Dict[str, Dict[str, Any]] = {}
        self.mission_history: List[MissionResult] = []

        self.intent_router = IntentRouter()
        self.sub_agent_planner = SubAgentPlanner()
        self._swarm_adapter = None

        # OODA 生命周期钩子
        self._lifecycle_hooks: List[OODALifecycleHook] = []

        # 注册内置审计钩子（遵循 AGENTS.md 规则 10：所有变更通过 unified_audit.py 统一写入）
        try:
            from odap.biz.core.agent.impl.audit_ooda_hook import AuditOODAHook
            self.add_lifecycle_hook(AuditOODAHook())
        except Exception as e:
            logger.warning("Failed to register AuditOODAHook: %s", e)

    def _default_config(self) -> Dict[str, Any]:
        return {
            "coordinator": {
                "max_parallel_agents": 3,
                "task_timeout_seconds": 300,
                "retry_attempts": 2,
            },
            "ooda": {
                "confirm_before_act": True,
                "write_to_graphiti": True,
                "max_ooda_loops": 3,
            },
        }

    # ── 懒加载默认工厂方法（延迟导入 infra 实现，避免 biz→infra 直接耦合）──

    @staticmethod
    def _default_opa_manager():
        from odap.infra.opa import OPAManager
        return OPAManager()

    @staticmethod
    def _default_query_service():
        from odap.infra.query import QueryService
        return QueryService()

    @staticmethod
    def _default_write_proxy():
        from odap.infra.query import get_graph_write_proxy
        return get_graph_write_proxy()

    @staticmethod
    def _default_fault_manager():
        from odap.infra.resilience.fault_tolerance import FaultRecoveryManager
        return FaultRecoveryManager.get_instance()

    @staticmethod
    def _default_state_manager():
        from odap.infra.resilience.state_persistence import StatePersistenceManager
        return StatePersistenceManager.get_instance()

    @staticmethod
    def _default_health_monitor():
        from odap.infra.resilience.health_monitor import HealthMonitor
        return HealthMonitor.get_instance()

    def _subscribe_agent_events(self):
        """订阅 agent:task_completed 事件，将 Intelligence Agent 结果自动路由到 Director Agent"""
        try:
            from odap.web.ws.event_bus import get_event_bus
            bus = get_event_bus()
            bus.subscribe("agent:task_completed", self._on_agent_task_completed)
            logger.info("已订阅 agent:task_completed 事件")
        except Exception as e:
            logger.warning(f"订阅 agent:task_completed 事件失败: {e}")

    def _on_agent_task_completed(self, event_type: str, data: dict, workspace_id: str = None):
        """处理 agent:task_completed 事件，将结果路由到目标 Agent"""
        try:
            target_agents = data.get("target_agents", [])
            agent_type = data.get("agent_type", "")
            result = data.get("result", {})

            if "director" in target_agents and agent_type == "intelligence":
                director = self.agents.get(AgentType.DIRECTOR)
                if director:
                    director._pending_intel_data = result
                logger.info(f"Intelligence Agent result routed to Director Agent, threat_level={result.get('threat_level', 'unknown')}")
        except Exception as e:
            logger.warning(f"处理 agent:task_completed 事件失败: {e}")

    def _initialize_agents(self) -> Dict[AgentType, OHSwarmAgent]:
        """初始化三个 OHSwarmAgent（基于 OH QueryEngine 的不同配置实例）"""
        return {
            AgentType.INTELLIGENCE: OHSwarmAgent(
                role="intelligence",
                agent_type=AgentType.INTELLIGENCE,
                opa_manager=self.opa_manager,
                write_proxy=self._write_proxy,
            ),
            AgentType.DIRECTOR: OHSwarmAgent(
                role="director",
                agent_type=AgentType.DIRECTOR,
                opa_manager=self.opa_manager,
                write_proxy=self._write_proxy,
            ),
            AgentType.OPERATIONS: OHSwarmAgent(
                role="operations",
                agent_type=AgentType.OPERATIONS,
                opa_manager=self.opa_manager,
                write_proxy=self._write_proxy,
            ),
        }

    async def initialize(self) -> None:
        """初始化 Swarm"""
        logger.info("DomainSwarm 初始化中...")

        try:
            self._write_proxy.initialize_graph()
            logger.info("Graphiti 连接正常")
        except Exception as e:
            logger.warning(f"Graphiti 初始化失败: {e}")
            logger.warning("将使用 fallback 模式")

        await self.health_monitor.start_monitoring()
        logger.info("健康监控已启动")

        # 订阅 agent:task_completed 事件，将 Intelligence Agent 结果路由到 Director
        self._subscribe_agent_events()

        logger.info(f"已初始化 {len(self.agents)} 个 Agent")
        for agent_type, agent in self.agents.items():
            logger.info(f"  - {agent_type.value}: {type(agent).__name__}")

    async def execute_mission(self, mission: str, context: Optional[Dict[str, Any]] = None) -> MissionResult:
        """执行完整 OODA 循环（含 EVALUATE + 条件性 Re-loop + 韧性接线）"""
        mission_id = str(uuid.uuid4())[:16]
        start_time = time.perf_counter()

        # ── 检查点恢复：如有未完成的 mission，从断点继续 ──
        recovered = await self._try_recover_mission(mission_id)
        if recovered:
            mission_id = recovered["mission_id"]
            mission_ctx = recovered
            logger.info(f"[{mission_id}] 从检查点恢复，已完成阶段: {[p.value for p in mission_ctx.get('phases_completed', [])]}")
        else:
            logger.info(f"[{mission_id}] 开始执行任务: {mission}")
            await self._emit_ooda_event("ooda:mission_started", mission_id, {"mission": mission})
            mission_ctx = {
                "mission": mission,
                "mission_id": mission_id,
                "context": context or {},
                "phases_completed": [],
                "phase_data": {},
                "graphiti_episodes": [],
                "ooda_loop_count": 0,
                "error": None,
                "agent_ids": [agent_type.value for agent_type in self.agents.keys()],
            }

        self.active_missions[mission_id] = mission_ctx
        await self.state_manager.save_checkpoint(mission_id, mission_ctx)

        max_ooda_loops = self.config.get("ooda", {}).get("max_ooda_loops", 3)

        with agent_span("execute_mission", mission_type="ooda",
                        attributes={"agent.mission_id": mission_id}) as span:
            try:
                while mission_ctx["ooda_loop_count"] < max_ooda_loops:
                    mission_ctx["ooda_loop_count"] += 1
                    loop_num = mission_ctx["ooda_loop_count"]
                    logger.info(f"[{mission_id}] OODA 循环 #{loop_num}/{max_ooda_loops}")
    
                    # --- OBSERVE ---
                    observe_result = await self._execute_phase_with_tolerance(
                        OODAPhase.OBSERVE, mission_ctx, "intelligence",
                        lambda: self._observe(mission_ctx["mission"], mission_ctx.get("context")),
                    )
                    mission_ctx["phase_data"]["observe"] = observe_result
    
                    # --- ORIENT ---
                    orient_result = await self._execute_phase_with_tolerance(
                        OODAPhase.ORIENT, mission_ctx, "intelligence",
                        lambda: self._orient(observe_result, mission_ctx.get("context")),
                    )
                    mission_ctx["phase_data"]["orient"] = orient_result
    
                    # --- DECIDE ---
                    decide_result = await self._execute_phase_with_tolerance(
                        OODAPhase.DECIDE, mission_ctx, "director",
                        lambda: self._decide(orient_result, mission_ctx.get("context")),
                    )
                    mission_ctx["phase_data"]["decide"] = decide_result
    
                    # --- ACT ---
                    act_result = await self._execute_phase_with_tolerance(
                        OODAPhase.ACT, mission_ctx, "operations",
                        lambda: self._act(decide_result, mission_ctx.get("context")),
                    )
                    mission_ctx["phase_data"]["act"] = act_result
    
                    # --- EVALUATE ---
                    evaluate_result = await self._execute_phase_with_tolerance(
                        OODAPhase.EVALUATE, mission_ctx, "intelligence",
                        lambda: self._evaluate(act_result, decide_result, mission_ctx),
                    )
                    mission_ctx["phase_data"]["evaluate"] = evaluate_result
    
                    if self.config.get("ooda", {}).get("write_to_graphiti", True):
                        await self._write_episodes(mission_ctx)
    
                    # 条件性 Re-loop：评估结果要求持续监控时触发新一轮 OODA
                    requires_monitoring = evaluate_result.get("requires_monitoring", False)
                    if not requires_monitoring:
                        logger.info(f"[{mission_id}] 评估完成，无需持续监控，OODA 闭环结束")
                        break
                    else:
                        logger.info(f"[{mission_id}] 评估结果要求持续监控，启动 OODA 循环 #{loop_num + 1}")
                        # 将评估结果注入下一轮的上下文
                        mission_ctx["context"] = mission_ctx.get("context") or {}
                        mission_ctx["context"]["previous_evaluation"] = evaluate_result
                        mission_ctx["context"]["previous_act_result"] = act_result

                execution_time_ms = (time.perf_counter() - start_time) * 1000

                result = MissionResult(
                    mission_id=mission_id,
                    success=True,
                    phases_completed=mission_ctx["phases_completed"],
                    final_decision=mission_ctx["phase_data"].get("decide"),
                    execution_time_ms=round(execution_time_ms, 2),
                    graphiti_episodes=mission_ctx["graphiti_episodes"],
                )
                await self._emit_ooda_event("ooda:mission_completed", mission_id, {"success": True, "execution_time_ms": round(execution_time_ms, 2)})

                logger.info(f"[{mission_id}] 任务完成，耗时: {execution_time_ms:.2f}ms, OODA 循环: {mission_ctx['ooda_loop_count']} 次")

            except Exception as e:
                import traceback
                logger.error(f"[{mission_id}] 任务执行失败: {e}")
                logger.error(f"[{mission_id}] 详细错误: {traceback.format_exc()}")
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))

                # 通过 FaultRecoveryManager 处理故障
                recovery = await self.fault_manager.handle_failure(
                    agent_id="domain_swarm",
                    error=e,
                )
                logger.info(f"[{mission_id}] 故障恢复策略: {recovery.get('action', 'none')}")

                execution_time_ms = (time.perf_counter() - start_time) * 1000
                result = MissionResult(
                    mission_id=mission_id,
                    success=False,
                    phases_completed=mission_ctx["phases_completed"],
                    execution_time_ms=round(execution_time_ms, 2),
                    error_message=str(e),
                )
                await self._emit_ooda_event("ooda:mission_failed", mission_id, {"success": False, "error": str(e)[:200]})

        self.mission_history.append(result)
        if mission_id in self.active_missions:
            del self.active_missions[mission_id]

        return result

    async def _execute_phase_with_tolerance(
        self,
        phase: OODAPhase,
        mission_ctx: Dict[str, Any],
        agent_id: str,
        phase_fn: Callable,
    ) -> Dict[str, Any]:
        """执行单个 OODA 阶段，含生命周期钩子 + 检查点 + 容错"""
        await self._fire_phase_start(phase.value, mission_ctx)
        await self._emit_ooda_event(f"ooda:{phase.value}_started", mission_ctx["mission_id"], None)

        # 通过 FaultRecoveryManager 的 execute_with_tolerance 包装执行
        tolerance_result = await self.fault_manager.execute_with_tolerance(
            agent_id=agent_id,
            func=phase_fn,
        )

        if tolerance_result.get("status") == "success":
            phase_result = tolerance_result["result"]
        else:
            # 容错降级：使用故障恢复结果
            phase_result = tolerance_result
            logger.warning(f"[{mission_ctx['mission_id']}] {phase.value} 阶段降级: {tolerance_result.get('action', 'unknown')}")

        mission_ctx["phases_completed"].append(phase)
        await self.state_manager.save_checkpoint(mission_ctx["mission_id"], mission_ctx)
        await self._fire_phase_end(phase.value, phase_result, mission_ctx)
        await self._emit_ooda_event(f"ooda:{phase.value}_completed", mission_ctx["mission_id"], phase_result)
        logger.info(f"[{mission_ctx['mission_id']}] {phase.value.capitalize()} 阶段完成")

        return phase_result

    async def _evaluate(
        self,
        act_result: Dict[str, Any],
        decide_result: Dict[str, Any],
        mission_ctx: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluate 阶段 — 评估行动效果，决定是否需要持续监控

        设计规格（swarm_orchestrator/DESIGN.md 3.1 节）:
        - 比较预期效果与实际结果，计算偏差
        - 识别根本原因（如有偏差）
        - 判断是否需要持续监控（requires_monitoring）
        """
        logger.info("[Evaluate] 评估行动效果")

        recommended_action = decide_result.get("recommended_action", {})
        expected_outcome = recommended_action.get("description", "")
        actual_outcome = act_result.get("status", "unknown")

        # 计算偏差
        deviation_detected = False
        deviation_reason = ""

        if actual_outcome in ("failed", "cancelled"):
            deviation_detected = True
            deviation_reason = f"行动状态异常: {actual_outcome}"
        elif actual_outcome == "pending_data":
            deviation_detected = True
            deviation_reason = "数据不足，需要更多情报"

        # 判断是否需要持续监控
        requires_monitoring = False
        threat_level = decide_result.get("threat_level", "unknown")

        if deviation_detected:
            requires_monitoring = True
        elif threat_level in ("high", "critical"):
            requires_monitoring = True
        elif decide_result.get("requires_confirmation") and actual_outcome != "completed":
            requires_monitoring = True

        evaluate_result = {
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
            "deviation_detected": deviation_detected,
            "deviation_reason": deviation_reason,
            "requires_monitoring": requires_monitoring,
            "threat_level": threat_level,
            "recommendation": "continue_monitoring" if requires_monitoring else "mission_complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 缓存评估结果，供 FaultRecoveryManager 回退使用
        self.fault_manager.cache_result("evaluate", evaluate_result)

        return evaluate_result

    async def _try_recover_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """尝试从检查点恢复未完成的 mission"""
        checkpoints = self.state_manager.list_checkpoints()
        for cp in checkpoints:
            # 找到未完成的 mission（有检查点但不在 active_missions 中）
            existing_mission_id = cp.get("mission_id", "")
            if existing_mission_id and existing_mission_id not in self.active_missions:
                checkpoint_data = await self.state_manager.load_checkpoint(existing_mission_id)
                if checkpoint_data and checkpoint_data.get("phases_completed"):
                    # 检查是否所有阶段都已完成（包括 evaluate）
                    completed_phases = checkpoint_data.get("phases_completed", [])
                    all_phases_done = all(
                        p in completed_phases
                        for p in [OODAPhase.OBSERVE, OODAPhase.ORIENT, OODAPhase.DECIDE, OODAPhase.ACT]
                    )
                    if not all_phases_done:
                        logger.info(f"发现未完成任务 {existing_mission_id}，准备恢复")
                        return checkpoint_data
        return None

    async def resume_from_confirmation(
        self,
        mission_id: str,
        confirmed: bool,
        context: Optional[Dict[str, Any]] = None,
    ) -> MissionResult:
        """从人工确认断点恢复执行

        当 execute_streaming 返回 WAITING_CONFIRMATION 后，
        调用此方法传入人工决策继续执行。
        """
        mission_ctx = self.active_missions.get(mission_id)
        if not mission_ctx:
            return MissionResult(
                mission_id=mission_id,
                success=False,
                phases_completed=[],
                error_message=f"Mission {mission_id} not found or already completed",
            )

        decide_result = mission_ctx.get("phase_data", {}).get("decide", {})

        if not confirmed:
            logger.info(f"[{mission_id}] 人工拒绝确认，任务取消")
            return MissionResult(
                mission_id=mission_id,
                success=False,
                phases_completed=mission_ctx.get("phases_completed", []),
                error_message="Human confirmation denied",
            )

        # 人工确认通过，继续执行 ACT 阶段
        logger.info(f"[{mission_id}] 人工确认通过，继续执行")
        start_time = time.perf_counter()

        try:
            act_result = await self._execute_phase_with_tolerance(
                OODAPhase.ACT, mission_ctx, "operations",
                lambda: self._act(decide_result, context),
            )
            mission_ctx["phase_data"]["act"] = act_result

            evaluate_result = await self._execute_phase_with_tolerance(
                OODAPhase.EVALUATE, mission_ctx, "intelligence",
                lambda: self._evaluate(act_result, decide_result, mission_ctx),
            )
            mission_ctx["phase_data"]["evaluate"] = evaluate_result

            if self.config.get("ooda", {}).get("write_to_graphiti", True):
                await self._write_episodes(mission_ctx)

            execution_time_ms = (time.perf_counter() - start_time) * 1000
            result = MissionResult(
                mission_id=mission_id,
                success=True,
                phases_completed=mission_ctx["phases_completed"],
                final_decision=decide_result,
                execution_time_ms=round(execution_time_ms, 2),
                graphiti_episodes=mission_ctx["graphiti_episodes"],
            )
        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            result = MissionResult(
                mission_id=mission_id,
                success=False,
                phases_completed=mission_ctx.get("phases_completed", []),
                execution_time_ms=round(execution_time_ms, 2),
                error_message=str(e),
            )

        self.mission_history.append(result)
        if mission_id in self.active_missions:
            del self.active_missions[mission_id]

        return result

    async def execute_streaming(self, mission: str, context: Optional[Dict[str, Any]] = None) -> AsyncGenerator[OODAProgress, None]:
        """流式执行 OODA 循环，逐步返回进度（含 EVALUATE 阶段 + HITL 恢复支持）"""
        mission_id = str(uuid.uuid4())[:16]

        # 保存 mission 上下文以便 HITL 恢复
        mission_ctx = {
            "mission": mission,
            "mission_id": mission_id,
            "context": context or {},
            "phases_completed": [],
            "phase_data": {},
            "graphiti_episodes": [],
            "ooda_loop_count": 0,
            "error": None,
            "agent_ids": [agent_type.value for agent_type in self.agents.keys()],
        }
        self.active_missions[mission_id] = mission_ctx
        await self.state_manager.save_checkpoint(mission_id, mission_ctx)

        yield OODAProgress(
            phase=OODAPhase.OBSERVE,
            status=OODAStatus.STARTED,
            agent=AgentType.INTELLIGENCE,
            message="开始感知阶段",
        )

        try:
            observe_result = await self._observe(mission, context)
            mission_ctx["phase_data"]["observe"] = observe_result
            mission_ctx["phases_completed"].append(OODAPhase.OBSERVE)
            await self.state_manager.save_checkpoint(mission_id, mission_ctx)
            yield OODAProgress(
                phase=OODAPhase.OBSERVE,
                status=OODAStatus.COMPLETED,
                agent=AgentType.INTELLIGENCE,
                data=observe_result,
            )
        except Exception as e:
            yield OODAProgress(
                phase=OODAPhase.OBSERVE,
                status=OODAStatus.ERROR,
                agent=AgentType.INTELLIGENCE,
                message=str(e),
            )
            return

        yield OODAProgress(
            phase=OODAPhase.ORIENT,
            status=OODAStatus.STARTED,
            agent=AgentType.INTELLIGENCE,
            message="开始理解阶段",
        )

        try:
            orient_result = await self._orient(observe_result, context)
            mission_ctx["phase_data"]["orient"] = orient_result
            mission_ctx["phases_completed"].append(OODAPhase.ORIENT)
            await self.state_manager.save_checkpoint(mission_id, mission_ctx)
            yield OODAProgress(
                phase=OODAPhase.ORIENT,
                status=OODAStatus.COMPLETED,
                agent=AgentType.INTELLIGENCE,
                data=orient_result,
            )
        except Exception as e:
            yield OODAProgress(
                phase=OODAPhase.ORIENT,
                status=OODAStatus.ERROR,
                agent=AgentType.INTELLIGENCE,
                message=str(e),
            )
            return

        yield OODAProgress(
            phase=OODAPhase.DECIDE,
            status=OODAStatus.STARTED,
            agent=AgentType.DIRECTOR,
            message="开始决策阶段",
        )

        try:
            decide_result = await self._decide(orient_result, context)
            mission_ctx["phase_data"]["decide"] = decide_result

            if decide_result.get("requires_confirmation"):
                # 保存检查点以便恢复，不删除 active_mission
                await self.state_manager.save_checkpoint(mission_id, mission_ctx)
                yield OODAProgress(
                    phase=OODAPhase.DECIDE,
                    status=OODAStatus.WAITING_CONFIRMATION,
                    agent=AgentType.DIRECTOR,
                    message="等待人工确认",
                    data={"mission_id": mission_id, **decide_result},
                )
                return  # 后续通过 resume_from_confirmation() 恢复

            mission_ctx["phases_completed"].append(OODAPhase.DECIDE)
            await self.state_manager.save_checkpoint(mission_id, mission_ctx)
            yield OODAProgress(
                phase=OODAPhase.DECIDE,
                status=OODAStatus.COMPLETED,
                agent=AgentType.DIRECTOR,
                data=decide_result,
            )
        except Exception as e:
            yield OODAProgress(
                phase=OODAPhase.DECIDE,
                status=OODAStatus.ERROR,
                agent=AgentType.DIRECTOR,
                message=str(e),
            )
            return

        yield OODAProgress(
            phase=OODAPhase.ACT,
            status=OODAStatus.STARTED,
            agent=AgentType.OPERATIONS,
            message="开始行动阶段",
        )

        try:
            act_result = await self._act(decide_result, context)
            mission_ctx["phase_data"]["act"] = act_result
            mission_ctx["phases_completed"].append(OODAPhase.ACT)
            await self.state_manager.save_checkpoint(mission_id, mission_ctx)
            yield OODAProgress(
                phase=OODAPhase.ACT,
                status=OODAStatus.COMPLETED,
                agent=AgentType.OPERATIONS,
                data=act_result,
            )
        except Exception as e:
            yield OODAProgress(
                phase=OODAPhase.ACT,
                status=OODAStatus.ERROR,
                agent=AgentType.OPERATIONS,
                message=str(e),
            )
            return

        # --- EVALUATE ---
        yield OODAProgress(
            phase=OODAPhase.EVALUATE,
            status=OODAStatus.STARTED,
            agent=AgentType.INTELLIGENCE,
            message="开始评估阶段",
        )

        try:
            evaluate_result = await self._evaluate(act_result, decide_result, mission_ctx)
            mission_ctx["phase_data"]["evaluate"] = evaluate_result
            mission_ctx["phases_completed"].append(OODAPhase.EVALUATE)
            await self.state_manager.save_checkpoint(mission_id, mission_ctx)
            yield OODAProgress(
                phase=OODAPhase.EVALUATE,
                status=OODAStatus.COMPLETED,
                agent=AgentType.INTELLIGENCE,
                data=evaluate_result,
            )
        except Exception as e:
            yield OODAProgress(
                phase=OODAPhase.EVALUATE,
                status=OODAStatus.ERROR,
                agent=AgentType.INTELLIGENCE,
                message=str(e),
            )

        # 清理 active_missions
        if mission_id in self.active_missions:
            del self.active_missions[mission_id]

    async def _observe(self, mission: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Observe 阶段 - Intelligence 感知（委托给 OHSwarmAgent）"""
        logger.info(f"[Observe] 收集情报: {mission}")
        agent = self.agents[AgentType.INTELLIGENCE]
        return await agent.run(
            f"收集情报：{mission}",
            context=context,
        )

    # ------------------------------------------------------------------
    # OODAInterface 实现
    # ------------------------------------------------------------------

    def add_lifecycle_hook(self, hook: OODALifecycleHook) -> None:
        """添加 OODA 生命周期钩子"""
        self._lifecycle_hooks.append(hook)
        logger.info("OODA lifecycle hook added: %s", type(hook).__name__)

    # ------------------------------------------------------------------
    # 生命周期钩子与事件发射辅助方法
    # ------------------------------------------------------------------

    async def _fire_phase_start(self, phase: str, context: Dict[str, Any]) -> None:
        """触发所有钩子的 on_phase_start 回调（优雅降级：异常仅记录日志）"""
        for hook in self._lifecycle_hooks:
            try:
                await hook.on_phase_start(phase, context)
            except Exception as e:
                logger.warning("Lifecycle hook on_phase_start error (phase=%s): %s", phase, e)

    async def _fire_phase_end(self, phase: str, result: Any, context: Dict[str, Any]) -> None:
        """触发所有钩子的 on_phase_end 回调（优雅降级：异常仅记录日志）"""
        for hook in self._lifecycle_hooks:
            try:
                await hook.on_phase_end(phase, result, context)
            except Exception as e:
                logger.warning("Lifecycle hook on_phase_end error (phase=%s): %s", phase, e)

    async def _emit_ooda_event(self, event_type: str, mission_id: str, result: Any) -> None:
        """向 DomainEventBus 发布 OODA 阶段完成事件（优雅降级）"""
        try:
            from odap.infra.events import get_event_bus
            event_bus = get_event_bus()
            result_summary = str(result)[:200] if result else ""
            await event_bus.emit(event_type, {
                "mission_id": mission_id,
                "result_summary": result_summary,
            })
        except Exception as e:
            logger.debug("OODA event emit failed (%s): %s", event_type, e)

    async def _orient(self, observe_result: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Orient 阶段 - Intelligence 理解分析"""
        logger.info("[Orient] 分析威胁模式")

        rag_result = await self._query_service.execute_async(
            workspace_id="default",
            query=f".entity with(search='{observe_result.get('summary', '')}')",
            limit=3,
        )
        rag_context = json.dumps(rag_result.rows, ensure_ascii=False, default=str) if rag_result.rows else ""

        oriented = {
            **observe_result,
            "historical_context": rag_context,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return oriented

    async def _decide(self, orient_result: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Decide 阶段 - Director 决策（委托给 OHSwarmAgent）"""
        logger.info("[Decide] 制定行动方案")
        agent = self.agents[AgentType.DIRECTOR]
        # 将情报数据注入 Director 的上下文
        agent._pending_intel_data = orient_result
        return await agent.run(
            f"基于以下情报制定决策方案：{json.dumps(orient_result, ensure_ascii=False, default=str)[:2000]}",
            context=context,
        )

    async def _act(self, decide_result: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Act 阶段 - Operations 执行（委托给 OHSwarmAgent）"""
        logger.info(f"[Act] 执行命令: {decide_result.get('recommended_action')}")

        recommended = decide_result.get("recommended_action", {})
        order = {
            "type": recommended.get("type", "observe"),
            "targets": recommended.get("targets", []),
            "requires_confirmation": decide_result.get("requires_confirmation", False),
            "description": recommended.get("description", ""),
        }

        agent = self.agents[AgentType.OPERATIONS]
        return await agent.run(
            f"执行以下命令：{json.dumps(order, ensure_ascii=False, default=str)[:2000]}",
            context={"order": order, **(context or {})},
        )

    async def _write_episodes(self, mission_ctx: Dict[str, Any]) -> None:
        """写 Graphiti Episode"""
        try:
            episode_text = f"任务: {mission_ctx['mission']}\n"
            episode_text += f"完成阶段: {[p.value for p in mission_ctx['phases_completed']]}\n"
            episode_text += f"最终决策: {json.dumps(mission_ctx.get('final_decision', {}), ensure_ascii=False, default=str)}"

            result = await self._write_proxy.add_episode(
                name=f"mission_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                content=episode_text,
                source_description="DomainSwarm/OODA",
            )

            if result.get("status") == "success":
                mission_ctx["graphiti_episodes"].append("ooda_mission_episode")
        except Exception as e:
            logger.warning(f"Graphiti 写入失败: {e}")

    def _get_swarm_adapter(self) -> Optional[ISwarmAdapter]:
        if self._swarm_adapter is not None:
            return self._swarm_adapter
        try:
            from odap.biz.integration.openharness_agent.adapter.swarm_adapter import SwarmAdapter
            self._swarm_adapter = SwarmAdapter()
        except Exception as e:
            logger.warning(f"SwarmAdapter not available: {e}")
            self._swarm_adapter = None
        return self._swarm_adapter

    async def dispatch_intent(self, intent: str, context: Optional[Dict[str, Any]] = None, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        task_id = str(uuid.uuid4())[:16]
        routing = self.intent_router.route(intent, context)
        assigned_agent = routing["agent"]
        confidence = routing["confidence"]

        plan = self.sub_agent_planner.plan(intent, assigned_agent, context)

        adapter = self._get_swarm_adapter()
        if adapter:
            try:
                swarm_result = adapter.dispatch_intent("default", intent, context)
                if swarm_result.get("status") == "success":
                    return {
                        "task_id": task_id,
                        "assigned_agent": assigned_agent,
                        "confidence": confidence,
                        "routing_source": routing.get("source", "unknown"),
                        "plan": plan,
                        "swarm_observation": swarm_result.get("observation"),
                        "status": "dispatched",
                    }
            except Exception as e:
                logger.warning(f"SwarmAdapter dispatch failed, using fallback: {e}")

        return {
            "task_id": task_id,
            "assigned_agent": assigned_agent,
            "confidence": confidence,
            "routing_source": routing.get("source", "unknown"),
            "plan": plan,
            "status": "dispatched",
        }

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        mission = self.active_missions.get(task_id)
        if mission:
            return {
                "task_id": task_id,
                "status": "running",
                "phases_completed": [p.value if hasattr(p, 'value') else p for p in mission.get("phases_completed", [])],
                "mission": mission.get("mission", ""),
            }
        for result in self.mission_history:
            if result.mission_id == task_id:
                return {
                    "task_id": task_id,
                    "status": "completed" if result.success else "failed",
                    "phases_completed": [p.value for p in result.phases_completed],
                    "final_decision": result.final_decision,
                    "execution_time_ms": result.execution_time_ms,
                    "error_message": result.error_message,
                }
        return {"status": "error", "message": f"Task {task_id} not found"}

    async def get_decision_chain(self, task_id: str) -> Dict[str, Any]:
        for result in self.mission_history:
            if result.mission_id == task_id:
                chain = []
                for phase in result.phases_completed:
                    chain.append({
                        "phase": phase.value,
                        "description": f"OODA {phase.value} phase completed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                return {
                    "task_id": task_id,
                    "chain": chain,
                    "final_decision": result.final_decision,
                }
        return {"status": "error", "message": f"Task {task_id} not found"}

    async def configure_swarm(self, agent_roles: Optional[Dict[str, Any]] = None, routing_rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if agent_roles:
            for role_name, role_config in agent_roles.items():
                agent_type = AgentType(role_name) if role_name in [t.value for t in AgentType] else None
                if agent_type and agent_type in self.agents:
                    agent = self.agents[agent_type]
                    if hasattr(agent, 'config'):
                        for key, value in role_config.items():
                            if hasattr(agent.config, key):
                                setattr(agent.config, key, value)

        if routing_rules:
            for rule in routing_rules:
                self.intent_router._RULES.append(rule)

        return {
            "status": "success",
            "agent_roles": list(self.agents.keys()),
            "routing_rules_count": len(self.intent_router._RULES),
        }

    async def shutdown(self) -> None:
        """关闭 Swarm"""
        logger.info("DomainSwarm 关闭中...")
        await self.health_monitor.stop_monitoring()
        self.active_missions.clear()
        logger.info("DomainSwarm 已关闭")

    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        return asyncio.run(self.health_monitor.get_health_report())

    def get_persistence_stats(self) -> Dict[str, Any]:
        """获取持久化统计"""
        return self.state_manager.get_persistence_stats()

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """列出所有检查点"""
        return self.state_manager.list_checkpoints()

    def get_fault_summary(self) -> Dict[str, Any]:
        """获取故障汇总"""
        return self.fault_manager.get_failure_summary()

    def get_mission_history(self) -> List[Dict[str, Any]]:
        """获取任务历史"""
        return [r.to_dict() for r in self.mission_history]


if __name__ == "__main__":
    import asyncio

    async def main():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(message)s",
        )

        swarm = DomainSwarm()
        await swarm.initialize()

        logger.info('\n' + '=' * 60)
        logger.info('DomainSwarm OODA 循环测试')
        logger.info('=' * 60)

        result = await swarm.execute_mission("分析B区威胁并采取行动")

        logger.info('\n任务结果:')
        logger.info(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))

        logger.info('\n历史记录:')
        for r in swarm.get_mission_history():
            logger.info(f"  - {r['mission_id']}: {('✅' if r['success'] else '❌')} {r['execution_time_ms']:.2f}ms")

        await swarm.shutdown()

    asyncio.run(main())