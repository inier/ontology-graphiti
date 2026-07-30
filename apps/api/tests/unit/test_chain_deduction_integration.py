"""T029 TDD tests — ChainEngine + DeductionStepper 集成 (Phase 2 / Iter 2).

验证 ChainEngine 注入 deduction_engine 后的真实推理路径：
  - DeductionStepper 懒加载：首次 step() 触发 create_and_simulate
  - metric_impacts → steps 经循环检测层（008 层保留）
  - rule_violations → conflicts 透传
  - 显式 stepper 优先（TDD FakeStepper 不被 DeductionStepper 覆盖）
  - deduction_engine 异常 → 降级空 steps（不阻断，explain.status=degraded）
  - 无 deduction_engine → _DefaultStepper（Phase 1 行为不变）

DeductionEngine 用 FakeDeductionEngine mock（不依赖真实 storage/Neo4j）。
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest


# ── fakes ─────────────────────────────────────────────────────────────────


class FakeDeductionEngine:
    """可控的 DeductionEngine mock，返回预设 ChainResult。"""

    def __init__(self, chain_result: Dict[str, Any] = None, simulate_raises: bool = False):
        self._chain_result = chain_result or {
            "status": "completed",
            "metric_impacts": [],
            "rule_violations": [],
            "risk_score": 0.0,
            "recommendation": "",
            "projected_state": {},
        }
        self._simulate_raises = simulate_raises
        self.scenario_created: List[str] = []
        self.scenario_deleted: List[str] = []

    async def create_scenario(self, name, description, **kwargs):
        self.scenario_created.append(name)
        return {"scenario_id": "sc-test", "name": name}

    async def add_execution_chain(self, scenario_id, name, description, steps, conditions=None):
        return {"chain_id": "ch-test", "steps": steps}

    async def simulate_chain(self, scenario_id, chain_id):
        if self._simulate_raises:
            raise RuntimeError("deduction engine crash")
        return self._chain_result

    async def delete_scenario(self, scenario_id):
        self.scenario_deleted.append(scenario_id)
        return {"status": "ok"}


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def deduction_result_with_impacts():
    """有 2 个 metric_impacts + 1 个 violation 的 ChainResult。"""
    return {
        "status": "completed",
        "chain_id": "ch-test",
        "metric_impacts": [
            {"metric_name": "pop", "before": "A", "after": "B", "delta": 10, "unit": "人"},
            {"metric_name": "area", "before": "B", "after": "C", "delta": -5, "unit": "km²"},
        ],
        "rule_violations": [
            {"rule_id": "R1", "rule_type": "constraint", "description": "超载"},
        ],
        "risk_score": 30.0,
        "recommendation": "建议扩容",
        "projected_state": {"pop": "B", "area": "C"},
    }


# ══════════════════════════════════════════════════════════════════════════
# T029-1: 注入 deduction_engine → DeductionStepper 路径
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_deduction_engine_produces_real_steps(deduction_result_with_impacts):
    """T029-1: 注入 deduction_engine → metric_impacts 转为 steps（非空）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    engine = FakeDeductionEngine(chain_result=deduction_result_with_impacts)
    ce = ChainEngine(deduction_engine=engine, rules=["R1", "R2"])

    result = await ce.reason("ws-test", query="扩张影响", rules=["R1", "R2"], max_depth=10)

    reasoning = result["reasoning"]
    # metric_impacts 有 2 项 → steps 应含 s0(起点) + 2 = 3
    assert len(reasoning["steps"]) >= 3, f"steps 过少: {len(reasoning['steps'])}"
    # scenario 被创建和清理
    assert len(engine.scenario_created) == 1
    assert engine.scenario_deleted == ["sc-test"]


@pytest.mark.asyncio
async def test_deduction_violations_become_conflicts(deduction_result_with_impacts):
    """T029-2: rule_violations → reasoning.conflicts。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    engine = FakeDeductionEngine(chain_result=deduction_result_with_impacts)
    ce = ChainEngine(deduction_engine=engine)

    result = await ce.reason("ws-test", query="test", rules=["R1", "R2"], max_depth=10)

    conflicts = result["reasoning"]["conflicts"]
    assert len(conflicts) == 1
    assert conflicts[0]["rule_a"] == "R1"
    assert conflicts[0]["description"] == "超载"


@pytest.mark.asyncio
async def test_deduction_conclusion_from_recommendation(deduction_result_with_impacts):
    """T029-3: recommendation → conclusion。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    engine = FakeDeductionEngine(chain_result=deduction_result_with_impacts)
    ce = ChainEngine(deduction_engine=engine)

    result = await ce.reason("ws-test", query="test", rules=["R1"], max_depth=10)

    assert result["reasoning"]["conclusion"] == "建议扩容"


