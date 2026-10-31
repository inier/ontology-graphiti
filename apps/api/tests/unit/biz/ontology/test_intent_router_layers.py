"""意图漏斗分层单测（`intent_router.py` + `intent_ranking.py` + `intent_frame.py`）。

分层可度量是这一版的核心承诺：同一个 router 用 `layers="l1"|"l2"|"full"` 切换，
评测脚本据此出增益表。这里把每层的行为分别钉住，避免"总指标达标"掩盖某一层失效。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from odap.biz.core.ontology.orchestration.impl.intent_llm import (
    INTENT_LLM_UNAVAILABLE,
    RestrictedLLMDisambiguator,
)
from odap.biz.core.ontology.orchestration.impl.intent_router import (
    L1IntentRouter,
    UslDictionary,
)
from odap.biz.core.ontology.orchestration.impl.intent_terms import TermSpan

ROOT = Path(__file__).resolve().parents[6]
TERMS = json.loads(
    (ROOT / "apps" / "api" / "tests" / "eval" / "intent" / "usl_terms.json").read_text("utf-8")
)["terms"]

UNSEEN = "电商业务的动销率这季度怎么样"  # 词典里没有「动销率」，只能靠形态
COMPOSITE = "上季度退货比例是多少，然后冻结供应商"
ACTION = "帮我删掉这批测试订单"


def _router(layer: str = "full", **kwargs) -> L1IntentRouter:
    return L1IntentRouter(dictionary=UslDictionary(loader=lambda: list(TERMS)),
                          layers=layer, **kwargs)


async def _route(query: str, layer: str = "full", **kwargs):
    return await _router(layer, **kwargs).route(query, {"sub": "u-1"}, "ws-1")


class TestLayerL1:
    async def test_unseen_noun_is_clarified(self):
        """只有词典时跨域词必然漏召回 —— 这正是 61% 的来源，必须显式澄清而不是乱判。"""
        frame = await _route(UNSEEN, layer="l1")
        assert frame.intent_type == "unknown"
        assert frame.clarify_question
        assert frame.level == "L0"

    async def test_dict_hit_is_l1_level(self):
        frame = await _route("上季度退货率是多少", layer="l1")
        assert frame.intent_type == "metric_query"
        assert frame.level == "L1"
        assert any(e.kind == "dict_hit" for e in frame.prov.evidence)

    async def test_l1_does_not_use_compose(self):
        """动作组合属于 L2，L1 只能认出词典里连写的动作（如「删除订单」）。"""
        frame = await _route(ACTION, layer="l1")
        assert frame.intent_type == "concept_lookup"
        assert frame.slots["terms"] == ["订单"]


class TestLayerL2:
    async def test_morphology_recovers_unseen_noun(self):
        frame = await _route(UNSEEN, layer="l2")
        assert frame.intent_type == "metric_query"
        assert frame.slots["terms"] == ["动销率"]
        assert frame.level == "L2"
        routing = frame.slots["routing"]
        assert routing["l1"]["hit"] is False
        assert routing["l2"]["cues"] == ["动销率"]

    async def test_cue_evidence_written_to_provenance(self):
        frame = await _route(UNSEEN, layer="l2")
        refs = [e.ref for e in frame.prov.evidence if e.kind == "intent_cue"]
        assert "cue:metric_query:动销率" in refs

    async def test_cue_evidence_passes_mechanical_check(self):
        """溯源证据必须能被机检器验证：不能"随便写个 cue 就声称是某意图"。"""
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver()
        frame = await _route(UNSEEN, layer="l2")
        cue_evidence = [e for e in frame.prov.evidence if e.kind == "intent_cue"]
        assert cue_evidence
        for evidence in cue_evidence:
            ok, reason = resolver.resolve(evidence.kind, evidence.ref)
            assert ok, f"{evidence.ref} 未通过机检：{reason}"

    async def test_forged_cue_evidence_rejected(self):
        from odap.biz.core.ontology.orchestration.evidence import DefaultEvidenceResolver

        resolver = DefaultEvidenceResolver()
        ok, _reason = resolver.resolve("intent_cue", "cue:metric_query:员工年假")
        assert ok is False

    async def test_compose_recovers_action_phrase(self):
        frame = await _route(ACTION, layer="l2")
        assert frame.intent_type == "action_request"
        assert frame.slots["terms"] == ["删掉这批测试订单"]
        assert frame.slots["routing"]["l2"]["actions"] == ["删掉这批测试订单"]

    async def test_l2_equals_full_when_no_fuzzy_or_vector_needed(self):
        l2 = await _route(UNSEEN, layer="l2")
        full = await _route(UNSEEN, layer="full")
        assert (l2.intent_type, l2.slots["terms"]) == (full.intent_type, full.slots["terms"])


class TestComposite:
    async def test_primary_intent_from_first_clause(self):
        frame = await _route(COMPOSITE)
        assert frame.intent_type == "metric_query"
        assert frame.primary_intent == "metric_query"

    async def test_sub_intent_carries_action_terms(self):
        frame = await _route(COMPOSITE)
        assert len(frame.sub_intents) == 1
        assert frame.sub_intents[0].intent_type == "action_request"
        assert frame.sub_intents[0].terms == ["冻结供应商"]

    async def test_action_first_query_keeps_action_primary(self):
        """主句在前：「帮我删掉订单，然后看履约率」主意图是动作，不是指标。"""
        frame = await _route("帮我删掉这批测试订单，然后看下履约率")
        assert frame.intent_type == "action_request"
        assert [s.intent_type for s in frame.sub_intents] == ["metric_query"]

    async def test_action_slot_survives_in_terms(self):
        """动作槽位是 F9 写操作的输入，不能因为主意图是指标就丢进 entities。"""
        frame = await _route(COMPOSITE)
        assert frame.slots["terms"][0] == "退货比例"
        assert "冻结供应商" in frame.slots["terms"]

    async def test_lookup_term_goes_to_entities(self):
        """非主意图类别的命中进 entities，避免污染主槽位袋。"""
        frame = await _route("上季度退货比例是多少，供应商等级现在什么水平")
        assert frame.slots["terms"] == ["退货比例"]
        assert frame.slots["entities"] == ["供应商等级"]


class TestRoutingTrace:
    async def test_routing_records_every_layer(self):
        routing = (await _route(COMPOSITE)).slots["routing"]
        for key in ("l1", "l2", "candidates", "primary_clause", "reason", "chosen"):
            assert key in routing, key
        assert routing["chosen"]["intent"] == "metric_query"
        assert routing["chosen"]["source"] in {"primary_clause", "l2", "l3"}

    async def test_candidates_carry_source_and_score(self):
        routing = (await _route(COMPOSITE)).slots["routing"]
        sources = {c["source"] for c in routing["candidates"]}
        assert sources == {"dict", "compose"}
        for candidate in routing["candidates"]:
            assert 0.0 < candidate["score"] <= 1.0

    async def test_primary_clause_is_original_text(self):
        routing = (await _route(COMPOSITE)).slots["routing"]
        assert routing["primary_clause"] in COMPOSITE


class TestClarifyPaths:
    async def test_empty_query(self):
        frame = await _route("   ")
        assert frame.intent_type == "unknown"
        assert "请输入" in frame.clarify_question

    @pytest.mark.parametrize("query", ["你好", "年假天数还剩多少", "今天天气怎么样"])
    async def test_no_evidence_clarifies(self, query):
        frame = await _route(query)
        assert frame.intent_type == "unknown"
        assert frame.confidence == 0.0
        assert frame.clarify_question
        refs = [e.ref for e in frame.prov.evidence]
        assert "decision:clarify_no_dictionary_hit" in refs

    async def test_dictionary_failure_is_explicit(self):
        def _broken():
            raise RuntimeError("SQLite 打开失败")

        router = L1IntentRouter(dictionary=UslDictionary(loader=_broken))
        frame = await router.route("上季度退货率是多少", {}, "ws-1")
        assert frame.intent_type == "unknown"
        assert "SQLite 打开失败" in frame.slots["dictionary_error"]
        assert any(e.ref == "decision:clarify_dictionary_unavailable"
                   for e in frame.prov.evidence)


class _FakeEmbedder:
    """向量召回替身：只产出两条低分候选，用来触发 L3（不联网）。"""

    degraded_reason = None

    def find_vector_spans(self, text, blocked=()):
        first, second = text.find("坪效"), text.find("仓容")
        return [
            TermSpan("坪效", first, first + 2, "metric_query", 0.72, "vector", "坪效"),
            TermSpan("仓容", second, second + 2, "concept_lookup", 0.70, "vector", "仓容"),
        ]


class _StubClient:
    endpoint = "http://127.0.0.1:9/v1/chat/completions"
    model = "stub-chat"

    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, system, user):
        return self.payload


L3_QUERY = "坪效和仓容比一下"


class TestLayerL3:
    async def test_unavailable_degrades_to_clarify(self):
        frame = await _route(L3_QUERY, embedder=_FakeEmbedder(),
                             llm=RestrictedLLMDisambiguator(client=None))
        assert frame.intent_type == "unknown"
        assert frame.slots["intent_error_code"] == INTENT_LLM_UNAVAILABLE
        assert frame.slots["routing"]["l3"]["used"] is False
        assert any(e.ref == "decision:intent_l3_unavailable" for e in frame.prov.evidence)

    async def test_valid_choice_overrides_primary_intent(self):
        llm = RestrictedLLMDisambiguator(
            client=_StubClient({"choice": 0, "confidence": 0.93, "reason": "坪效是指标问句"})
        )
        frame = await _route(L3_QUERY, embedder=_FakeEmbedder(), llm=llm)
        assert frame.intent_type == "metric_query"
        assert frame.confidence >= 0.80
        routing = frame.slots["routing"]
        assert routing["l3"]["used"] is True
        assert routing["chosen"]["source"] == "l3"
        assert any(e.ref == "decision:intent_l3_used" for e in frame.prov.evidence)

    async def test_model_undecidable_degrades_to_clarify(self):
        llm = RestrictedLLMDisambiguator(
            client=_StubClient({"choice": -1, "confidence": 0.0, "reason": "候选都不像"})
        )
        frame = await _route(L3_QUERY, embedder=_FakeEmbedder(), llm=llm)
        assert frame.intent_type == "unknown"
        assert "候选都不像" in frame.clarify_question

    async def test_l3_not_triggered_when_l2_confident(self):
        """L3 只在置信不足时介入：高置信查询不应产生 l3 记录。"""
        routing = (await _route(COMPOSITE)).slots["routing"]
        assert "l3" not in routing
