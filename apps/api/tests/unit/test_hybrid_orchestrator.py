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


# ══════════════════════════════════════════════════════════════════════
# Phase 3 T034: 混合故障注入增强 (Phase 2+ 质量门深化)
# ══════════════════════════════════════════════════════════════════════


# ── T034-1: 多个 on_failure 策略混合 + 多种故障类型 ───────────────────────

class _FlakyEngine:
    """可控故障引擎：奇数调抛 RuntimeError，偶数调返回成功；或逐次指定返回。"""

    def __init__(self, name: str, *, raise_pattern=None, rows_per_call=None):
        self.name = name
        self._raise_pat = raise_pattern  # list[bool]; None=全成功; True=raise
        self._rows = rows_per_call or [[]]
        self.calls = []  # (ws, query, limit)

    async def search(self, workspace_id: str, query: str, limit: int = 20):
        self.calls.append((workspace_id, query, limit))
        idx = len(self.calls) - 1
        if self._raise_pat and idx < len(self._raise_pat) and self._raise_pat[idx]:
            raise RuntimeError(f"{self.name} 偶发故障 #{idx}")
        rows = self._rows[idx] if idx < len(self._rows) else list(self._rows[-1])
        return {
            "mode": self.name,
            "total": len(rows),
            "rows": list(rows),
            "explain": {"source": self.name, "call_index": idx},
        }


@pytest.mark.asyncio
async def test_mixed_strategies_with_mixed_failure_patterns():
    """T034-1: 5 组件 on_failure 策略混合：skip/abort/degrade/skip/abort + 不同故障模式。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng_g = _FlakyEngine("graph", rows_per_call=[[{"id": "g1"}]])  # 成功
    eng_n = _FlakyEngine("nl", raise_pattern=[True])              # 1st raise
    eng_c = _FlakyEngine("chain", rows_per_call=[[{"id": "c1"}, {"id": "c2"}]])  # 成功
    eng_m = _FlakyEngine("mdl", raise_pattern=[True])             # 1st raise
    eng_t = _FlakyEngine("metric", rows_per_call=[[{"id": "t1"}]]) # 成功（若执行到）

    engines = {
        "graph": eng_g, "nl": eng_n, "chain": eng_c,
        "mdl": eng_m, "metric": eng_t,
    }
    orch = HybridOrchestrator(engines=engines)
    # on_failure: skip | abort | degrade | skip | skip
    components = [
        {"type": "graph", "params": {"query": "qg"}, "on_failure": "skip"},
        {"type": "nl",    "params": {"query": "qn"}, "on_failure": "abort"},  # ← 故障且 abort
        {"type": "chain", "params": {"query": "qc"}, "on_failure": "degrade"},
        {"type": "mdl",   "params": {"query": "qm"}, "on_failure": "skip"},
        {"type": "metric","params": {"query": "qt"}, "on_failure": "skip"},
    ]
    result = await orch.orchestrate("ws-t034", components)

    # nl abort 生效：后续 chain/mdl/metric 不执行
    assert len(eng_g.calls) == 1 and eng_n.calls, "前置执行必调"
    assert eng_c.calls == [] and eng_m.calls == [] and eng_t.calls == [], (
        "abort 后后续组件不执行"
    )
    statuses = [c["status"] for c in result["components"]]
    # 索引 0 ok, 1 error/aborted, 2..4 未执行 (not_executed/aborted/skipped 之一)
    assert statuses[0] == "ok"
    assert statuses[1] in ("error", "aborted"), f"故障组件应标记 error/aborted: {statuses}"
    for i in (2, 3, 4):
        assert statuses[i] in ("aborted", "not_executed", "skipped", "pending"), (
            f"abort 后组件 {i} 状态错: {statuses[i]}"
        )
    # warning 含 "中止/abort" 字样
    assert any(
        "中止" in w or "abort" in w.lower()
        for w in result["warnings"]
    ), f"缺少 abort 警告: {result['warnings']}"


# ── T034-2: 降级组件结果被标记 degraded，且其 rows 不计入 total ────────────

@pytest.mark.asyncio
async def test_degraded_component_not_counted_in_total():
    """T034-2: degrade 组件失败后，其 total 不纳入汇总，仅保留成功组件 rows。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng_g = _FlakyEngine("graph", rows_per_call=[[{"id": "g1"}, {"id": "g2"}]])
    eng_c = _FlakyEngine("chain", raise_pattern=[True])  # degrade
    eng_m = _FlakyEngine("metric", rows_per_call=[[{"id": "m1"}]])
    engines = {"graph": eng_g, "chain": eng_c, "metric": eng_m}
    orch = HybridOrchestrator(engines=engines)
    components = [
        {"type": "graph",  "params": {"query": "q"}, "on_failure": "degrade"},
        {"type": "chain",  "params": {"query": "q"}, "on_failure": "degrade"},
        {"type": "metric", "params": {"query": "q"}, "on_failure": "degrade"},
    ]
    result = await orch.orchestrate("ws-t034", components)

    statuses = [c["status"] for c in result["components"]]
    assert statuses == ["ok", "degraded", "ok"], statuses
    # rows 仅 ok 组件：graph 2 行 + metric 1 行 = 3 行
    ids = [r["id"] for r in result["rows"]]
    assert ids == ["g1", "g2", "m1"], f"rows 应仅含 ok 组件: {ids}"
    assert result["total"] == 3, f"total 应为 3: {result['total']}"


