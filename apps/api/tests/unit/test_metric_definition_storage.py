"""T023 MetricDefinitionStorage — TDD 测试 (spec 008 Phase 2 / Iter 1).

验证 MetricDefinition 的 SQLite 持久化层：
- 幂等 DDL（CREATE TABLE IF NOT EXISTS）
- CRUD：save / get / get_by_name / list / delete
- JSON 字段（bindings / tags）序列化
- UNIQUE 约束（metric_id 主键 + name 唯一）
- tmp_path 真实 SQLite（AGENTS.md 测试规则）

参考模式：sqlite_usl_storage.py（_get_conn WAL + 每次 connect/close）。
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.design.model.models.metric import (
    AggregationFunction,
    MetricBinding,
    MetricDefinition,
)
from odap.biz.core.ontology.semantic_retrieval.storage.metric_definition_storage import (
    MetricDefinitionStorage,
)


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def storage(tmp_path):
    """tmp_path 真实 SQLite（AGENTS.md：测试用真实 DB，不 mock）。"""
    return MetricDefinitionStorage(db_path=str(tmp_path / "metric_defs.db"))


@pytest.fixture
def sample_definition():
    """势力人口指标 = SUM(binding.population) + AVG(binding.area) * 0.5"""
    return MetricDefinition(
        metric_id="metric_faction_pop",
        name="势力人口",
        name_en="FactionPopulation",
        description="各势力的总人口聚合",
        domain="military",
        tags=["人口", "势力"],
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
        unit="万人",
        precision=2,
    )


# ── T023-1: 幂等初始化 ────────────────────────────────────────────────────


def test_init_db_idempotent(storage, tmp_path):
    """重复初始化不报错（CREATE TABLE IF NOT EXISTS 幂等）。"""
    # 再次用同一路径构造 — 不应抛异常
    MetricDefinitionStorage(db_path=str(tmp_path / "metric_defs.db"))


# ── T023-2: save + get 圆环 ────────────────────────────────────────────────


def test_save_and_get_by_id(storage, sample_definition):
    """save 后能按 metric_id 取回完整定义。"""
    storage.save(sample_definition)
    got = storage.get(sample_definition.metric_id)
    assert got is not None
    assert got["metric_id"] == "metric_faction_pop"
    assert got["name"] == "势力人口"
    assert got["unit"] == "万人"


def test_get_nonexistent_returns_none(storage):
    """不存在的 metric_id → None。"""
    assert storage.get("no_such_metric") is None


# ── T023-3: get_by_name ────────────────────────────────────────────────────


def test_get_by_name(storage, sample_definition):
    """按 name 唯一查找。"""
    storage.save(sample_definition)
    got = storage.get_by_name("势力人口")
    assert got is not None
    assert got["metric_id"] == "metric_faction_pop"


def test_get_by_name_nonexistent_returns_none(storage):
    assert storage.get_by_name("不存在指标") is None


# ── T023-4: JSON 字段序列化（bindings / tags）────────────────────────────


def test_json_fields_roundtrip(storage, sample_definition):
    """bindings（list[MetricBinding]）与 tags（list[str]）序列化往返。"""
    storage.save(sample_definition)
    got = storage.get(sample_definition.metric_id)
    assert len(got["bindings"]) == 2
    assert got["bindings"][0]["source_entity_type_id"] == "Faction"
    assert got["bindings"][0]["aggregation"] == "sum"  # Enum → .value
    assert got["bindings"][0]["alias"] == "A"
    assert got["tags"] == ["人口", "势力"]


# ── T023-5: list 分页 + domain 过滤 ───────────────────────────────────────


def test_list_with_domain_filter(storage, sample_definition):
    """list 支持 domain 过滤 + 分页。"""
    storage.save(sample_definition)
    # 另一个不同 domain 的指标
    other = MetricDefinition(
        metric_id="metric_revenue",
        name="税收",
        domain="economy",
        bindings=[
            MetricBinding(
                source_entity_type_id="City",
                source_property_id="tax",
                aggregation=AggregationFunction.SUM,
                alias="A",
            )
        ],
    )
    storage.save(other)

    all_defs, total = storage.list(page=1, page_size=10)
    assert total == 2

    military_only, mil_total = storage.list(domain="military", page=1, page_size=10)
    assert mil_total == 1
    assert military_only[0]["name"] == "势力人口"


# ── T023-6: save 幂等 upsert（同 metric_id 覆盖）─────────────────────────


def test_save_upsert_overwrites(storage, sample_definition):
    """同 metric_id 再次 save → 覆盖而非插入第二条。"""
    storage.save(sample_definition)
    updated = sample_definition.model_copy(update={"description": "更新后的描述"})
    storage.save(updated)

    got = storage.get(sample_definition.metric_id)
    assert got["description"] == "更新后的描述"

    _, total = storage.list(page=1, page_size=10)
    assert total == 1  # 仍是 1 条，未重复插入


# ── T023-7: delete ─────────────────────────────────────────────────────────


def test_delete_returns_true_and_removes(storage, sample_definition):
    """delete 已存在 → True；再查 → None。"""
    storage.save(sample_definition)
    assert storage.delete(sample_definition.metric_id) is True
    assert storage.get(sample_definition.metric_id) is None


def test_delete_nonexistent_returns_false(storage):
    """delete 不存在 → False（不抛异常）。"""
    assert storage.delete("no_such_metric") is False
