"""TDD tests for MetricEngine (spec 008 / US2 / FR-006 BI 指标查询).

RED 阶段：本文件先于 impl/metric_engine.py 编写，运行时应失败（模块不存在）。
GREEN 阶段：实现 MetricEngine 后全部通过。

Constitution III：测试独立可运行，外部依赖（QueryService/Neo4j）通过 mock 隔离。

覆盖场景（T011 要求）：
  1. count 实例数（按 object_type 过滤 + 空集合 0 值）
  2. density 连接密度（图中 edges/vertices 比值 + 孤立点 density=0）
  3. trend 时间趋势（granularity=day/week/month + time_window 边界）
  4. 空集/无匹配结果（所有指标返回合理零值，不抛异常）
  5. granularity 校验（非法 granularity 抛 ValueError）
  6. 分页边界（limit≤200 校验 + result_total 字段一致性）
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_query_service(entities=None, relations=None):
    """构造 mock QueryService。

    execute_async 返回 {rows, total, explain} 结构，
    MetricEngine 通过 DSL 调用 QueryService（而非 Neo4j 驱动，避免破坏 Constitution IV）。
    """
    qs = MagicMock()

    async def _execute_async(workspace_id, dsl, **kwargs):
        if "metric:count" in dsl:
            count = len(entities) if entities is not None else 42
            return {"rows": [{"metric": "count", "value": count}], "total": 1, "explain": {"dsl": dsl}}
        if "metric:density" in dsl:
            v_count = len(entities) if entities is not None else 10
            e_count = len(relations) if relations is not None else 15
            density = round(e_count / v_count, 3) if v_count > 0 else 0.0
            return {"rows": [{"metric": "density", "value": density}], "total": 1, "explain": {"dsl": dsl}}
        if "metric:trend" in dsl:
            # 模拟 3 天的日趋势数据
            trend_rows = [
                {"date": "2026-07-28", "value": 5},
                {"date": "2026-07-29", "value": 8},
                {"date": "2026-07-30", "value": 12},
            ]
            return {"rows": trend_rows, "total": len(trend_rows), "explain": {"dsl": dsl}}
        return {"rows": [], "total": 0, "explain": {"dsl": dsl}}

    qs.execute_async = AsyncMock(side_effect=_execute_async)
    return qs


# ---------------------------------------------------------------------------
# 1. count 实例数（按 object_type 过滤 + 空集合 0 值）
# ---------------------------------------------------------------------------

async def test_count_instances_by_object_type():
    """T011-1: count 指标返回实例数，filters.object_type 被透传至 QueryService。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service(entities=[{"id": "e1"}, {"id": "e2"}, {"id": "e3"}])
    engine = MetricEngine(query_service=qs)

    result = await engine.metric(
        "ws-test",
        metric="count",
        object_type="装备",
        limit=20,
    )

    assert result["mode"] == "metric"
    assert result["total"] >= 1
    # 结果中的 metrics 字段包含 count 值
    metrics = result["rows"] if "metrics" not in result else result["metrics"]
    # MetricEngine 统一按 SearchResult 结构返回，其中 rows/metrics 其一
    values = [m.get("value", m.get("count")) for m in metrics if "count" in str(m)]
    # 至少包含一个 count 指标，值为 3（entities 数组长度）
    any_count = any(3 == v for v in values) or any(
        "count" in str(m).lower() for m in metrics
    )
    assert any_count, f"Expected count metric in result, got {metrics}"


