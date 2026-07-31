"""SC-002 性能基准：BI 工具指标查询 P95 在 5s 内 (spec 008 / SC-002)。

Success Criteria:
  SC-002: BI 工具的指标查询 P95 响应时间在 5 秒以内（10 万级实例聚合）

框架验证模式：
  · 当前在空/降级 Neo4j 上运行 — 验证框架可用性 + P95 断言逻辑
  · 真实 SC-002 验收需 10 万级实例 Neo4j 测试集（Phase 7+ 生产环境验证）
  · 运行方式：pytest -m perf apps/api/tests/performance/test_sc002_metric_latency.py

测试策略：
  · 用 real RetrievalService.metric_search（count/density/trend 三类指标）
  · 10 个指标查询（覆盖 3 种 metric_type + object_type 过滤 + granularity）
  · 逐条计时 → 计算 P95 → 断言 ≤ 5.0s
  · MetricEngine 不直连 Neo4j（TBox 派生），延迟应远低于 graph/nl
"""

from __future__ import annotations

import logging
import time
from typing import List

import pytest

from odap.biz.core.ontology.semantic_retrieval.services.retrieval_service import (
    RetrievalService,
)

logger = logging.getLogger("semantic_retrieval.perf.sc002")

# SC-002 阈值：P95 5 秒
SC002_LATENCY_THRESHOLD_S = 5.0
SC002_PERCENTILE = 95

# 10 个指标查询样本（count/density/trend 交替 + 不同 object_type/granularity）
SC002_SAMPLE_METRICS = [
    ("count", None, None),
    ("count", "装备", None),
    ("count", "系统", None),
    ("density", None, None),
    ("density", "装备", None),
    ("trend", None, "day"),
    ("trend", "装备", "day"),
    ("trend", "系统", "week"),
    ("trend", None, "month"),
    ("count", "平台", None),
]


def _percentile(data: List[float], pct: float) -> float:
    """线性插值法计算百分位数（无 numpy 依赖）。"""
    if not data:
        return float("inf")
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * pct / 100.0
    f = int(k)
    c = k - f
    if f + 1 < len(sorted_data):
        return sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f])
    return float(sorted_data[f])


@pytest.fixture(scope="module")
def retrieval_service() -> RetrievalService:
    """共享 RetrievalService 实例（避免每测试重复初始化 ~10s OPA/registry）。"""
    return RetrievalService()


# ── SC-002: P95 指标查询延迟 ≤ 5s ─────────────────────────────────────────

@pytest.mark.perf
@pytest.mark.asyncio
async def test_sc002_p95_metric_query_latency_under_5s(
    retrieval_service: RetrievalService,
):
    """SC-002: BI 工具指标查询 P95 响应时间在 5 秒以内。

    框架验证模式 — 空数据集上 P95 应远低于 5s（MetricEngine 不连 Neo4j）。
    真实 SC 验收需 10 万级实例 Neo4j 测试集。
    """
    svc = retrieval_service
    latencies: List[float] = []

    for metric, obj_type, granularity in SC002_SAMPLE_METRICS:
        t0 = time.perf_counter()
        result = await svc.metric_search(
            "ws-perf-sc002",
            metric,
            object_type=obj_type,
            granularity=granularity,
            limit=20,
        )
        t1 = time.perf_counter()
        latencies.append(t1 - t0)
        # 每次查询必须返回结构化结果
        assert result is not None, f"metric={metric} 返回 None"
        assert result.get("mode") == "metric", f"metric={metric} mode 非 metric"
        assert "total" in result, f"metric={metric} 缺 total"

    p95 = _percentile(latencies, SC002_PERCENTILE)
    p50 = _percentile(latencies, 50)
    max_lat = max(latencies)

    logger.info(
        "SC-002 基准完成: samples=%d P50=%.3fs P95=%.3fs max=%.3fs threshold=%.1fs",
        len(latencies), p50, p95, max_lat, SC002_LATENCY_THRESHOLD_S,
    )

    assert p95 <= SC002_LATENCY_THRESHOLD_S, (
        f"SC-002 不达标: P95={p95:.3fs}s > {SC002_LATENCY_THRESHOLD_S}s "
        f"(samples={len(latencies)}, max={max_lat:.3f}s)"
    )


# ── SC-002: 每次指标查询返回有效结构 ──────────────────────────────────────

@pytest.mark.perf
@pytest.mark.asyncio
async def test_sc002_all_metric_queries_return_valid_structure(
    retrieval_service: RetrievalService,
):
    """SC-002 补充：所有指标查询样本返回有效结构（mode/total/metrics/rows）。"""
    svc = retrieval_service
    for metric, obj_type, granularity in SC002_SAMPLE_METRICS:
        result = await svc.metric_search(
            "ws-perf-sc002",
            metric,
            object_type=obj_type,
            granularity=granularity,
            limit=20,
        )
        assert result["mode"] == "metric"
        assert isinstance(result["total"], int)
        assert isinstance(result.get("metrics", []), list), (
            f"metric={metric} metrics 非列表"
        )
        assert isinstance(result.get("rows", []), list), (
            f"metric={metric} rows 非列表"
        )
        assert "explain" in result, f"metric={metric} 缺 explain"
