"""DeductionEngine 适配层 — ScenarioMapper + ChainResultAdapter + DeductionStepper.

(Phase 2 / Iter 2 / T027-T029)

将 DeductionEngine 的 simulate_chain 适配为 ChainEngine 的 stepper 接口：
  1. ScenarioMapper: query+rules → 临时 scenario + chain + simulate + 清理
  2. ChainResultAdapter: ChainResult → steps/conflicts/conclusion/confidence
  3. DeductionStepper: 实现 stepper 接口（step/conflicts），懒加载 simulate

设计要点：
  - 008 循环检测层保留（DeductionEngine 无此能力）— DeductionStepper 预计算 steps
    后供 ChainEngine 逐 step 检测循环
  - 临时 scenario 在 finally 中清理（不残留）；清理失败不阻断
  - DeductionEngine 异常 → DeductionStepper 返回空 steps（ChainEngine 降级）
  - 不修改 packages/，仅依赖 IDeductionEngine 接口

Constitution I: 函数体 ≤ 40 行。
Constitution IV: 不新建接口；仅适配器类。
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("semantic_retrieval.deduction_adapter")


# ══════════════════════════════════════════════════════════════════════════
# T027: ScenarioMapper
# ══════════════════════════════════════════════════════════════════════════


class ScenarioMapper:
    """将 query + rules[] 映射为 DeductionEngine 临时 scenario + simulate + 清理。"""

    def __init__(self, deduction_engine: Any) -> None:
        self._engine = deduction_engine

    async def create_and_simulate(
        self,
        query: str,
        rules: List[str],
        target_object_id: str = "",
        target_object_type: str = "",
    ) -> Dict[str, Any]:
        """完整流程：create → add_chain → simulate → cleanup → return ChainResult。"""
        scenario = await self._create_scenario(query, target_object_id, target_object_type)
        scenario_id = scenario.get("scenario_id") or scenario.get("id")
        if not scenario_id:
            return {"status": "error", "message": "create_scenario returned no id"}

        try:
            return await self._add_and_simulate(scenario_id, query, rules)
        finally:
            await self._safe_cleanup(scenario_id)

    async def _create_scenario(
        self, query: str, target_object_id: str, target_object_type: str
    ) -> Dict[str, Any]:
        """创建临时 scenario（名称截断防溢出）。"""
        name = f"sr_chain_{query[:32]}" if query else "sr_chain"
        return await self._engine.create_scenario(
            name=name,
            description=f"semantic_retrieval chain reasoning: {query}",
            target_object_id=target_object_id,
            target_object_type=target_object_type,
        )

    async def _add_and_simulate(
        self, scenario_id: str, query: str, rules: List[str]
    ) -> Dict[str, Any]:
        """add_execution_chain + simulate_chain；失败返回 error dict。"""
        chain = await self._engine.add_execution_chain(
            scenario_id,
            name="retrieval_chain",
            description=f"auto-generated from semantic_retrieval rules: {query}",
            steps=self._rules_to_steps(rules),
        )
        chain_id = chain.get("chain_id")
        if not chain_id:
            return {"status": "error", "message": "add_execution_chain returned no chain_id"}
        return await self._engine.simulate_chain(scenario_id, chain_id)

    @staticmethod
    def _rules_to_steps(rules: List[str]) -> List[Dict[str, Any]]:
        """rules[] → ChainStep[]（每条规则一个 step）。"""
        return [
            {
                "step_order": i,
                "action_type_id": rule_id,
                "description": f"semantic_retrieval rule: {rule_id}",
            }
            for i, rule_id in enumerate(rules)
        ]

    async def _safe_cleanup(self, scenario_id: str) -> None:
        """清理临时 scenario；失败仅 log warning 不阻断。"""
        try:
            await self._engine.delete_scenario(scenario_id)
        except Exception as e:  # noqa: BLE001 — cleanup 不阻断
            logger.warning(f"scenario cleanup failed for {scenario_id}: {e}")


# ══════════════════════════════════════════════════════════════════════════
# T028: ChainResultAdapter
# ══════════════════════════════════════════════════════════════════════════


class ChainResultAdapter:
    """ChainResult → ChainEngine 兼容结构（steps/conflicts/conclusion/confidence）。"""

    @staticmethod
    def to_steps(
        chain_result: Dict[str, Any], rules: List[str]
    ) -> List[Dict[str, Any]]:
        """metric_impacts → steps[{step_id, rule_id, input, output, duration_ms}]。"""
        impacts = chain_result.get("metric_impacts", [])
        steps: List[Dict[str, Any]] = []
        for i, impact in enumerate(impacts):
            rule_id = rules[i] if i < len(rules) else f"impact_{i}"
            steps.append(ChainResultAdapter._impact_to_step(i, impact, rule_id))
        return steps

    @staticmethod
    def _impact_to_step(
        idx: int, impact: Dict[str, Any], rule_id: str
    ) -> Dict[str, Any]:
        """单个 MetricImpact → ChainStep dict。"""
        before = impact.get("before", "")
        after = impact.get("after", impact.get("metric_name", ""))
        return {
            "step_id": f"s{idx + 1}",
            "rule_id": rule_id,
            "input": str(before),
            "output": str(after),
            "duration_ms": 0,
        }

    @staticmethod
    def to_conflicts(chain_result: Dict[str, Any]) -> List[Dict[str, str]]:
        """rule_violations → conflicts[{rule_a, rule_b, description}]。"""
        violations = chain_result.get("rule_violations", [])
        return [
            {
                "rule_a": v.get("rule_id", ""),
                "rule_b": v.get("rule_type", ""),
                "description": v.get("description", ""),
            }
            for v in violations
        ]

    @staticmethod
    def to_conclusion(chain_result: Dict[str, Any]) -> str:
        """projected_state / recommendation → conclusion string。"""
        recommendation = chain_result.get("recommendation", "")
        if recommendation:
            return recommendation
        projected = chain_result.get("projected_state", {})
        if projected:
            return f"投影状态: {projected}"
        return "推理完成，无投影状态"

    @staticmethod
    def to_confidence(chain_result: Dict[str, Any]) -> float:
        """risk_score → confidence = 1 - risk_score/100（clamp 0..1）。"""
        risk_score = float(chain_result.get("risk_score", 0) or 0)
        confidence = 1.0 - risk_score / 100.0
        return max(0.0, min(1.0, confidence))


# ══════════════════════════════════════════════════════════════════════════
# T029: DeductionStepper（实现 ChainEngine stepper 接口）
# ══════════════════════════════════════════════════════════════════════════


class DeductionStepper:
    """DeductionEngine 适配为 stepper：懒加载 simulate，预计算 steps 供循环检测。

    - 首次 step() 触发 ScenarioMapper.create_and_simulate → 缓存 steps
    - 后续 step() 逐个返回缓存 steps
    - conflicts() 返回 ChainResultAdapter.to_conflicts 结果
    - simulate 异常 → 缓存空 steps + 标记 degraded（不抛异常）
    """

    def __init__(
        self,
        deduction_engine: Any,
        query: str,
        rules: List[str],
    ) -> None:
        self._mapper = ScenarioMapper(deduction_engine)
        self._query = query
        self._rules = list(rules)
        self._cached_steps: Optional[List[Dict[str, Any]]] = None
        self._cached_conflicts: List[Dict[str, str]] = []
        self._chain_result: Optional[Dict[str, Any]] = None
        self._step_idx = 0
        self.degraded = False

    async def _ensure_simulated(self) -> None:
        """首次调用时创建 scenario + simulate；异常 → degraded + 空 steps。"""
        if self._cached_steps is not None:
            return
        try:
            result = await self._mapper.create_and_simulate(self._query, self._rules)
            self._cache_result(result)
        except Exception as e:  # noqa: BLE001 — 降级不阻断
            logger.warning(f"DeductionStepper simulate failed, degrading: {e}")
            self._cached_steps = []
            self._cached_conflicts = []
            self.degraded = True

    def _cache_result(self, result: Dict[str, Any]) -> None:
        """将 ChainResult 缓存为 steps + conflicts + 原始 result。"""
        if result.get("status") == "error":
            self._cached_steps = []
            self._cached_conflicts = []
            self.degraded = True
            return
        self._chain_result = result
        self._cached_steps = ChainResultAdapter.to_steps(result, self._rules)
        self._cached_conflicts = ChainResultAdapter.to_conflicts(result)

    @property
    def conclusion(self) -> Optional[str]:
        """ChainResult 的 conclusion（recommendation 或 projected_state）；未模拟返回 None。"""
        if self._chain_result is None or self.degraded:
            return None
        return ChainResultAdapter.to_conclusion(self._chain_result)

    @property
    def confidence(self) -> Optional[float]:
        """ChainResult 的 confidence（1 - risk_score/100）；未模拟返回 None。"""
        if self._chain_result is None or self.degraded:
            return None
        return ChainResultAdapter.to_confidence(self._chain_result)

    async def step(
        self, rule_id: str, input_val: str, duration_ms: int = 50
    ) -> Optional[Dict[str, Any]]:
        """返回下一个预计算 step；无更多 step 返回 None。"""
        await self._ensure_simulated()
        if self._step_idx >= len(self._cached_steps):
            return None
        s = self._cached_steps[self._step_idx]
        self._step_idx += 1
        return s

    def conflicts(self) -> List[Dict[str, str]]:
        """返回缓存的 conflicts（step() 后才可用）。"""
        return list(self._cached_conflicts)


__all__ = ["ScenarioMapper", "ChainResultAdapter", "DeductionStepper"]
