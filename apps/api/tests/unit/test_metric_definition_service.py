"""T024 MetricDefinitionService — TDD 测试 (spec 008 Phase 2 / Iter 1).

验证按 MetricDefinition 的 bindings + formula 计算自定义指标：
- 按 binding.source_entity_type_id + source_property_id 调 QueryService 取属性值
- 按 aggregation（COUNT/SUM/AVG/MIN/MAX/COUNT_DISTINCT/RATIO）聚合
- formula 非空时按 alias 引用 binding 结果安全求值（ast，禁止 eval）
- 无 formula 时返回单 binding 的聚合值
- 空结果集返回 0（不除零）
- 无 MetricDefinition 时返回 None（供 MetricEngine fallback TBox）
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest import mock

import pytest

from odap.biz.core.ontology.design.model.models.metric import (
    AggregationFunction,
    MetricBinding,
    MetricDefinition,
)
from odap.biz.core.ontology.semantic_retrieval.services.metric_definition_service import (
    MetricDefinitionService,
)


# ── fakes ─────────────────────────────────────────────────────────────────


class FakeQueryService:
    """按 source_entity_type_id 返回预设属性值 rows。"""

    def __init__(self, by_type: Dict[str, List[Dict[str, Any]]]):
        self._by_type = by_type
        self.calls: List[str] = []

    async def execute_async(self, workspace_id: str, query: str, limit: int = 20):
        self.calls.append(query)
        # 解析 query 中的 type: 过滤器（DSL: .entity type:Faction）
        etype = self._extract_type(query)
        rows = self._by_type.get(etype, [])
        return _FakeResult(rows=rows, total=len(rows), explain={"source": "entity"})

    @staticmethod
    def _extract_type(query: str) -> str:
        for tok in query.split():
            if tok.startswith("type:"):
                return tok[5:]
        return ""


class _FakeResult:
    def __init__(self, rows, total, explain):
        self.rows = rows
        self.total = total
        self.explain = explain


class FakeStorage:
    """内存 storage：按 name 查找 MetricDefinition dict。"""

    def __init__(self, defs: Dict[str, Dict[str, Any]]):
        self._defs = defs

    def get_by_name(self, name: str):
        return self._defs.get(name)


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def faction_rows():
    return [
        {"entity_type": "Faction", "population": 100, "area": 50.0},
        {"entity_type": "Faction", "population": 200, "area": 70.0},
        {"entity_type": "Faction", "population": 300, "area": 90.0},
    ]


@pytest.fixture
def pop_metric():
    """势力人口 = SUM(population)。无 formula。"""
    return MetricDefinition(
        metric_id="m1",
        name="势力人口",
        bindings=[
            MetricBinding(
                source_entity_type_id="Faction",
                source_property_id="population",
                aggregation=AggregationFunction.SUM,
                alias="A",
            )
        ],
        unit="万人",
        precision=2,
    )


# ── T024-1: SUM 聚合（无 formula）────────────────────────────────────────


@pytest.mark.asyncio
async def test_sum_aggregation_without_formula(faction_rows, pop_metric):
    qs = FakeQueryService({"Faction": faction_rows})
    svc = MetricDefinitionService(query_service=qs, storage=FakeStorage({}))
    result = await svc.compute("ws-1", pop_metric.model_dump(mode="json"))
    assert result is not None
    assert result["metric_name"] == "势力人口"
    assert result["value"] == 600  # 100+200+300
    assert result["unit"] == "万人"


# ── T024-2: formula 引用多 binding alias ──────────────────────────────────


@pytest.mark.asyncio
async def test_formula_with_multiple_bindings(faction_rows):
    """指标 = SUM(population) + AVG(area) * 0.5 → 600 + 70*0.5 = 635"""
    metric = MetricDefinition(
        metric_id="m2",
        name="综合指数",
        bindings=[
            MetricBinding(
                source_entity_type_id="Faction",
                source_property_id="population",
                aggregation=AggregationFunction.SUM,
                alias="A",
            ),
            MetricBinding(
                source_entity_type_id="Faction",
                source_property_id="area",
                aggregation=AggregationFunction.AVG,
                alias="B",
            ),
        ],
        formula="A + B * 0.5",
        unit="指数",
        precision=2,
    )
    qs = FakeQueryService({"Faction": faction_rows})
    svc = MetricDefinitionService(query_service=qs, storage=FakeStorage({}))
    result = await svc.compute("ws-1", metric.model_dump(mode="json"))
    assert result is not None
    assert result["value"] == pytest.approx(635.0, rel=1e-6)


# ── T024-3: COUNT / AVG / MIN / MAX / COUNT_DISTINCT ──────────────────────


@pytest.mark.asyncio
async def test_count_aggregation(faction_rows):
    metric = MetricDefinition(
        metric_id="m3",
        name="势力数量",
        bindings=[
            MetricBinding(
                source_entity_type_id="Faction",
                source_property_id="population",
                aggregation=AggregationFunction.COUNT,
                alias="A",
            )
        ],
    )
    qs = FakeQueryService({"Faction": faction_rows})
    svc = MetricDefinitionService(query_service=qs, storage=FakeStorage({}))
    result = await svc.compute("ws-1", metric.model_dump(mode="json"))
    assert result["value"] == 3


@pytest.mark.asyncio
async def test_avg_min_max_aggregation(faction_rows):
    for agg, expected in [
        (AggregationFunction.AVG, 200.0),  # (100+200+300)/3
        (AggregationFunction.MIN, 100),
        (AggregationFunction.MAX, 300),
        (AggregationFunction.COUNT_DISTINCT, 3),  # 3 distinct values
    ]:
        metric = MetricDefinition(
            metric_id=f"m_{agg.value}",
            name=f"test_{agg.value}",
            bindings=[
                MetricBinding(
                    source_entity_type_id="Faction",
                    source_property_id="population",
                    aggregation=agg,
                    alias="A",
                )
            ],
        )
        qs = FakeQueryService({"Faction": faction_rows})
        svc = MetricDefinitionService(query_service=qs, storage=FakeStorage({}))
        result = await svc.compute("ws-1", metric.model_dump(mode="json"))
        assert result["value"] == expected, f"{agg.value} 期望 {expected}, 实际 {result['value']}"


# ── T024-4: 空结果集返回 0（不除零）──────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_rows_returns_zero_without_division_error():
    metric = MetricDefinition(
        metric_id="m_empty",
        name="空集指标",
        bindings=[
            MetricBinding(
                source_entity_type_id="Ghost",
                source_property_id="value",
                aggregation=AggregationFunction.AVG,
                alias="A",
            )
        ],
    )
    qs = FakeQueryService({"Ghost": []})  # 无实体
    svc = MetricDefinitionService(query_service=qs, storage=FakeStorage({}))
    result = await svc.compute("ws-1", metric.model_dump(mode="json"))
    assert result is not None
    assert result["value"] == 0  # 不抛 ZeroDivisionError


# ── T024-5: RATIO 聚合（两 binding 相除）──────────────────────────────────


@pytest.mark.asyncio
async def test_ratio_aggregation_via_formula(faction_rows):
    """密度 = SUM(population) / SUM(area) → 600 / 210 ≈ 2.857"""
    metric = MetricDefinition(
        metric_id="m_ratio",
        name="人口密度",
        bindings=[
            MetricBinding(
                source_entity_type_id="Faction",
                source_property_id="population",
                aggregation=AggregationFunction.SUM,
                alias="A",
            ),
            MetricBinding(
                source_entity_type_id="Faction",
                source_property_id="area",
                aggregation=AggregationFunction.SUM,
                alias="B",
            ),
        ],
        formula="A / B",
        precision=3,
    )
    qs = FakeQueryService({"Faction": faction_rows})
    svc = MetricDefinitionService(query_service=qs, storage=FakeStorage({}))
    result = await svc.compute("ws-1", metric.model_dump(mode="json"))
    assert result["value"] == pytest.approx(600 / 210, rel=1e-6)


# ── T024-6: formula 安全求值（禁止 eval 危险调用）───────────────────────


@pytest.mark.asyncio
async def test_formula_rejects_dangerous_expressions(faction_rows):
    """formula 含 __import__ / open / eval 等调用 → 应拒绝（不执行）。"""
    metric = MetricDefinition(
        metric_id="m_evil",
        name="恶意指标",
        bindings=[
            MetricBinding(
                source_entity_type_id="Faction",
                source_property_id="population",
                aggregation=AggregationFunction.SUM,
                alias="A",
            )
        ],
        formula="__import__('os').system('echo pwned')",
    )
    qs = FakeQueryService({"Faction": faction_rows})
    svc = MetricDefinitionService(query_service=qs, storage=FakeStorage({}))
    result = await svc.compute("ws-1", metric.model_dump(mode="json"))
    # 危险 formula 被拒 → 降级返回 binding 原始值（A=600），不执行系统命令
    assert result is not None
    assert result["value"] == 600  # fallback 到 binding A


# ── T024-7: 按名加载定义 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_by_name_from_storage(faction_rows, pop_metric):
    """resolve_and_compute 按名从 storage 加载并计算。"""
    storage = FakeStorage({"势力人口": pop_metric.model_dump(mode="json")})
    qs = FakeQueryService({"Faction": faction_rows})
    svc = MetricDefinitionService(query_service=qs, storage=storage)
    result = await svc.resolve_and_compute("ws-1", "势力人口")
    assert result is not None
    assert result["value"] == 600


@pytest.mark.asyncio
async def test_resolve_nonexistent_returns_none():
    """无定义 → None（供 MetricEngine fallback TBox）。"""
    qs = FakeQueryService({})
    svc = MetricDefinitionService(query_service=qs, storage=FakeStorage({}))
    result = await svc.resolve_and_compute("ws-1", "不存在指标")
    assert result is None


# ── T024-8: filter_condition 透传到 DSL ────────────────────────────────────


@pytest.mark.asyncio
async def test_filter_condition_added_to_dsl(faction_rows):
    """binding.filter_condition 应追加到查询 DSL（如 status=='active'）。"""
    metric = MetricDefinition(
        metric_id="m_filter",
        name="活跃势力人口",
        bindings=[
            MetricBinding(
                source_entity_type_id="Faction",
                source_property_id="population",
                aggregation=AggregationFunction.SUM,
                alias="A",
                filter_condition='status == "active"',
            )
        ],
    )
    qs = FakeQueryService({"Faction": faction_rows})
    svc = MetricDefinitionService(query_service=qs, storage=FakeStorage({}))
    await svc.compute("ws-1", metric.model_dump(mode="json"))
    # DSL 应包含 type:Faction 和 filter 条件
    assert any("type:Faction" in c for c in qs.calls), qs.calls
    assert any("status" in c for c in qs.calls), qs.calls