# ══════════════════════════════════════════════════════════════════════════
# T029-2: 循环检测层保留（008 层在 DeductionStepper 之上）
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_cycle_detection_still_runs_on_deduction_steps():
    """T029-4: DeductionStepper 产出的 steps 仍经循环检测（before==after 形成自环）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    # 2 个 impacts: A→B, B→A → 第二步 output=A 已在 visited → 循环
    cyclic_result = {
        "status": "completed",
        "metric_impacts": [
            {"metric_name": "m1", "before": "A", "after": "B", "delta": 1, "unit": ""},
            {"metric_name": "m2", "before": "B", "after": "A", "delta": 1, "unit": ""},
        ],
        "rule_violations": [],
        "risk_score": 0.0,
        "recommendation": "",
        "projected_state": {},
    }
    engine = FakeDeductionEngine(chain_result=cyclic_result)
    ce = ChainEngine(deduction_engine=engine)

    result = await ce.reason("ws-test", query="A", rules=["R1", "R2"], max_depth=10)

    reasoning = result["reasoning"]
    # 起点为 A（query 首 token），第一步 A→B，第二步 B→A（A 已访问）→ 循环
    assert reasoning["cycle_detected"] is True
    assert "cycle_path" in reasoning
    assert any("循环" in w for w in result["warnings"])


# ══════════════════════════════════════════════════════════════════════════
# T029-3: 显式 stepper 优先（TDD FakeStepper 不被覆盖）
# ══════════════════════════════════════════════════════════════════════════


class _FakeStepper:
    """TDD FakeStepper（Phase 1 测试用），不应被 DeductionStepper 覆盖。"""

    def __init__(self, outputs):
        self._outputs = list(outputs)
        self._idx = 0

    async def step(self, rule_id, input_val, duration_ms=50):
        if self._idx >= len(self._outputs):
            return None
        out = self._outputs[self._idx]
        self._idx += 1
        return {"step_id": f"s{self._idx}", "rule_id": rule_id, "input": input_val, "output": out, "duration_ms": duration_ms}

    def conflicts(self):
        return []


@pytest.mark.asyncio
async def test_explicit_stepper_takes_priority_over_deduction():
    """T029-5: 同时注入 stepper + deduction_engine → 显式 stepper 优先。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    engine = FakeDeductionEngine()
    stepper = _FakeStepper(["X", "Y"])
    ce = ChainEngine(stepper=stepper, deduction_engine=engine)

    result = await ce.reason("ws-test", query="A", rules=["R1", "R2"], max_depth=10)

    # 显式 stepper 的 outputs 被使用（非 DeductionEngine 的 metric_impacts）
    steps = result["reasoning"]["steps"]
    outputs = [s["output"] for s in steps]
    assert "X" in outputs and "Y" in outputs
    # DeductionEngine 未被调用
    assert len(engine.scenario_created) == 0


# ══════════════════════════════════════════════════════════════════════════
# T029-4: 降级路径（deduction_engine 异常 → 不阻断）
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_deduction_crash_does_not_block_api():
    """T029-6: simulate_chain 抛异常 → 降级空 steps + explain.status=degraded。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    engine = FakeDeductionEngine(simulate_raises=True)
    ce = ChainEngine(deduction_engine=engine)

    result = await ce.reason("ws-test", query="test", rules=["R1"], max_depth=10)

    # 不抛异常；返回有效结构
    assert result["mode"] == "chain"
    assert "reasoning" in result
    # 降级标记
    explain = result.get("explain", {})
    assert explain.get("status") == "degraded"
    # 仅有 s0 起点 step（无 metric_impacts）
    assert len(result["reasoning"]["steps"]) == 1


@pytest.mark.asyncio
async def test_deduction_empty_impacts_returns_only_init_step():
    """T029-7: ChainResult 无 metric_impacts → 仅 s0 起点，不阻断。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    engine = FakeDeductionEngine(chain_result={
        "status": "completed", "metric_impacts": [], "rule_violations": [],
        "risk_score": 0.0, "recommendation": "无影响", "projected_state": {},
    })
    ce = ChainEngine(deduction_engine=engine)

    result = await ce.reason("ws-test", query="test", rules=["R1"], max_depth=10)

    assert result["mode"] == "chain"
    assert len(result["reasoning"]["steps"]) == 1  # 仅 s0
    # 无降级（simulate 成功，只是无 impacts）
    explain = result.get("explain", {})
    assert explain.get("status") != "degraded"


# ══════════════════════════════════════════════════════════════════════════
# T029-5: 无 deduction_engine → Phase 1 行为不变
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_no_deduction_engine_uses_default_stepper():
    """T029-8: 未注入 deduction_engine → _DefaultStepper（Phase 1 行为）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.chain_engine import ChainEngine

    ce = ChainEngine()  # 无 stepper，无 deduction_engine

    result = await ce.reason("ws-test", query="test", rules=["R1"], max_depth=10)

    assert result["mode"] == "chain"
    # _DefaultStepper 无 outputs → 仅 s0
    assert len(result["reasoning"]["steps"]) == 1
    # 无 explain.degraded（不是降级，是默认行为）
    assert "explain" not in result or result["explain"].get("status") != "degraded"
