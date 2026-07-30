"""T027/T028 TDD tests — ScenarioMapper + ChainResultAdapter (Phase 2 / Iter 2).

验证 DeductionEngine 集成的两个适配器：

ScenarioMapper (T027):
  - create_and_simulate: create → add_chain → simulate → cleanup → return ChainResult
  - rules[] → ChainStep[] 映射
  - 清理总执行（try/finally，即使 simulate 失败）
  - create_scenario 失败 → 返回 error，不调 add_chain

ChainResultAdapter (T028):
  - to_steps: metric_impacts → ChainEngine steps[{step_id, rule_id, input, output, duration_ms}]
  - to_conflicts: rule_violations → conflicts[{rule_a, rule_b, description}]
  - to_conclusion: projected_state / recommendation → conclusion string
  - to_confidence: risk_score → confidence = 1 - risk_score/100 (clamp 0..1)
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from odap.biz.core.ontology.semantic_retrieval.impl.deduction_adapter import (
    ChainResultAdapter,
    ScenarioMapper,
)


# ── fakes ─────────────────────────────────────────────────────────────────


class FakeDeductionEngine:
    """记录调用顺序的 mock DeductionEngine。"""

    def __init__(
        self,
        chain_result: Dict[str, Any] = None,
        create_fails: bool = False,
        simulate_fails: bool = False,
    ):
        self._chain_result = chain_result or {"status": "completed", "metric_impacts": []}
        self._create_fails = create_fails
        self._simulate_fails = simulate_fails
        self.calls: List[str] = []
        self.deleted_scenarios: List[str] = []

    async def create_scenario(self, name, description, **kwargs):
        self.calls.append("create_scenario")
        if self._create_fails:
            return {"status": "error", "message": "create failed"}
        return {"scenario_id": "sc-1", "name": name, "description": description}

    async def add_execution_chain(self, scenario_id, name, description, steps, conditions=None):
        self.calls.append("add_execution_chain")
        self.calls.append(f"steps_count={len(steps)}")
        return {"chain_id": "ch-1", "name": name, "steps": steps}

    async def simulate_chain(self, scenario_id, chain_id):
        self.calls.append("simulate_chain")
        if self._simulate_fails:
            return {"status": "error", "message": "simulate failed"}
        return self._chain_result

    async def delete_scenario(self, scenario_id):
        self.calls.append("delete_scenario")
        self.deleted_scenarios.append(scenario_id)
        return {"status": "ok", "scenario_id": scenario_id}


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def sample_chain_result():
    """模拟 DeductionEngine.simulate_chain 返回的 ChainResult dict。"""
    return {
        "chain_id": "ch-1",
        "status": "completed",
        "metric_impacts": [
            {"metric_name": "population", "before": 100, "after": 150, "delta": 50, "unit": "人"},
            {"metric_name": "area", "before": 50, "after": 45, "delta": -5, "unit": "km²"},
        ],
        "risk_level": "medium",
        "risk_score": 35.0,
        "rule_violations": [
            {"rule_id": "R1", "rule_type": "constraint", "description": "超载", "severity": "warning"},
        ],
        "recommendation": "建议增加资源",
        "confidence": 0.65,
        "projected_state": {"population": 150, "area": 45},
    }


# ══════════════════════════════════════════════════════════════════════════
# T027: ScenarioMapper
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_create_and_simulate_happy_path(sample_chain_result):
    """T027-1: create → add_chain → simulate → cleanup → return ChainResult。"""
    engine = FakeDeductionEngine(chain_result=sample_chain_result)
    mapper = ScenarioMapper(engine)

    result = await mapper.create_and_simulate(
        query="势力扩张影响", rules=["R1", "R2"]
    )

    assert result["status"] == "completed"
    assert result["chain_id"] == "ch-1"
    # 调用顺序正确
    assert engine.calls == [
        "create_scenario", "add_execution_chain", "steps_count=2",
        "simulate_chain", "delete_scenario",
    ]
    # 清理执行
    assert engine.deleted_scenarios == ["sc-1"]


@pytest.mark.asyncio
async def test_rules_mapped_to_chain_steps():
    """T027-2: rules[] → ChainStep[]（每条规则一个 step，含 step_order + action_type_id）。"""
    engine = FakeDeductionEngine()
    mapper = ScenarioMapper(engine)
    await mapper.create_and_simulate(query="test", rules=["RULE_A", "RULE_B", "RULE_C"])
    # steps_count=3 证明 rules 被映射为 3 个 ChainStep
    assert "steps_count=3" in engine.calls


@pytest.mark.asyncio
async def test_cleanup_always_called_on_simulate_failure():
    """T027-3: simulate_chain 失败时，cleanup 仍在 finally 中执行。"""
    engine = FakeDeductionEngine(simulate_fails=True)
    mapper = ScenarioMapper(engine)

    result = await mapper.create_and_simulate(query="test", rules=["R1"])

    assert result["status"] == "error"
    # 即使 simulate 失败，delete_scenario 仍被调用
    assert "delete_scenario" in engine.calls
    assert engine.deleted_scenarios == ["sc-1"]


@pytest.mark.asyncio
async def test_create_scenario_failure_returns_error_no_chain():
    """T027-4: create_scenario 失败 → 返回 error，不调 add_execution_chain。"""
    engine = FakeDeductionEngine(create_fails=True)
    mapper = ScenarioMapper(engine)

    result = await mapper.create_and_simulate(query="test", rules=["R1"])

    assert result["status"] == "error"
    assert "add_execution_chain" not in engine.calls
    assert "simulate_chain" not in engine.calls


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_block_result(sample_chain_result):
    """T027-5: delete_scenario 抛异常时不阻断结果返回（try/except 兜底）。"""
    engine = FakeDeductionEngine(chain_result=sample_chain_result)

    async def _boom(scenario_id):
        raise RuntimeError("cleanup boom")
    engine.delete_scenario = _boom

    mapper = ScenarioMapper(engine)
    result = await mapper.create_and_simulate(query="test", rules=["R1"])
    # 结果仍正常返回
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_empty_rules_still_creates_scenario():
    """T027-6: rules=[] 时仍创建 scenario + chain（0 steps），不阻断。"""
    engine = FakeDeductionEngine()
    mapper = ScenarioMapper(engine)
    result = await mapper.create_and_simulate(query="empty", rules=[])
    assert "steps_count=0" in engine.calls
    assert result["status"] == "completed"


# ══════════════════════════════════════════════════════════════════════════
# T028: ChainResultAdapter
# ══════════════════════════════════════════════════════════════════════════


def test_to_steps_maps_metric_impacts(sample_chain_result):
    """T028-1: metric_impacts → steps[{step_id, rule_id, input, output, duration_ms}]。"""
    rules = ["R1", "R2"]
    steps = ChainResultAdapter.to_steps(sample_chain_result, rules)

    assert len(steps) == 2
    assert steps[0]["rule_id"] == "R1"
    assert steps[0]["input"] == "100"  # before
    assert steps[0]["output"] == "150"  # after
    assert {"step_id", "rule_id", "input", "output", "duration_ms"}.issubset(steps[0].keys())


def test_to_steps_handles_more_rules_than_impacts(sample_chain_result):
    """T028-1b: rules 比 impacts 多时，仅产出 impacts 数量的 steps。"""
    rules = ["R1", "R2", "R3", "R4"]
    steps = ChainResultAdapter.to_steps(sample_chain_result, rules)
    assert len(steps) == 2  # 跟随 metric_impacts 数量


def test_to_steps_empty_impacts():
    """T028-1c: 无 metric_impacts → 空 steps 列表。"""
    result = {"metric_impacts": []}
    steps = ChainResultAdapter.to_steps(result, ["R1"])
    assert steps == []


def test_to_conflicts_maps_rule_violations(sample_chain_result):
    """T028-2: rule_violations → conflicts[{rule_a, rule_b, description}]。"""
    conflicts = ChainResultAdapter.to_conflicts(sample_chain_result)

    assert len(conflicts) == 1
    assert conflicts[0]["rule_a"] == "R1"
    assert conflicts[0]["description"] == "超载"
    assert {"rule_a", "rule_b", "description"}.issubset(conflicts[0].keys())


def test_to_conflicts_empty_violations():
    """T028-2b: 无 rule_violations → 空 conflicts。"""
    assert ChainResultAdapter.to_conflicts({"rule_violations": []}) == []


def test_to_conclusion_prefers_recommendation(sample_chain_result):
    """T028-3: 有 recommendation 时优先使用。"""
    conclusion = ChainResultAdapter.to_conclusion(sample_chain_result)
    assert conclusion == "建议增加资源"


def test_to_conclusion_falls_back_to_projected_state():
    """T028-3b: 无 recommendation 时用 projected_state。"""
    result = {"recommendation": "", "projected_state": {"pop": 100}}
    conclusion = ChainResultAdapter.to_conclusion(result)
    assert "pop" in conclusion or "100" in conclusion


def test_to_confidence_from_risk_score(sample_chain_result):
    """T028-4: risk_score=35 → confidence=1-0.35=0.65。"""
    confidence = ChainResultAdapter.to_confidence(sample_chain_result)
    assert confidence == pytest.approx(0.65, rel=1e-6)


def test_to_confidence_clamps_to_zero():
    """T028-4b: risk_score=120 → confidence=0（不超过 0）。"""
    result = {"risk_score": 120.0}
    assert ChainResultAdapter.to_confidence(result) == 0.0


def test_to_confidence_clamps_to_one():
    """T028-4c: risk_score=-10 → confidence=1（不低于 1）。"""
    result = {"risk_score": -10.0}
    assert ChainResultAdapter.to_confidence(result) == 1.0