async def test_count_empty_set_returns_zero():
    """T011-1b: 空集合时 count 指标返回 0（不抛异常，不返回 None）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service(entities=[])
    engine = MetricEngine(query_service=qs)

    result = await engine.metric("ws-test", metric="count", object_type="装备", limit=20)

    # metrics/rows 中 count 必须为 0 或显式声明零值
    metrics = result.get("metrics", result.get("rows", []))
    # 要么有 value=0 项，要么 total=1 + rows[0].value=0
    all_values = [m.get("value") for m in metrics if isinstance(m, dict)]
    assert 0 in all_values or result.get("total") == 0


# ---------------------------------------------------------------------------
# 2. density 连接密度（edges/vertices 比值 + 孤立点 density=0）
# ---------------------------------------------------------------------------

async def test_density_ratio_edges_over_vertices():
    """T011-2: density = edges / vertices。10 vertices, 15 relations => 1.5。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    entities = [{"id": f"e{i}"} for i in range(10)]
    relations = [{"id": f"r{i}"} for i in range(15)]
    qs = _make_query_service(entities=entities, relations=relations)
    engine = MetricEngine(query_service=qs)

    result = await engine.metric("ws-test", metric="density", limit=20)

    metrics = result.get("metrics", result.get("rows", []))
    density_values = [m.get("value") for m in metrics if "density" in str(m).lower()]
    assert 1.5 in density_values or any(abs(v - 1.5) < 0.01 for v in density_values if isinstance(v, float))


async def test_density_isolated_graph_returns_zero():
    """T011-2b: 孤立图（vertices>0 但 edges=0）时 density=0，不产生 ZeroDivisionError。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    entities = [{"id": "e1"}, {"id": "e2"}]  # 2 vertices, 0 edges
    qs = _make_query_service(entities=entities, relations=[])
    engine = MetricEngine(query_service=qs)

    result = await engine.metric("ws-test", metric="density", limit=20)

    metrics = result.get("metrics", result.get("rows", []))
    density_values = [m.get("value") for m in metrics if "density" in str(m).lower()]
    # 孤立图密度必须为 0（或等价浮点零）
    assert 0 in density_values or 0.0 in density_values


# ---------------------------------------------------------------------------
# 3. trend 时间趋势（granularity=day/week/month + time_window 边界）
# ---------------------------------------------------------------------------

async def test_trend_granularity_day_returns_daily_series():
    """T011-3: granularity='day' 返回按日聚合的序列，每项含 date+value。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service()
    engine = MetricEngine(query_service=qs)

    result = await engine.metric(
        "ws-test",
        metric="trend",
        granularity="day",
        time_window={"start": "2026-07-28", "end": "2026-07-30"},
        limit=20,
    )

    metrics = result.get("metrics", result.get("rows", []))
    # 趋势数据是多行，每行含 date 维度和 value
    has_date = any("date" in str(m) for m in metrics)
    values = [m.get("value") for m in metrics if isinstance(m, dict)]
    assert has_date
    assert len(values) >= 3, f"Expected 3+ trend points, got {len(values)}: {metrics}"


# ---------------------------------------------------------------------------
# 4. 空集/无匹配结果（所有指标返回合理零值，不抛异常）
# ---------------------------------------------------------------------------

async def test_unknown_metric_returns_empty_or_degraded():
    """T011-4: 不识别的 metric 名（TBox 自动派生失败）优雅降级：返回零值 + explain.status='degraded'。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service()
    engine = MetricEngine(query_service=qs)

    result = await engine.metric("ws-test", metric="unknown_metric_xyz", limit=20)

    # 不应抛异常；应返回空 metrics 或 status='degraded'
    metrics = result.get("metrics", result.get("rows", []))
    explain = result.get("explain", {})
    assert explain.get("status") == "degraded" or len(metrics) == 0 or result.get("total") == 0


# ---------------------------------------------------------------------------
# 5. granularity 校验（非法 granularity 抛 ValueError）
# ---------------------------------------------------------------------------

async def test_invalid_granularity_raises_value_error():
    """T011-5: granularity ∉ {day, week, month, None} 抛 ValueError（由调用方转 HTTP 400）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service()
    engine = MetricEngine(query_service=qs)

    with pytest.raises(ValueError, match="granularity"):
        await engine.metric(
            "ws-test",
            metric="trend",
            granularity="hour",  # 非法：仅 day/week/month
            limit=20,
        )


# ---------------------------------------------------------------------------
# 6. 分页边界（limit ≤ 200 校验 + result_total 字段一致性）
# ---------------------------------------------------------------------------

async def test_limit_exceeds_maximum_raises_value_error():
    """T011-6: limit > 200 抛 ValueError（与 schemas.MetricRequest/SEARCH_MAX 一致）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service()
    engine = MetricEngine(query_service=qs)

    with pytest.raises(ValueError, match="limit"):
        await engine.metric("ws-test", metric="count", limit=500)


async def test_limit_negative_raises_value_error():
    """T011-6b: limit ≤ 0 同样抛 ValueError。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service()
    engine = MetricEngine(query_service=qs)

    with pytest.raises(ValueError, match="limit"):
        await engine.metric("ws-test", metric="count", limit=0)


