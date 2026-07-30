"""T016 [P] US4: 混合检索编排（TDD RED → GREEN）。

测试目标（tasks.md T016 + spec FR-007/008 + contracts /hybrid）:
  T016-1 skip: 组件 2 失败 + on_failure=skip → 组件 3 仍执行 + warning
  T016-2 abort: 组件 2 失败 + on_failure=abort → 组件 3 不执行 + warning
  T016-3 degrade: 组件 2 失败 + on_failure=degrade → 组件 3 仍执行 + 失败组件标记 degraded
  T016-4 组件数 > 10 → ValueError（contracts/api-contracts.md L71 max_length=10）
  T016-5 组件数 > 5 → 性能警告（spec §99 "超过 5 个组件时给出性能警告"）
  T016-6 结果合并 concat: 多组件 rows 顺序拼接
  T016-7 全部成功 → 无 warning + total = sum(rows)

设计 (Q5 §5.7 决策):
  · 不直接适配 PipelineService（其 6 阶段是本体构建，与检索编排语义不符）
  · 复用其"有序步骤 + on_failure + 结果聚合"模式 → Thin Adapter
  · 注入 engines: Dict[str, Any]，每个引擎须有 .search(ws, query, limit) 适配器
"""

from __future__ import annotations

import pytest


# ── FakeEngine：可控成功/失败 + 计数调用次数 ─────────────────────────────

class FakeEngine:
    """可控的检索引擎：根据 raise_on 决定是否抛异常。"""

    def __init__(self, name: str, rows=None, raise_on=False):
        self.name = name
        self._rows = rows or []
        self._raise = raise_on
        self.call_count = 0

    async def search(self, workspace_id: str, query: str, limit: int = 20):
        self.call_count += 1
        if self._raise:
            raise RuntimeError(f"{self.name} 故障")
        return {
            "mode": self.name,
            "total": len(self._rows),
            "rows": list(self._rows),
            "explain": {"source": self.name},
        }


def _make_components(specs):
    """specs: [(type, params, on_failure), ...] → list of dict。"""
    return [
        {"type": t, "params": p, "on_failure": f}
        for t, p, f in specs
    ]


# ── T016-1: skip — 失败组件跳过，后续继续执行 ────────────────────────────

@pytest.mark.asyncio
async def test_skip_strategy_continues_after_failure():
    """T016-1: 组件 2 失败 + on_failure=skip → 组件 3 仍执行 + warnings 含跳过提示。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[{"id": "g1"}])
    eng2 = FakeEngine("chain", raise_on=True)
    eng3 = FakeEngine("metric", rows=[{"id": "m1"}])
    engines = {"graph": eng1, "chain": eng2, "metric": eng3}

    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q1"}, "skip"),
        ("chain", {"query": "q2"}, "skip"),
        ("metric", {"query": "q3"}, "skip"),
    ])
    result = await orch.orchestrate("ws-test", components)

    assert eng1.call_count == 1
    assert eng2.call_count == 1  # 调过但失败
    assert eng3.call_count == 1, "skip 策略下后续组件应继续执行"
    assert result["mode"] == "hybrid"
    assert any("跳过" in w or "skip" in w.lower() for w in result["warnings"]), (
        f"warnings 缺少跳过提示: {result['warnings']}"
    )
    # 失败组件在 components 中标记 skipped
    statuses = [c["status"] for c in result["components"]]
    assert "skipped" in statuses, f"未标记 skipped: {statuses}"


# ── T016-2: abort — 失败组件中止整条链 ───────────────────────────────────

@pytest.mark.asyncio
async def test_abort_strategy_stops_chain():
    """T016-2: 组件 2 失败 + on_failure=abort → 组件 3 不执行 + warning。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[{"id": "g1"}])
    eng2 = FakeEngine("chain", raise_on=True)
    eng3 = FakeEngine("metric", rows=[{"id": "m1"}])
    engines = {"graph": eng1, "chain": eng2, "metric": eng3}

    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q1"}, "skip"),
        ("chain", {"query": "q2"}, "abort"),
        ("metric", {"query": "q3"}, "skip"),
    ])
    result = await orch.orchestrate("ws-test", components)

    assert eng1.call_count == 1
    assert eng2.call_count == 1
    assert eng3.call_count == 0, "abort 策略下后续组件不应执行"
    assert any("中止" in w or "abort" in w.lower() for w in result["warnings"]), (
        f"warnings 缺少中止提示: {result['warnings']}"
    )
    statuses = [c["status"] for c in result["components"]]
    assert "aborted" in statuses or "error" in statuses, (
        f"未标记 aborted/error: {statuses}"
    )


