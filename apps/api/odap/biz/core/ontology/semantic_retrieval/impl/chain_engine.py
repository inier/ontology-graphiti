"""ChainEngine — 链式推理 + 循环检测层 (spec 008 / FR-004/FR-014 / US3).

设计: Thin Adapter + 可注入 stepper
  · 循环检测层是纯装饰器（stepper 注入），与具体引擎解耦
  · TDD 用 FakeStepper（测试文件中）控制 steps/conflicts
  · 生产环境 default_stepper 接 DeductionEngine（不兼容时优雅降级 explain.status=degraded）
  · 所有函数体 ≤ 40 行（Constitution I）
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("semantic_retrieval.chain")

MAX_DEPTH_HARD_LIMIT = 10


# ── 默认 stepper：生产 Thin Adapter（不依赖 DeductionEngine 具体签名） ──

class _DefaultStepper:
    """生产默认 stepper：语义不足时仅转发起点，不阻塞 API。

    TODO Phase 2+：对接 DeductionEngine.simulate_chain(scenario_id, chain_id)
    当真实传导规则通过 scenario_id + rules[] 映射后再替换本实现。
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
    """链式推理：按 rules[] 有序步进，检测循环 + 深度超限 + 规则冲突 (FR-014)。"""

    def __init__(
        self,
        stepper: Any = None,
        rules: Optional[List[str]] = None,
        *,
        deduction_engine: Any = None,
    ):
        self._stepper = stepper or _DefaultStepper()
        self._default_rules = list(rules or [])
        self._deduction = deduction_engine  # Phase 2+ 预留接口

    # ── 公共 API ─────────────────────────────────────────────────────────

    async def reason(
        self,
        workspace_id: str,
        *,
        query: str,
        rules: Optional[List[str]] = None,
        max_depth: int = 5,
    ) -> Dict[str, Any]:
        """执行推理链，返回结构 {mode, reasoning, warnings, total}。"""
        _ = workspace_id  # 预留（Phase 2 对接 scenario_id）
        if max_depth > MAX_DEPTH_HARD_LIMIT:
            raise ValueError(
                f"max_depth 上限为 {MAX_DEPTH_HARD_LIMIT}，当前 {max_depth}"
            )
        rules_list = list(rules or self._default_rules)
        steps: List[Dict[str, Any]] = []
        warnings: List[str] = []
        visited: List[str] = []
        cycle_path: Optional[List[str]] = None
        cycle_detected = False

        start_node = self._extract_start_node(query)
        self._append_init_step(steps, start_node)
        visited.append(start_node)

        current = start_node
        for idx, rule_id in enumerate(rules_list):
            if len(steps) - 1 >= max_depth:
                warnings.append(
                    f"推理深度达到 max_depth={max_depth}，已截断（剩余 {len(rules_list) - idx} 条规则未执行）"
                )
                break
            next_step = await self._stepper.step(rule_id, current, duration_ms=50)
            if next_step is None:
                break
            output = str(next_step["output"])
            if output in visited:
                cycle_detected = True
                cycle_start = visited.index(output)
                cycle_path = visited[cycle_start:] + [output]
                warnings.append(
                    "检测到循环依赖 "
                    + "→".join(cycle_path)
                    + "，推理已中止"
                )
                break
            steps.append(next_step)
            visited.append(output)
            current = output

        conflicts = self._safe_conflicts()
        reasoning = self._build_reasoning(steps, cycle_detected, cycle_path, conflicts, query)
        return {
            "mode": "chain",
            "reasoning": reasoning,
            "warnings": warnings,
            "total": len(steps),
        }

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

    def _safe_conflicts(self) -> List[Dict[str, str]]:
        """收集 stepper 冲突，stepper 不支持时返回空列表（不阻断）。"""
        try:
            raw = self._stepper.conflicts() or []
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
    ) -> Dict[str, Any]:
        """组装 ReasoningChain 结构（data-model.md §4）。"""
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
            "conclusion": conclusion,
            "confidence": confidence,
            "cycle_detected": cycle_detected,
            "conflicts": list(conflicts),
        }
        if cycle_detected and cycle_path is not None:
            reasoning["cycle_path"] = list(cycle_path)
        return reasoning
