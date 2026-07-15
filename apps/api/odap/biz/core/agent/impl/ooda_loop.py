import logging
import asyncio
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone

from odap.biz.core.agent.interfaces.ooda_interface import OODAInterface, OODALifecycleHook

logger = logging.getLogger(__name__)


class OODAPhase(str, Enum):
    """OODA 阶段（5 阶段完整模型：O-O-D-A-E）"""
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"
    EVALUATE = "evaluate"


# 默认最大 OODA 循环次数（条件性 Re-loop 时的上限）
DEFAULT_MAX_OODA_LOOPS = 3


class OODALoop(OODAInterface):
    def __init__(self, agent_id: str = "", role: str = "intelligence", max_ooda_loops: int = DEFAULT_MAX_OODA_LOOPS):
        self.agent_id = agent_id
        self.role = role
        self.max_ooda_loops = max_ooda_loops
        self.current_phase = OODAPhase.OBSERVE
        self.history: List[Dict[str, Any]] = []
        self.observations: List[Dict[str, Any]] = []
        self.analysis: Dict[str, Any] = {}
        self.decision: Dict[str, Any] = {}
        self._lifecycle_hooks: List[OODALifecycleHook] = []

        # 注册内置审计钩子（遵循 AGENTS.md 规则 10：所有变更通过 unified_audit.py 统一写入）
        try:
            from odap.biz.core.agent.impl.audit_ooda_hook import AuditOODAHook
            self.add_lifecycle_hook(AuditOODAHook())
        except Exception as e:
            logger.warning("Failed to register AuditOODAHook: %s", e)

    async def execute_mission(self, mission: Any, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """OODAInterface.execute_mission 实现

        Args:
            mission: 任务描述字符串
            context: 执行上下文（含 observations, query, workspace_id, graph_data 等）
        """
        ctx = context or {}
        return await self.run(ctx)

    def add_lifecycle_hook(self, hook: OODALifecycleHook) -> None:
        """OODAInterface.add_lifecycle_hook 实现"""
        self._lifecycle_hooks.append(hook)
        logger.info("OODALoop lifecycle hook added: %s", type(hook).__name__)

    async def _fire_phase_start(self, phase: str, context: Dict[str, Any]) -> None:
        """触发所有钩子的 on_phase_start 回调（优雅降级）"""
        for hook in self._lifecycle_hooks:
            try:
                await hook.on_phase_start(phase, context)
            except Exception as e:
                logger.warning("OODALoop hook on_phase_start error (phase=%s): %s", phase, e)

    async def _fire_phase_end(self, phase: str, result: Any, context: Dict[str, Any]) -> None:
        """触发所有钩子的 on_phase_end 回调（优雅降级）"""
        for hook in self._lifecycle_hooks:
            try:
                await hook.on_phase_end(phase, result, context)
            except Exception as e:
                logger.warning("OODALoop hook on_phase_end error (phase=%s): %s", phase, e)

    async def _emit_ooda_event(self, event_type: str, result: Any) -> None:
        """向 DomainEventBus 发布 OODA 阶段完成事件（优雅降级）"""
        try:
            from odap.infra.events import get_event_bus
            event_bus = get_event_bus()
            result_summary = str(result)[:200] if result else ""
            await event_bus.emit(event_type, {
                "agent_id": self.agent_id,
                "role": self.role,
                "result_summary": result_summary,
            })
        except Exception as e:
            logger.debug("OODALoop event emit failed (%s): %s", event_type, e)

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行完整 OODA 循环（含 EVALUATE + 条件性 Re-loop）

        当 EVALUATE 阶段判断 requires_monitoring=True 时，
        自动触发新一轮 OBSERVE，实现真正的 OODA 闭环。
        最多循环 max_ooda_loops 次。
        """
        ctx = context or {}
        loop_count = 0
        evaluate_result = None

        while loop_count < self.max_ooda_loops:
            loop_count += 1
            logger.info("OODA 循环 #%d/%d (agent=%s)", loop_count, self.max_ooda_loops, self.agent_id)

            # --- OBSERVE ---
            await self._fire_phase_start(OODAPhase.OBSERVE.value, ctx)
            observe_result = await self._observe(ctx)
            await self._fire_phase_end(OODAPhase.OBSERVE.value, observe_result, ctx)
            await self._emit_ooda_event("ooda:observe_completed", observe_result)

            # --- ORIENT ---
            await self._fire_phase_start(OODAPhase.ORIENT.value, ctx)
            orient_result = await self._orient(observe_result)
            await self._fire_phase_end(OODAPhase.ORIENT.value, orient_result, ctx)
            await self._emit_ooda_event("ooda:orient_completed", orient_result)

            # --- DECIDE ---
            await self._fire_phase_start(OODAPhase.DECIDE.value, ctx)
            decide_result = await self._decide(orient_result)
            await self._fire_phase_end(OODAPhase.DECIDE.value, decide_result, ctx)
            await self._emit_ooda_event("ooda:decide_completed", decide_result)

            # --- ACT ---
            await self._fire_phase_start(OODAPhase.ACT.value, ctx)
            act_result = await self._act(decide_result)
            await self._fire_phase_end(OODAPhase.ACT.value, act_result, ctx)
            await self._emit_ooda_event("ooda:act_completed", act_result)

            # --- EVALUATE ---
            await self._fire_phase_start(OODAPhase.EVALUATE.value, ctx)
            evaluate_result = await self._evaluate(act_result, decide_result)
            await self._fire_phase_end(OODAPhase.EVALUATE.value, evaluate_result, ctx)
            await self._emit_ooda_event("ooda:evaluate_completed", evaluate_result)

            # 条件性 Re-loop：评估结果要求持续监控时触发新一轮
            requires_monitoring = evaluate_result.get("requires_monitoring", False)
            if not requires_monitoring:
                logger.info("OODA 评估完成，无需持续监控，循环结束")
                break
            else:
                logger.info("OODA 评估要求持续监控，启动循环 #%d", loop_count + 1)
                # 将评估结果注入下一轮上下文
                ctx["previous_evaluation"] = evaluate_result

        return {
            "status": "success",
            "agent_id": self.agent_id,
            "role": self.role,
            "observe": observe_result,
            "orient": orient_result,
            "decide": decide_result,
            "act": act_result,
            "evaluate": evaluate_result,
            "ooda_loop_count": loop_count,
            "history": self.history,
        }

    async def _observe(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self.current_phase = OODAPhase.OBSERVE
        raw_observations = context.get("observations", [])
        query = context.get("query", "")
        workspace_id = context.get("workspace_id", "")

        self.observations = []
        for obs in raw_observations:
            if isinstance(obs, dict):
                self.observations.append(obs)
            elif isinstance(obs, str):
                self.observations.append({"content": obs, "source": "input"})

        if query and not any(o.get("content") == query for o in self.observations):
            self.observations.append({"content": query, "source": "query", "workspace_id": workspace_id})

        graph_data = context.get("graph_data", {})
        if graph_data:
            entities = graph_data.get("entities", [])
            relationships = graph_data.get("relationships", [])
            self.observations.append({
                "content": f"Graph data: {len(entities)} entities, {len(relationships)} relationships",
                "source": "knowledge_graph",
                "entity_count": len(entities),
                "relationship_count": len(relationships),
            })

        result = {
            "observations": self.observations,
            "observation_count": len(self.observations),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append({"phase": "observe", "result": result})
        return result

    async def _orient(self, observe_result: Dict[str, Any]) -> Dict[str, Any]:
        self.current_phase = OODAPhase.ORIENT
        observations = observe_result.get("observations", [])

        entity_types = set()
        key_entities = []
        for obs in observations:
            source = obs.get("source", "")
            content = obs.get("content", "")
            if source == "knowledge_graph":
                entity_count = obs.get("entity_count", 0)
                if entity_count > 0:
                    entity_types.add("graph_entities")
            if content and len(content) < 200:
                key_entities.append(content)

        urgency = "normal"
        for obs in observations:
            content = obs.get("content", "").lower()
            if any(kw in content for kw in ["紧急", "urgent", "critical", "立即", "immediately"]):
                urgency = "high"
                break

        completeness = "partial"
        if len(observations) >= 3 and any(o.get("source") == "knowledge_graph" for o in observations):
            completeness = "sufficient"
        elif len(observations) >= 5:
            completeness = "sufficient"
        elif len(observations) == 0:
            completeness = "empty"

        self.analysis = {
            "key_entities": key_entities[:10],
            "entity_types": list(entity_types),
            "urgency": urgency,
            "data_completeness": completeness,
            "observation_count": len(observations),
        }

        result = {
            "analysis": self.analysis,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append({"phase": "orient", "result": result})
        return result

    async def _decide(self, orient_result: Dict[str, Any]) -> Dict[str, Any]:
        self.current_phase = OODAPhase.DECIDE
        analysis = orient_result.get("analysis", {})
        urgency = analysis.get("urgency", "normal")
        completeness = analysis.get("data_completeness", "partial")

        if completeness == "empty":
            decision = "request_more_data"
            reasoning = "No observations available, need more data before proceeding"
            confidence = 0.2
        elif urgency == "high":
            decision = "act_immediately"
            reasoning = "Urgent situation detected, proceeding with available data"
            confidence = 0.7
        elif completeness == "sufficient":
            decision = "proceed"
            reasoning = "Sufficient data available for informed decision"
            confidence = 0.85
        else:
            decision = "proceed_with_caution"
            reasoning = "Partial data available, proceeding with caution"
            confidence = 0.6

        if self.role == "director":
            if decision == "proceed":
                decision = "proceed_with_strategy"
                reasoning += " (director review)"
        elif self.role == "operations":
            if decision in ("proceed", "proceed_with_caution"):
                decision = "execute"
                reasoning += " (operations execution)"

        self.decision = {
            "decision": decision,
            "reasoning": reasoning,
            "confidence": confidence,
            "analysis": analysis,
        }

        result = {
            "decision": decision,
            "reasoning": reasoning,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append({"phase": "decide", "result": result})
        return result

    async def _act(self, decide_result: Dict[str, Any]) -> Dict[str, Any]:
        self.current_phase = OODAPhase.ACT
        decision = decide_result.get("decision", "proceed")
        confidence = decide_result.get("confidence", 0.5)

        if decision == "request_more_data":
            action = "gather_intelligence"
            result_status = "pending_data"
        elif decision in ("act_immediately", "execute"):
            action = "execute_task"
            result_status = "executing"
        elif decision in ("proceed", "proceed_with_strategy", "proceed_with_caution"):
            action = "execute_with_monitoring"
            result_status = "in_progress"
        else:
            action = "wait"
            result_status = "idle"

        result = {
            "action": action,
            "result": result_status,
            "confidence": confidence,
            "decision": decision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append({"phase": "act", "result": result})
        return result

    async def _evaluate(self, act_result: Dict[str, Any], decide_result: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate 阶段 — 评估行动效果，决定是否需要持续监控

        比较预期效果与实际结果，判断是否需要继续观察（条件性 Re-loop）。
        """
        self.current_phase = OODAPhase.EVALUATE

        actual_status = act_result.get("result", "unknown")
        expected_decision = decide_result.get("decision", "proceed")
        confidence = decide_result.get("confidence", 0.5)

        # 偏差检测
        deviation_detected = False
        deviation_reason = ""

        if actual_status in ("failed", "cancelled"):
            deviation_detected = True
            deviation_reason = f"行动状态异常: {actual_status}"
        elif actual_status == "pending_data":
            deviation_detected = True
            deviation_reason = "数据不足，需要更多情报"
        elif confidence < 0.5:
            deviation_detected = True
            deviation_reason = f"决策置信度过低: {confidence}"

        # 判断是否需要持续监控
        requires_monitoring = False
        if deviation_detected:
            requires_monitoring = True
        elif actual_status in ("executing", "in_progress"):
            requires_monitoring = True

        evaluate_result = {
            "actual_status": actual_status,
            "expected_decision": expected_decision,
            "deviation_detected": deviation_detected,
            "deviation_reason": deviation_reason,
            "requires_monitoring": requires_monitoring,
            "confidence": confidence,
            "recommendation": "continue_monitoring" if requires_monitoring else "mission_complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append({"phase": "evaluate", "result": evaluate_result})
        return evaluate_result