# ── T034-3: 未知组件类型 → ValueError 明确提示 ─────────────────────────────

@pytest.mark.asyncio
async def test_unknown_component_type_raises_value_error():
    """T034-3: 组件 type 不在 engines 键集中 → ValueError（避免 KeyError 吞掉上下文）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    orch = HybridOrchestrator(engines={"graph": _FlakyEngine("graph")})
    components = [
        {"type": "graph",         "params": {"query": "q"}, "on_failure": "skip"},
        {"type": "does_not_exist","params": {"query": "q"}, "on_failure": "skip"},
    ]
    with pytest.raises(ValueError) as exc:
        await orch.orchestrate("ws-t034", components)
    msg = str(exc.value)
    assert "does_not_exist" in msg or "组件类型" in msg or "component" in msg.lower(), (
        f"错误消息未标识未知类型: {msg}"
    )


# ── T034-4: on_failure 字段缺失 → 默认 degrade（保守策略） ────────────────

@pytest.mark.asyncio
async def test_on_failure_defaults_to_degrade():
    """T034-4: 组件 on_failure 为空 → 按 degrade 保守策略执行（不中止后续）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng_g = _FlakyEngine("graph", rows_per_call=[[{"id": "g1"}]])
    eng_c = _FlakyEngine("chain", raise_pattern=[True])  # 失败
    eng_m = _FlakyEngine("metric", rows_per_call=[[{"id": "m1"}]])
    engines = {"graph": eng_g, "chain": eng_c, "metric": eng_m}
    orch = HybridOrchestrator(engines=engines)
    # 第二个组件缺 on_failure，期望按 degrade 保守策略处理：chain 失败 → degraded，metric 仍执行
    components = [
        {"type": "graph",  "params": {"query": "q"}, "on_failure": "skip"},
        {"type": "chain",  "params": {"query": "q"}},                      # ← 缺 on_failure
        {"type": "metric", "params": {"query": "q"}, "on_failure": "skip"},
    ]
    result = await orch.orchestrate("ws-t034", components)

    assert len(eng_m.calls) == 1, "on_failure 缺失应保守 degrade，后续 metric 仍执行"
    statuses = [c["status"] for c in result["components"]]
    assert statuses[1] in ("degraded", "skipped"), (
        f"on_failure 缺省策略失败组件状态错: {statuses[1]}"
    )
    assert statuses[2] == "ok"


# ══════════════════════════════════════════════════════════════════════
# Phase 4 T038: Hybrid merge=interleave/rank 实现（contracts 扩展 + 代码预留完整化）
# ══════════════════════════════════════════════════════════════════════


# ── T038-1: merge=interleave — 多组件 rows 交替拼接 ───────────────────────

