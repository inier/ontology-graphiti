"""子项目 A：gap_pool 归因分层 —— emitter/接线/服务层测试（真实函数体，规则 14.6）。

capture fixture 与 test_gap_wiring.py 同范式：只替换 emitter 的落库 sink，
宿主分支（canonical_of / _resolve_term / extract / ask）走真实实现体。
服务层测试用真 SQLiteGapStorage（tmp_path），断言 attribution 落库与 stats.by_layer。
"""
import pytest
from odap.biz.semantic_admin.gap_pool.models import GapLayer, GapSignalSource
from odap.biz.semantic_admin.gap_pool.services import gap_emitter
from odap.biz.semantic_admin.gap_pool.services.gap_service import GapService
from odap.biz.semantic_admin.gap_pool.storage import SQLiteGapStorage
from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import UslTermResolver


@pytest.fixture(autouse=True)
def capture_signals(monkeypatch):
    """把 emitter 的落库替换为内存收集，隔离 DB，但调用点走真实分支。"""
    calls = []

    def fake_report(source, expression, **kw):
        calls.append((str(source), expression, kw))

    monkeypatch.setattr(gap_emitter, "report_gap_signal", fake_report)
    return calls


_REAL_REPORT = gap_emitter.report_gap_signal   # 模块导入时留存真实函数体


@pytest.fixture
def real_store(tmp_path, monkeypatch):
    """还原真实 emitter 并注入 tmp DB 的 GapService，走 emitter→service→storage 真链路。"""
    monkeypatch.setattr(gap_emitter, "report_gap_signal", _REAL_REPORT)
    store = SQLiteGapStorage(db_path=str(tmp_path / "concept_gaps.db"))
    svc = GapService(storage=store)
    monkeypatch.setattr(gap_emitter, "_service_singleton", svc)
    return store


def _find(calls, source):
    return [kw for s, _e, kw in calls if s == source]


# ── 接线点 1: usl_term_resolver（content / term） ────────────────────────

def test_term_resolver_miss_carries_content_attribution(capture_signals):
    r = UslTermResolver()
    r.load_terms("d1", [{"canonical": "势力", "synonyms": [],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False}])
    assert r.canonical_of("诸侯", "d1") is None
    kws = _find(capture_signals, "term_resolve_miss")
    assert kws, "未命中应发 term_resolve_miss 信号"
    attr = kws[0].get("attribution")
    assert attr is not None
    assert attr["layer"] == GapLayer.CONTENT.value
    assert attr["target_kind"] == "term"
    assert attr["target_ref"] == "诸侯"


def test_term_resolver_no_domain_branch_also_attributed(capture_signals):
    """无 domain_id 分支（usl_term_resolver.py 第二个发射点）同样带归因。"""
    r = UslTermResolver()
    r.load_terms("d1", [{"canonical": "势力", "synonyms": [],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False}])
    assert r.canonical_of("诸侯") is None
    kws = _find(capture_signals, "term_resolve_miss")
    assert kws and kws[0]["attribution"]["layer"] == "content"


# ── 接线点 2: nl_engine（tool / engine） ────────────────────────────────

def test_nl_engine_miss_carries_tool_attribution(capture_signals):
    from odap.biz.core.ontology.semantic_retrieval.impl.nl_engine import NLEngine

    class _StubUsl:
        def list_terms(self, *, synonym_keyword=None, page_size=5, **kw):
            return [], 0

    eng = NLEngine(usl_manager=_StubUsl())
    assert eng._resolve_term("诸侯", _StubUsl()) is None
    kws = _find(capture_signals, "nl_query_unanswered")
    assert kws, "USL 未命中应发 nl_query_unanswered 信号"
    attr = kws[0].get("attribution")
    assert attr["layer"] == GapLayer.TOOL.value
    assert attr["target_kind"] == "engine"
    assert attr["target_ref"] == "nl_engine"


# ── 接线点 3: intent_recognizer（content / term） ────────────────────────

def test_intent_recognizer_discard_carries_content_attribution(capture_signals):
    from odap.biz.data.qa.pipeline.understanding.intent_recognizer import EntityExtractor

    ex = EntityExtractor(llm_client=None, term_resolver=None, entity_set={"曹操"})
    assert ex.extract("查询「诸侯」的关联", domain_id="d1") == []
    kws = _find(capture_signals, "mapping_failure")
    assert kws, "丢弃分支应发 mapping_failure 信号"
    attr = kws[0].get("attribution")
    assert attr["layer"] == GapLayer.CONTENT.value
    assert attr["target_kind"] == "term"
    assert attr["target_ref"] == "诸侯"


# ── 接线点 4: qa_engine fallback（tool / engine） ────────────────────────