# ── T016-3: degrade — 失败组件降级返回，后续继续 ─────────────────────────

@pytest.mark.asyncio
async def test_degrade_strategy_returns_partial_and_continues():
    """T016-3: 组件 2 失败 + on_failure=degrade → 标记 degraded + 组件 3 仍执行。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[{"id": "g1"}])
    eng2 = FakeEngine("chain", raise_on=True)
    eng3 = FakeEngine("metric", rows=[{"id": "m1"}])
    engines = {"graph": eng1, "chain": eng2, "metric": eng3}

    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q1"}, "skip"),
        ("chain", {"query": "q2"}, "degrade"),
        ("metric", {"query": "q3"}, "skip"),
    ])
    result = await orch.orchestrate("ws-test", components)

    assert eng3.call_count == 1, "degrade 策略下后续组件应继续执行"
    statuses = [c["status"] for c in result["components"]]
    assert "degraded" in statuses, f"未标记 degraded: {statuses}"
    assert any("降级" in w or "degrade" in w.lower() for w in result["warnings"])


# ── T016-4: 组件数 > 10 → ValueError ─────────────────────────────────────

@pytest.mark.asyncio
async def test_components_over_10_raises_value_error():
    """T016-4: 11 个组件 → ValueError（FR-007 边界 max=10）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    orch = HybridOrchestrator(engines={"graph": FakeEngine("graph")})
    components = _make_components([("graph", {"query": "q"}, "skip")] * 11)
    with pytest.raises(ValueError) as exc_info:
        await orch.orchestrate("ws-test", components)
    msg = str(exc_info.value).lower()
    assert "10" in msg or "组件" in msg


# ── T016-5: 组件数 > 5 → 性能警告 ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_components_over_5_emits_performance_warning():
    """T016-5: 6 个组件 → warnings 含性能警告（spec §99）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng = FakeEngine("graph", rows=[{"id": "g1"}])
    orch = HybridOrchestrator(engines={"graph": eng})
    components = _make_components([("graph", {"query": "q"}, "skip")] * 6)
    result = await orch.orchestrate("ws-test", components)

    assert any("性能" in w or "performance" in w.lower() or "5" in w for w in result["warnings"]), (
        f"6 个组件未生成性能警告: {result['warnings']}"
    )


# ── T016-6: 结果合并 concat ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_merge_concat_appends_rows_in_order():
    """T016-6: 多组件 rows 按执行顺序拼接（merge=concat 默认）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[{"id": "g1"}, {"id": "g2"}])
    eng2 = FakeEngine("metric", rows=[{"id": "m1"}])
    engines = {"graph": eng1, "metric": eng2}

    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q1"}, "skip"),
        ("metric", {"query": "q2"}, "skip"),
    ])
    result = await orch.orchestrate("ws-test", components)

    # rows 按组件顺序拼接：[g1, g2, m1]
    assert len(result["rows"]) == 3, f"合并行数错: {len(result['rows'])}"
    ids = [r["id"] for r in result["rows"]]
    assert ids == ["g1", "g2", "m1"], f"rows 顺序错: {ids}"
    assert result["total"] == 3


# ── T016-7: 全部成功 → 无 warning + total = sum ──────────────────────────

@pytest.mark.asyncio
async def test_all_components_success_no_warnings():
    """T016-7: 3 个组件全部成功 → warnings=[] + total=各组件 rows 之和。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[{"id": "g1"}])
    eng2 = FakeEngine("chain", rows=[{"id": "c1"}, {"id": "c2"}])
    eng3 = FakeEngine("metric", rows=[{"id": "m1"}])
    engines = {"graph": eng1, "chain": eng2, "metric": eng3}

    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q1"}, "skip"),
        ("chain", {"query": "q2"}, "skip"),
        ("metric", {"query": "q3"}, "skip"),
    ])
    result = await orch.orchestrate("ws-test", components)

    assert result["warnings"] == [], f"全成功不应有 warnings: {result['warnings']}"
    assert result["total"] == 4, f"total 应为 1+2+1=4: {result['total']}"
    statuses = [c["status"] for c in result["components"]]
    assert all(s == "ok" for s in statuses), f"应全部 ok: {statuses}"
    assert result["mode"] == "hybrid"
