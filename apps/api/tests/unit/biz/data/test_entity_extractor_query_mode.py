"""TDD：EntityExtractor 三模式（off/inject/query）+ 生产接线（子项目 C E-5/E-6/E-18/E-19）。

边界桩：SemanticsProvider（query 模式的本体查询）用 fake 注入；其余（模式分派、
缓存、降级、off/inject 分支）走真实函数体（规则 14.6）。
"""
from __future__ import annotations

import pytest

from odap.biz.data.qa.pipeline.understanding import intent_recognizer as ir
from odap.biz.data.qa.pipeline.understanding import extractor_mode as em
from odap.biz.data.qa.pipeline.understanding.intent_recognizer import (
    EntityExtractor,
    UnderstandingStage,
    SemanticsProvider,
)


@pytest.fixture(autouse=True)
def _silence_gap(monkeypatch):
    """拦截缺口信号，避免测试污染默认 DB。"""
    calls = []
    import odap.biz.semantic_admin.gap_pool.services.gap_emitter as ge
    monkeypatch.setattr(ge, "report_gap_signal",
                        lambda *a, **kw: calls.append((a, kw)))
    return calls


class _FakeProvider:
    def __init__(self, mapping=None, boom=False):
        self._mapping = mapping or {}
        self._boom = boom
        self.calls = []

    def query(self, expression, domain_id="", kinds=("content",)):
        self.calls.append((expression, domain_id))
        if self._boom:
            raise RuntimeError("tool down")
        canonical = self._mapping.get(expression)
        return {"content": {"canonical": canonical}}


def test_off_mode_passthrough():
    ex = EntityExtractor()
    ex.set_entity_context(mode="off")
    # 「司马懿」引号提取 → 原词直通
    assert ex.extract("「司马懿」是谁") == ["司马懿"]
    assert ex.mode == "off"


def test_query_mode_returns_canonical_from_provider():
    provider = _FakeProvider(mapping={"司马懿": "人物"})
    ex = EntityExtractor()
    ex.set_entity_context(mode="query", semantics_provider=provider)
    assert ex.extract("「司马懿」是谁") == ["人物"]
    assert ex.mode == "query"


def test_query_mode_cache_hit_avoids_repeat_query():
    provider = _FakeProvider(mapping={"司马懿": "人物"})
    ex = EntityExtractor()
    ex.set_entity_context(mode="query", semantics_provider=provider)
    ex.extract("「司马懿」与「司马懿」")
    # 同一 entity 在同一 extract 内应只查询一次
    assert [c[0] for c in provider.calls].count("司马懿") == 1


def test_query_mode_provider_failure_falls_back_to_raw():
    provider = _FakeProvider(boom=True)
    ex = EntityExtractor()
    ex.set_entity_context(mode="query", semantics_provider=provider)
    # 工具失败 → 原词兜底，不抛
    assert ex.extract("「未知词」") == ["未知词"]


def test_query_mode_unknown_emits_gap_and_filters(_silence_gap):
    provider = _FakeProvider(mapping={})   # 全部未命中
    ex = EntityExtractor()
    ex.set_entity_context(mode="query", semantics_provider=provider)
    assert ex.extract("「未收词」") == []    # 未命中 canonical → 过滤
    assert _silence_gap                     # 触发了缺口信号


def test_inject_mode_still_filters_by_entity_set():
    class _Resolver:
        def resolve(self, entity, domain_id=""):
            return entity

    ex = EntityExtractor()
    ex.set_entity_context(term_resolver=_Resolver(), entity_set={"人物"}, mode="inject")
    # 司马懿 不在 entity_set → 过滤
    assert ex.extract("「司马懿」") == []
    assert ex.mode == "inject"


def test_understanding_stage_wires_mode(monkeypatch):
    monkeypatch.setattr(em, "_read_from_sa_config", lambda: "query")
    monkeypatch.delenv("EXTRACTOR_MODE", raising=False)
    stage = UnderstandingStage(llm_client=None)
    assert stage.entity_extractor.mode == "query"


def test_semantics_provider_default_is_callable():
    # 默认 provider 可构造（真实 USL，可能不可用 → 返回 None canonical，不抛）
    p = SemanticsProvider()
    out = p.query("不存在的词xyz", domain_id="")
    assert "content" in out


def test_cost_audit_recorded_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("COST_AUDIT_ENABLED", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    provider = _FakeProvider(mapping={"司马懿": "人物"})
    ex = EntityExtractor()
    ex.set_entity_context(mode="query", semantics_provider=provider)
    ex.extract("「司马懿」")
    from odap.biz.data.qa.evaluation.cost_audit import CostAuditStorage
    recs = CostAuditStorage(db_path=str(tmp_path / "cost_audit.db")).list_records(
        call_kind="entity_extract")
    assert len(recs) >= 1
    assert recs[0]["mode"] == "query"

