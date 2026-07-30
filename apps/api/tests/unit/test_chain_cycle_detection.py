"""T013 [P] US3: 链式推理循环检测（TDD RED → GREEN）。

测试目标（tasks.md T013 精确要求）:
  T013-1 循环检测：A→B→C→A 中止 + cycle_path 返回
  T013-2 max_depth≤10 防无限递归
  T013-3 规则冲突 conflicts 列表收集
  T013-4 正常链：无循环，steps 完整保留

测试用 FakeStepper 注入 steps 序列（避免真实 DeductionEngine 依赖），
生产 ChainEngine 通过 Thin Adapter 接 DeductionEngine（不兼容时优雅降级）。
"""

from __future__ import annotations

import pytest


# ── FakeStepper: 为 TDD 注入可控 steps / conflicts / 深度超限 ──────────

class FakeStepper:
    """生成可控的 steps 序列，用于循环检测层的纯函数 TDD。"""

    def __init__(self, step_outputs, conflicts=None):
        self._step_outputs = list(step_outputs)
        self._conflicts = conflicts or []
        self._call_count = 0

    async def step(self, rule_id: str, input_val: str, duration_ms: int = 50):
        """每调用一次，吐出下一个 step。"""
        if self._call_count >= len(self._step_outputs):
            return None  # 序列结束
        out = self._step_outputs[self._call_count]
        self._call_count += 1
        return {
            "step_id": f"s{self._call_count}",
            "rule_id": rule_id,
            "input": input_val,
            "output": out,
            "duration_ms": duration_ms,
        }

    def conflicts(self):
        return list(self._conflicts)


# ── T013-1: 循环检测 A → B → C → A，中止 + cycle_path 返回 ──────────────

@pytest.mark.asyncio
async def test_cycle_detection_aborts_and_returns_path():
    """T013-1: A→B→C→A 循环被检测，cycle_detected=true + cycle_path=[A,B,C,A]。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    # Fake: A → B → C → A（第 3 次 step 回到 A → 形成 A-B-C-A 环，3 边）
    stepper = FakeStepper(["B", "C", "A"])
    engine = ChainEngine(stepper=stepper, rules=["X", "Y", "Z"])
    # query 首 token = "A"，_extract_start_node → 起始节点 A
    result = await engine.reason(
        "ws-test",
        query="A 间接依赖的所有平台",
        rules=["X", "Y", "Z"],
        max_depth=10,
    )

    reasoning = result["reasoning"]
    assert reasoning["cycle_detected"] is True, "循环未被标记 cycle_detected=true"
    assert "cycle_path" in reasoning, "循环路径缺失"
    path = reasoning["cycle_path"]
    # 循环路径至少包含重复节点：开头 == 结尾
    assert len(path) >= 4, f"cycle_path 过短: {path}"
    assert path[0] == path[-1], f"cycle_path 首尾不等: {path}"
    # 中止：剩余深度没有被用完
    assert len(reasoning["steps"]) <= 4, f"循环未中止，steps 过多: {len(reasoning['steps'])}"
    assert "warnings" in result, "循环时未产生警告列表"
    assert any("循环" in w for w in result["warnings"]), f"warnings 无循环提示: {result['warnings']}"


# ── T013-2: max_depth ≤ 10，深度超限截断 + 警告 ──────────────────────────

@pytest.mark.asyncio
async def test_max_depth_exceeded_truncates_with_warning():
    """T013-2: max_depth=3 时，无限长 stepper 被截断，并生成 warning。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    # Fake: 无限产生不同节点（无循环，但深度超限）
    stepper = FakeStepper([f"node{i}" for i in range(1, 50)])
    engine = ChainEngine(stepper=stepper, rules=["R" for _ in range(50)])
    result = await engine.reason(
        "ws-test",
        query="depth test",
        rules=[f"R{i}" for i in range(50)],
        max_depth=3,
    )

    reasoning = result["reasoning"]
    # 传导边数 = len(steps) - 1（减去 s0 起点），不得超过 max_depth=3
    edge_count = len(reasoning["steps"]) - 1
    assert edge_count <= 3, (
        f"max_depth=3 但传导边数={edge_count} 未被截断 (steps={len(reasoning['steps'])})"
    )
    assert reasoning["cycle_detected"] is False
    assert any("深度" in w or "max_depth" in w for w in result["warnings"]), (
        f"深度超限无警告: {result['warnings']}"
    )


@pytest.mark.asyncio
async def test_max_depth_over_10_raises_value_error():
    """T013-2b: max_depth > 10 直接抛 ValueError（防无限递归硬性上限）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    engine = ChainEngine()
    with pytest.raises(ValueError) as exc_info:
        await engine.reason(
            "ws-test",
            query="too deep",
            rules=["R1", "R2"],
            max_depth=11,
        )
    msg = str(exc_info.value).lower()
    assert "max_depth" in msg or "深度" in msg


# ── T013-3: 规则冲突 conflicts 列表收集 ──────────────────────────────────

@pytest.mark.asyncio
async def test_rule_conflicts_are_collected_and_returned():
    """T013-3: stepper.conflicts() 返回 [R1, R2] 冲突，进入 reasoning.conflicts。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    conflicts = [
        {"rule_a": "R1", "rule_b": "R2", "description": "输出互斥"},
        {"rule_a": "R3", "rule_b": "R1", "description": "优先级冲突"},
    ]
    stepper = FakeStepper(["B", "C"], conflicts=conflicts)
    engine = ChainEngine(stepper=stepper, rules=["R1", "R2", "R3"])
    result = await engine.reason(
        "ws-test",
        query="conflict test",
        rules=["R1", "R2", "R3"],
        max_depth=10,
    )

    reasoning = result["reasoning"]
    assert "conflicts" in reasoning, "conflicts 字段缺失"
    assert len(reasoning["conflicts"]) == 2, (
        f"冲突数不匹配: {len(reasoning['conflicts'])}"
    )
    # RuleConflict 结构完整
    for c in reasoning["conflicts"]:
        assert {"rule_a", "rule_b", "description"}.issubset(c.keys()), (
            f"RuleConflict 结构错误: {c}"
        )


# ── T013-4: 正常链无循环 + 无冲突，steps 完整保留 ─────────────────────────

@pytest.mark.asyncio
async def test_no_cycle_chain_preserves_all_steps():
    """T013-4: A → B → C → D，无循环无冲突，4 步完整 + cycle_detected=false。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    stepper = FakeStepper(["B", "C", "D"])  # A(起点) → B → C → D
    engine = ChainEngine(stepper=stepper, rules=["R1", "R2", "R3"])
    result = await engine.reason(
        "ws-test",
        query="normal chain",
        rules=["R1", "R2", "R3"],
        max_depth=10,
    )

    reasoning = result["reasoning"]
    assert reasoning["cycle_detected"] is False
    assert reasoning["conflicts"] == []
    assert len(reasoning["steps"]) == 4, (
        f"正常链步数错: 期望 4 (起点+3), 实际 {len(reasoning['steps'])}"
    )
    # ChainStep 结构完整
    for s in reasoning["steps"]:
        assert {"step_id", "rule_id", "input", "output", "duration_ms"}.issubset(
            s.keys()
        ), f"ChainStep 结构错误: {s}"
    # 无警告
    assert result["warnings"] == [], f"正常链不应有警告: {result['warnings']}"
    # conclusion / confidence / chain_id 必填
    assert isinstance(reasoning["chain_id"], str) and reasoning["chain_id"]
    assert isinstance(reasoning["conclusion"], str)
    assert 0.0 <= reasoning["confidence"] <= 1.0
    assert result["mode"] == "chain"
