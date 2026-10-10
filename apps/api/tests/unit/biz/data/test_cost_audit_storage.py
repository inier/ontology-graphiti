"""TDD：cost_audit 不可变成本对账存储（子项目 C E-8）。"""
from __future__ import annotations

from odap.biz.data.qa.evaluation.cost_audit import CostAuditStorage


def _store(tmp_path):
    return CostAuditStorage(db_path=str(tmp_path / "cost_audit.db"))


def test_record_and_list(tmp_path):
    s = _store(tmp_path)
    s.record(call_kind="ontology_semantics", mode="query", scope_key="ws::d1",
             expression="司马懿", cost={"round_trips": 1, "wall_ms": 12.5})
    recs = s.list_records()
    assert len(recs) == 1
    assert recs[0]["cost"]["wall_ms"] == 12.5
    assert recs[0]["mode"] == "query"


def test_aggregate_by_mode(tmp_path):
    s = _store(tmp_path)
    for w in (10.0, 20.0, 30.0):
        s.record(call_kind="entity_extract", mode="query", scope_key="ws::d1",
                 cost={"round_trips": 1, "wall_ms": w})
    s.record(call_kind="entity_extract", mode="inject", scope_key="ws::d1",
             cost={"round_trips": 0, "wall_ms": 2.0})
    agg = s.aggregate(call_kind="entity_extract")
    assert agg["query"]["count"] == 3
    assert agg["query"]["median_wall_ms"] == 20.0
    assert agg["query"]["total_round_trips"] == 3
    assert agg["inject"]["count"] == 1
    assert agg["inject"]["total_round_trips"] == 0


def test_append_only_no_update(tmp_path):
    # 表只 INSERT：record 两次同内容得到两行，无去重/覆盖
    s = _store(tmp_path)
    for _ in range(2):
        s.record(call_kind="ontology_semantics", mode="query", scope_key="ws",
                 expression="x", cost={})
    assert len(s.list_records()) == 2


def test_filter_by_scope(tmp_path):
    s = _store(tmp_path)
    s.record(call_kind="ontology_semantics", mode="query", scope_key="a", cost={})
    s.record(call_kind="ontology_semantics", mode="query", scope_key="b", cost={})
    assert len(s.list_records(scope_key="a")) == 1