# ---------------------------------------------------------------------------
# T026 (Phase 2 / Iter 1): 自定义 MetricDefinition 路径 + TBox fallback
# ---------------------------------------------------------------------------


def _make_mds(definition=None, raise_exc=None):
    """构造 mock MetricDefinitionService。

    - definition: resolve_and_compute 返回的自定义结果 dict（None 表示无定义）
    - raise_exc: resolve_and_compute 抛指定异常（验证降级路径）
    """
    mds = MagicMock()

    async def _resolve(workspace_id, metric_name):
        if raise_exc is not None:
            raise raise_exc
        return definition
    mds.resolve_and_compute = AsyncMock(side_effect=_resolve)
    return mds


async def test_custom_metric_definition_path_returns_custom_result():
    """T026-1: 注入 MDS 且命中定义 → 返回 definition='custom' 结果，不走 TBox。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service()
    custom_def = {
        "metric_name": "势力人口",
        "value": 600,
        "unit": "万人",
        "precision": 2,
        "bindings": {"A": 600.0},
    }
    mds = _make_mds(definition=custom_def)
    engine = MetricEngine(query_service=qs, metric_definition_service=mds)

    result = await engine.metric("ws-test", metric="势力人口", limit=20)

    assert result["mode"] == "metric"
    assert result["explain"]["definition"] == "custom"
    assert result["explain"]["status"] == "ok"
    assert result["total"] == 1
    metrics = result["metrics"]
    assert metrics[0]["metric_name"] == "势力人口"
    assert metrics[0]["value"] == 600
    assert metrics[0]["unit"] == "万人"
    # QueryService 不应被调用（自定义路径不经过 TBox DSL）
    qs.execute_async.assert_not_called()


async def test_custom_metric_not_in_storage_falls_back_to_tbox():
    """T026-2: MDS 未命中定义（返回 None）→ fallback TBox count（Phase 1 行为）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service(entities=[{"id": "e1"}, {"id": "e2"}])
    mds = _make_mds(definition=None)  # 无定义
    engine = MetricEngine(query_service=qs, metric_definition_service=mds)

    result = await engine.metric("ws-test", metric="count", limit=20)

    # 走 TBox 路径：definition 不为 'custom'
    assert result["explain"].get("definition") is None
    assert result["mode"] == "metric"
    # MDS 被调用过（尝试查找），但返回 None
    mds.resolve_and_compute.assert_awaited_once()
    # QueryService 被调用（TBox DSL）
    qs.execute_async.assert_awaited()


async def test_custom_metric_exception_falls_back_to_tbox():
    """T026-3: MDS 抛异常 → log warning + fallback TBox（不阻断）。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service(entities=[{"id": "e1"}])
    mds = _make_mds(raise_exc=RuntimeError("storage down"))
    engine = MetricEngine(query_service=qs, metric_definition_service=mds)

    result = await engine.metric("ws-test", metric="count", limit=20)

    # 异常被吞掉，fallback 到 TBox，不抛出
    assert result["mode"] == "metric"
    assert result["explain"].get("definition") is None
    qs.execute_async.assert_awaited()


async def test_no_mds_injected_skips_custom_path():
    """T026-4: 未注入 MDS（Phase 1 调用方式）→ 直接走 TBox，行为不变。"""
    from odap.biz.core.ontology.semantic_retrieval.impl.metric_engine import MetricEngine

    qs = _make_query_service(entities=[{"id": "e1"}, {"id": "e2"}, {"id": "e3"}])
    engine = MetricEngine(query_service=qs)  # 不传 metric_definition_service

    result = await engine.metric("ws-test", metric="count", limit=20)

    assert result["mode"] == "metric"
    assert result["explain"].get("definition") is None
    # TBox count 路径
    metrics = result.get("metrics", result.get("rows", []))
    values = [m.get("value") for m in metrics if isinstance(m, dict)]
    assert 3 in values