def test_qa_engine_unanswered_carries_tool_attribution(capture_signals):
    from unittest.mock import MagicMock
    from odap.biz.data.qa.qa_engine import QAEngineV2, RAGResult

    eng = QAEngineV2(use_mock=True)
    good = [RAGResult(content="实体A | 类型:人物", source="s1", score=0.8, metadata={})]
    eng.rag_pipeline.retrieve = MagicMock(return_value=good)
    eng.rag_pipeline.generate_context = MagicMock(return_value="实体A | 类型:人物")
    eng._generate_answer = MagicMock(return_value="未找到相关信息。")
    eng.ask("实体A是什么", user_id="test")
    kws = _find(capture_signals, "qa_unanswered")
    assert kws, "fallback 分支应发 qa_unanswered 信号"
    attr = kws[0].get("attribution")
    assert attr["layer"] == GapLayer.TOOL.value
    assert attr["target_kind"] == "engine"
    assert attr["target_ref"] == "qa_engine.fallback"


# ── emitter 透传（真实 emitter 函数体 + 真存储） ─────────────────────────

# real_store fixture 见文件头部（还原真实 emitter + 注入 tmp DB service）


def test_emitter_passes_attribution_to_storage(real_store):
    gap_emitter.report_gap_signal(
        GapSignalSource.TERM_RESOLVE_MISS, " 诸侯 ",
        domain_id="d1",
        attribution={"layer": "content", "target_kind": "term", "target_ref": "诸侯"},
    )
    g = real_store.get_by_expression("诸侯", "-::d1")
    assert g is not None
    assert g["attribution_counts_json"] == {"content": 1}
    assert g["sources_json"][-1]["attribution"]["layer"] == "content"


def test_emitter_without_attribution_backward_compatible(real_store):
    """旧签名（无 attribution）经真实 emitter 全链路行为不变。"""
    gap_emitter.report_gap_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯",
                                  domain_id="d1")
    g = real_store.get_by_expression("诸侯", "-::d1")
    assert g is not None
    assert g["heat"] == 1
    assert g["attribution_counts_json"] == {}


# ── 服务层：stats.by_layer（真实记录，无推断） ───────────────────────────

def test_stats_by_layer_from_real_records(real_store):
    svc = gap_emitter._get_service()
    svc.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "a", domain_id="d1",
                      attribution={"layer": "content", "target_kind": "term",
                                   "target_ref": "a"})
    svc.record_signal(GapSignalSource.QA_UNANSWERED, "b", domain_id="d1",
                      attribution={"layer": "tool", "target_kind": "engine",
                                   "target_ref": "qa_engine.fallback"})
    svc.record_signal(GapSignalSource.MAPPING_FAILURE, "a", domain_id="d1",
                      attribution={"layer": "content", "target_kind": "term",
                                   "target_ref": "a"})
    r = svc.stats()
    assert r["status"] == "ok"
    assert r["by_layer"] == {"content": 2, "tool": 1}


# ── 服务层：promote 透传 semantic_type（无归因时行为不变） ────────────────

def test_promote_passes_content_target_kind_as_semantic_type(real_store, monkeypatch):
    svc = gap_emitter._get_service()
    svc.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯", domain_id="d1",
                      attribution={"layer": "content", "target_kind": "属性",
                                   "target_ref": "诸侯"})
    gap = real_store.get_by_expression("诸侯", "-::d1")

    captured = {}

    def fake_factory():
        class _CS:
            def create_candidate_from_gap(self, payload):
                captured.update(payload)
                return {"status": "ok", "candidate_id": "cand-1"}
        return _CS()

    monkeypatch.setattr(svc, "_candidate_service_factory", fake_factory)
    r = svc.promote(gap["id"], actor="tester")
    assert r["status"] == "ok"
    assert captured.get("semantic_type") == "属性"   # content 层 target_kind 透传


def test_promote_without_attribution_keeps_default(real_store, monkeypatch):
    svc = gap_emitter._get_service()
    svc.record_signal(GapSignalSource.TERM_RESOLVE_MISS, "诸侯", domain_id="d1")
    gap = real_store.get_by_expression("诸侯", "-::d1")

    captured = {}

    def fake_factory():
        class _CS:
            def create_candidate_from_gap(self, payload):
                captured.update(payload)
                return {"status": "ok", "candidate_id": "cand-1"}
        return _CS()

    monkeypatch.setattr(svc, "_candidate_service_factory", fake_factory)
    r = svc.promote(gap["id"], actor="tester")
    assert r["status"] == "ok"
    assert "semantic_type" not in captured            # 不传 → candidate 默认"对象类型"
