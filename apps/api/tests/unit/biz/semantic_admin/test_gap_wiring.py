"""Task 4: 四类缺口信号源接线测试（真实函数体，规则 14.6）。

capture_signals 只替换 emitter 的落库 sink（gap_emitter.report_gap_signal），
宿主分支（canonical_of / _resolve_term / extract / ask）全部走真实实现体。
"""
import pytest
from odap.biz.semantic_admin.gap_pool.services import gap_emitter
from odap.biz.semantic_admin.usl_manager.services.usl_term_resolver import UslTermResolver


@pytest.fixture(autouse=True)
def capture_signals(monkeypatch):
    """把 emitter 的落库替换为内存收集，隔离 DB，但调用点走真实分支。"""
    calls = []
    def fake_report(source, expression, **kw):
        calls.append((str(source), expression, kw))
    monkeypatch.setattr(gap_emitter, "report_gap_signal", fake_report)
    return calls


def test_term_resolver_miss_emits(capture_signals):
    r = UslTermResolver()
    r.load_terms("d1", [{"canonical": "势力", "synonyms": ["阵营"],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False}])
    # 真实调用 canonical_of，未命中
    assert r.canonical_of("诸侯", "d1") is None
    assert any(s == "term_resolve_miss" and e == "诸侯" for s, e, _ in capture_signals)


def test_term_resolver_hit_does_not_emit(capture_signals):
    r = UslTermResolver()
    r.load_terms("d1", [{"canonical": "势力", "synonyms": [],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False}])
    assert r.canonical_of("势力", "d1") == "势力"
    assert not any(s == "term_resolve_miss" for s, _, _ in capture_signals)


def test_term_resolver_emit_false_suppresses(capture_signals):
    """终审 M1 回归：resolve-check 等读侧判定用 emit=False，未命中也不发信号。

    走真实 canonical_of 函数体（规则 14.6），仅 emitter sink 被 capture 替换。
    """
    r = UslTermResolver()
    r.load_terms("d1", [{"canonical": "势力", "synonyms": [],
                         "near_synonyms": [], "aliases": [], "stoplist_flag": False}])
    # 有 domain_id 分支：未命中 + emit=False → 不发
    assert r.canonical_of("诸侯", "d1", emit=False) is None
    # 无 domain_id 分支：未命中 + emit=False → 不发
    assert r.canonical_of("诸侯", emit=False) is None
    assert not any(s == "term_resolve_miss" for s, _, _ in capture_signals)
    # 对照：默认 emit=True 仍发（确保守卫没把运行时归因路径也关掉）
    assert r.canonical_of("诸侯", "d1") is None
    assert any(s == "term_resolve_miss" and e == "诸侯" for s, e, _ in capture_signals)


# ── Point 2: nl_engine（真实函数体） ────────────────────────────────────

def test_nl_engine_miss_emits(capture_signals):
    from odap.biz.core.ontology.semantic_retrieval.impl.nl_engine import NLEngine
    class _StubUsl:
        def list_terms(self, *, synonym_keyword=None, page_size=5, **kw):
            return [], 0
    eng = NLEngine(usl_manager=_StubUsl())
    assert eng._resolve_term("诸侯", _StubUsl()) is None
    assert any(s == "nl_query_unanswered" and e == "诸侯" for s, e, _ in capture_signals)


def test_nl_engine_usl_none_does_not_emit(capture_signals):
    from odap.biz.core.ontology.semantic_retrieval.impl.nl_engine import NLEngine
    eng = NLEngine(usl_manager=None)
    assert eng._resolve_term("诸侯", None) is None   # :60-61 infra branch, NOT wired
    assert not any(s == "nl_query_unanswered" for s, _, _ in capture_signals)


# ── Point 3: intent_recognizer EntityExtractor 丢弃分支（真实函数体） ────

def test_intent_recognizer_discard_emits(capture_signals):
    from odap.biz.data.qa.pipeline.understanding.intent_recognizer import EntityExtractor
    # 仅注入 entity_set（无 term_resolver / 无 LLM）：候选不在本体集合 → 丢弃分支
    ex = EntityExtractor(llm_client=None, term_resolver=None, entity_set={"曹操"})
    result = ex.extract("查询「诸侯」的关联", domain_id="d1")
    assert result == []
    assert any(
        s == "mapping_failure" and e == "诸侯" and kw.get("domain_id") == "d1"
        for s, e, kw in capture_signals
    )


def test_intent_recognizer_hit_does_not_emit(capture_signals):
    from odap.biz.data.qa.pipeline.understanding.intent_recognizer import EntityExtractor
    ex = EntityExtractor(llm_client=None, term_resolver=None, entity_set={"曹操"})
    result = ex.extract("查询「曹操」的关联", domain_id="d1")
    assert result == ["曹操"]
    assert not any(s == "mapping_failure" for s, _, _ in capture_signals)


# ── Point 4: qa_engine :1321 正常流未答检测（真实函数体，规则 14.6） ─────
# ask() 可离线构造：QAEngineV2(use_mock=True) + 桩 rag_pipeline.retrieve/
# generate_context（供给 RAG 数据）+ 桩 _generate_answer（供给 answer 文本）。
# 待验证的 :1321-1326 缺口发射分支走真实实现体，桩只喂输入、不替换该分支。

def _make_qa_engine(answer_text):
    from unittest.mock import MagicMock
    from odap.biz.data.qa.qa_engine import QAEngineV2, RAGResult
    eng = QAEngineV2(use_mock=True)
    good = [RAGResult(content="实体A | 类型:人物", source="s1", score=0.8, metadata={})]
    eng.rag_pipeline.retrieve = MagicMock(return_value=good)
    eng.rag_pipeline.generate_context = MagicMock(return_value="实体A | 类型:人物")
    eng._generate_answer = MagicMock(return_value=answer_text)
    return eng


def test_qa_engine_unanswered_emits(capture_signals):
    eng = _make_qa_engine("未找到相关信息。")
    result = eng.ask("实体A是什么", user_id="test")
    assert result["dialog_state"] != "waiting_for_clarification"
    assert any(
        s == "qa_unanswered" and e == "实体A是什么" for s, e, _ in capture_signals
    )


def test_qa_engine_answered_does_not_emit(capture_signals):
    eng = _make_qa_engine("实体A是一个人物。")
    eng.ask("实体A是什么", user_id="test")
    assert not any(s == "qa_unanswered" for s, _, _ in capture_signals)