@pytest.mark.asyncio
async def test_merge_interleave_alternates_rows_across_components():
    """T038-1: merge=interleave → rows 按轮询交替拼接（非 concat 顺序追加）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[{"id": "g1"}, {"id": "g2"}, {"id": "g3"}])
    eng2 = FakeEngine("metric", rows=[{"id": "m1"}, {"id": "m2"}])
    engines = {"graph": eng1, "metric": eng2}
    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q1"}, "skip"),
        ("metric", {"query": "q2"}, "skip"),
    ])
    result = await orch.orchestrate("ws-t038", components, merge="interleave")

    ids = [r["id"] for r in result["rows"]]
    # interleave: g1, m1, g2, m2, g3（轮询，短组件耗尽后剩余追加）
    assert ids == ["g1", "m1", "g2", "m2", "g3"], (
        f"interleave 顺序错: {ids}"
    )
    assert result["total"] == 5


# ── T038-2: merge=rank — 按 row.score 降序排列 ───────────────────────────

@pytest.mark.asyncio
async def test_merge_rank_orders_by_score_descending():
    """T038-2: merge=rank → rows 按 score 降序（无 score 视为 0 排末尾）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[
        {"id": "g1", "score": 0.3},
        {"id": "g2", "score": 0.9},
    ])
    eng2 = FakeEngine("metric", rows=[
        {"id": "m1", "score": 0.7},
        {"id": "m2"},  # 无 score → 0.0
    ])
    engines = {"graph": eng1, "metric": eng2}
    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q1"}, "skip"),
        ("metric", {"query": "q2"}, "skip"),
    ])
    result = await orch.orchestrate("ws-t038", components, merge="rank")

    ids = [r["id"] for r in result["rows"]]
    # rank by score desc: g2(0.9), m1(0.7), g1(0.3), m2(0.0)
    assert ids == ["g2", "m1", "g1", "m2"], (
        f"rank 顺序错: {ids}"
    )


# ── T038-3: merge=unknown → warn 回退 concat ─────────────────────────────

@pytest.mark.asyncio
async def test_merge_unknown_falls_back_to_concat_with_warning():
    """T038-3: merge=invalid → 回退 concat + warning 提示。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[{"id": "g1"}])
    eng2 = FakeEngine("metric", rows=[{"id": "m1"}])
    engines = {"graph": eng1, "metric": eng2}
    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q1"}, "skip"),
        ("metric", {"query": "q2"}, "skip"),
    ])
    result = await orch.orchestrate("ws-t038", components, merge="invalid_strategy")

    # 回退 concat: g1, m1
    ids = [r["id"] for r in result["rows"]]
    assert ids == ["g1", "m1"], f"应回退 concat: {ids}"
    # warning 含回退提示
    assert any(
        "concat" in w.lower() or "回退" in w or "fallback" in w.lower()
        for w in result["warnings"]
    ), f"缺少回退 warning: {result['warnings']}"


# ── T038-4: interleave 跳过 degraded/skipped 组件 ─────────────────────────

@pytest.mark.asyncio
async def test_merge_interleave_skips_failed_components():
    """T038-4: interleave 只合并 status=ok 的组件（degraded/skipped 跳过）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[{"id": "g1"}, {"id": "g2"}])
    eng2 = FakeEngine("chain", raise_on=True)  # degrade
    eng3 = FakeEngine("metric", rows=[{"id": "m1"}])
    engines = {"graph": eng1, "chain": eng2, "metric": eng3}
    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q"}, "degrade"),
        ("chain", {"query": "q"}, "degrade"),
        ("metric", {"query": "q"}, "degrade"),
    ])
    result = await orch.orchestrate("ws-t038", components, merge="interleave")

    # chain degraded → 不参与 interleave；只有 graph + metric
    ids = [r["id"] for r in result["rows"]]
    assert ids == ["g1", "m1", "g2"], (
        f"interleave 应跳过 degraded 组件: {ids}"
    )


# ── T038-5: rank 所有 row 无 score → 保持原 concat 顺序 ──────────────────

@pytest.mark.asyncio
async def test_merge_rank_no_scores_preserves_order():
    """T038-5: rank 下所有 row 均无 score → 全部 0.0，保持原 concat 顺序（稳定排序）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.hybrid_orchestrator import (
        HybridOrchestrator,
    )

    eng1 = FakeEngine("graph", rows=[{"id": "g1"}, {"id": "g2"}])
    eng2 = FakeEngine("metric", rows=[{"id": "m1"}])
    engines = {"graph": eng1, "metric": eng2}
    orch = HybridOrchestrator(engines=engines)
    components = _make_components([
        ("graph", {"query": "q"}, "skip"),
        ("metric", {"query": "q"}, "skip"),
    ])
    result = await orch.orchestrate("ws-t038", components, merge="rank")

    ids = [r["id"] for r in result["rows"]]
    # 无 score → 全 0.0 → 稳定排序保持原 concat 顺序
    assert ids == ["g1", "g2", "m1"], (
        f"无 score rank 应保持原序: {ids}"
    )
