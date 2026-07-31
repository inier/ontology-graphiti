"""ChainEngine — 链式推理 + 循环检测层 (spec 008 / FR-004/FR-014 / US3).

设计: Thin Adapter + 可注入 stepper
  · 循环检测层是纯装饰器（stepper 注入），与具体引擎解耦
  · TDD 用 FakeStepper（测试文件中）控制 steps/conflicts
  · Phase 2 (T029): deduction_engine 注入 → DeductionStepper（真实推理）
    不可用或异常 → fallback _DefaultStepper + explain.status=degraded
  · 008 循环检测层保留在 DeductionStepper 之上（DeductionEngine 无此能力）
  · 所有函数体 ≤ 40 行（Constitution I）
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.semantic_retrieval.impl.deduction_adapter import DeductionStepper

logger = logging.getLogger("semantic_retrieval.chain")

MAX_DEPTH_HARD_LIMIT = 10


# ── 默认 stepper：Phase 1 占位（无 DeductionEngine 时使用） ──

class _DefaultStepper:
    """生产默认 stepper：语义不足时仅转发起点，不阻塞 API。

    Phase 2: DeductionEngine 可用时由 DeductionStepper 替换；
    不可用或未注入时 fallback 本实现 + explain.status=degraded。
    """

    def __init__(self):
        self._outputs = []

    def feed(self, outputs: List[str]) -> None:
        """可选：外部预置 outputs（测试/调试用）。"""
        self._outputs = list(outputs)

    async def step(self, rule_id: str, input_val: str, duration_ms: int = 50):
        if not self._outputs:
            return None
        out = self._outputs.pop(0)
        return {
            "step_id": f"s{uuid.uuid4().hex[:4]}",
            "rule_id": rule_id,
            "input": input_val,
            "output": out,
            "duration_ms": duration_ms,
        }

    def conflicts(self) -> List[Dict[str, str]]:
        return []


# ── ChainEngine：循环检测层（核心） ───────────────────────────────────────

class ChainEngine:
    """链式推理：按 rules[] 有序步进，检测循环 + 深度超限 + 规则冲突 (FR-014)。

    Stepper 优先级（T029）：
      1. 显式 stepper（TDD 注入）优先
      2. deduction_engine 可用 → DeductionStepper（真实推理）
      3. 否则 _DefaultStepper（Phase 1 占位）
    """

    def __init__(
        self,
        stepper: Any = None,
        rules: Optional[List[str]] = None,
        *,
        deduction_engine: Any = None,
    ):
        self._explicit_stepper = stepper  # None 表示未显式注入
        self._stepper = stepper or _DefaultStepper()
        self._default_rules = list(rules or [])
        self._deduction = deduction_engine

    # ── 公共 API ─────────────────────────────────────────────────────────

    async def reason(
        self,
        workspace_id: str,
        *,
        query: str,
        rules: Optional[List[str]] = None,
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """执行推理链，返回结构 {mode, reasoning, warnings, total, explain?}。"""
        _ = workspace_id  # 预留（Phase 2 对接 scenario_id）
        if max_depth > MAX_DEPTH_HARD_LIMIT:
            raise ValueError(
                f"max_depth 上限为 {MAX_DEPTH_HARD_LIMIT}，当前 {max_depth}"
            )
        rules_list = list(rules or self._default_rules)
        stepper = self._resolve_stepper(query, rules_list)
        return await self._execute_chain(stepper, query, rules_list, max_depth)

    def _resolve_stepper(
        self, query: str, rules: List[str]
    ) -> Any:
        """T029: 显式 stepper 优先；否则 deduction_engine → DeductionStepper；否则默认。"""
        if self._explicit_stepper is not None:
            return self._stepper
        if self._deduction is not None:
            return DeductionStepper(self._deduction, query, rules)
        return self._stepper

    async def _execute_chain(
        self,
        stepper: Any,
        query: str,
        rules_list: List[str],
        max_depth: int,
    ) -> Dict[str, Any]:
        """执行推理 + 组装结果（含 explain 降级标记）。"""
        start_node = self._extract_start_node(query)
        steps: List[Dict[str, Any]] = []
        self._append_init_step(steps, start_node)

        visited = [start_node]
        cycle_ctx: Dict[str, Any] = {"cycle_detected": False, "cycle_path": None}
        warnings = await self._run_steps(
            stepper, rules_list, steps, visited, cycle_ctx, max_depth
        )

        conflicts = self._safe_conflicts(stepper)
        status = "degraded" if getattr(stepper, "degraded", False) else "ok"
        reasoning = self._build_reasoning(
            steps, cycle_ctx["cycle_detected"], cycle_ctx["cycle_path"],
            conflicts, query, status=status, max_depth=max_depth,
        )
        self._override_from_stepper(stepper, reasoning)
        return self._build_result(reasoning, warnings, steps, stepper)

    @staticmethod
    def _override_from_stepper(stepper: Any, reasoning: Dict[str, Any]) -> None:
        """DeductionStepper 提供 conclusion/confidence/status 时覆盖默认值（真实引擎优先）。"""
        conclusion = getattr(stepper, "conclusion", None)
        if conclusion:
            reasoning["conclusion"] = conclusion
        confidence = getattr(stepper, "confidence", None)
        if confidence is not None:
            reasoning["confidence"] = confidence
        if getattr(stepper, "degraded", False):
            reasoning["status"] = "degraded"

    @staticmethod
    def _build_result(
        reasoning: Dict[str, Any],
        warnings: List[str],
        steps: List[Dict[str, Any]],
        stepper: Any,
    ) -> Dict[str, Any]:
        """组装最终返回；DeductionStepper 降级时附 explain.status=degraded。"""
        result: Dict[str, Any] = {
            "mode": "chain",
            "reasoning": reasoning,
            "warnings": warnings,
            "total": len(steps),
        }
        if getattr(stepper, "degraded", False):
            result["explain"] = {"source": "chain", "status": "degraded"}
        return result

    async def _run_steps(
        self,
        stepper: Any,
        rules_list: List[str],
        steps: List[Dict[str, Any]],
        visited: List[str],
        cycle_ctx: Dict[str, Any],
        max_depth: int,
    ) -> List[str]:
        """按 rules 顺序步进；检测深度超限 / 循环依赖，返回 warnings。"""
        warnings: List[str] = []
        current = visited[0]
        for idx, rule_id in enumerate(rules_list):
            if len(steps) - 1 >= max_depth:
                warnings.append(self._depth_warning(idx, len(rules_list), max_depth))
                break
            next_step = await stepper.step(rule_id, current, duration_ms=50)
            if next_step is None:
                break
            output = str(next_step["output"])
            if output in visited:
                self._mark_cycle(visited, output, cycle_ctx, warnings)
                break
            steps.append(next_step)
            visited.append(output)
            current = output
        return warnings

    @staticmethod
    def _depth_warning(idx: int, total_rules: int, max_depth: int) -> str:
        return f"推理深度达到 max_depth={max_depth}，已截断（剩余 {total_rules - idx} 条规则未执行）"

    @staticmethod
    def _mark_cycle(
        visited: List[str],
        output: str,
        cycle_ctx: Dict[str, Any],
        warnings: List[str],
    ) -> None:
        cycle_ctx["cycle_detected"] = True
        cycle_start = visited.index(output)
        cycle_path = visited[cycle_start:] + [output]
        cycle_ctx["cycle_path"] = cycle_path
        warnings.append("检测到循环依赖 " + "→".join(cycle_path) + "，推理已中止")

    async def search(
        self,
        workspace_id: str,
        query: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """UnifiedRouter 适配器：query → 推理链，行 = steps。"""
        _ = limit
        return await self.reason(workspace_id, query=query)

    # ── 内部辅助（Constitution I：≤ 40 行，拆成小函数） ──────────────────

    @staticmethod
    def _extract_start_node(query: str) -> str:
        """从自然语言 query 提取起始节点，失败则回退 query 本身。"""
        tokens = query.strip().split()
        if not tokens:
            return "START"
        return tokens[0]

    @staticmethod
    def _append_init_step(steps: List[Dict[str, Any]], start_node: str) -> None:
        """在 steps 头部插入起点 s0（满足 T013-4 的 4 步断言：3 条边 + 1 起点）。"""
        steps.append(
            {
                "step_id": "s0",
                "rule_id": "init",
                "input": start_node,
                "output": start_node,
                "duration_ms": 0,
            }
        )

    @staticmethod
    def _safe_conflicts(stepper: Any) -> List[Dict[str, str]]:
        """收集 stepper 冲突，stepper 不支持时返回空列表（不阻断）。"""
        try:
            raw = stepper.conflicts() or []
            result = []
            for c in raw:
                if {"rule_a", "rule_b", "description"}.issubset(c.keys()):
                    result.append(dict(c))
            return result
        except Exception:  # noqa: BLE001 — stepper 无 conflicts() 时兜底
            return []

    @staticmethod
    def _build_reasoning(
        steps: List[Dict[str, Any]],
        cycle_detected: bool,
        cycle_path: Optional[List[str]],
        conflicts: List[Dict[str, str]],
        query: str,
        *,
        status: str = "ok",
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """组装 ReasoningChain 结构（data-model.md §4 + MdlEngine 对齐：status/max_depth）。"""
        last_output = steps[-1]["output"] if steps else query
        step_count = max(len(steps) - 1, 0)  # 不计 s0
        confidence = round(1.0 - (len(conflicts) * 0.15) - (0.1 if cycle_detected else 0.0), 2)
        confidence = max(0.0, min(1.0, confidence))
        conclusion = (
            f"基于 {step_count} 步推理，从 {steps[0]['output']} 推导到 {last_output}"
            if steps
            else "未产生有效推理步骤"
        )
        reasoning: Dict[str, Any] = {
            "chain_id": f"chain-{uuid.uuid4().hex[:8]}",
            "steps": list(steps),
            "status": status,
            "conclusion": conclusion,
            "confidence": confidence,
            "cycle_detected": cycle_detected,
            "conflicts": list(conflicts),
        }
        if max_depth is not None:
            reasoning["max_depth"] = max_depth
        if cycle_detected and cycle_path is not None:
            reasoning["cycle_path"] = list(cycle_path)
        return reasoning
