"""L3 受限 LLM 消歧单测（`intent_llm.py`）。

"受限"必须可验证，否则 L3 就是不可审计的黑盒：
- 候选封闭：只能返回候选下标，越界/非整数/无法判定之外的值一律不可用；
- 无理由不可用：空理由的结果不可审计，按不可用处理；
- 不可用即澄清：调用方（路由层）拿到 `LLMUnavailable` 必须降级，不允许就近猜。
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.orchestration.impl.intent_llm import (
    INTENT_LLM_UNAVAILABLE,
    Candidate,
    LLMUnavailable,
    OpenAICompatClient,
    RestrictedLLMDisambiguator,
)

CANDIDATES = [
    Candidate(index=0, surface="坪效", intent="metric_query", score=0.72),
    Candidate(index=1, surface="仓容", intent="concept_lookup", score=0.70),
]


class _FakeClient:
    endpoint = "http://127.0.0.1:9/v1/chat/completions"
    model = "fake-chat"

    def __init__(self, payload=None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.seen_prompt: str = ""
        self.seen_system: str = ""

    def complete_json(self, system: str, user: str):
        self.seen_system = system
        self.seen_prompt = user
        if self.error is not None:
            raise self.error
        return self.payload


def _disambiguator(payload=None, error=None, max_candidates: int = 5):
    client = _FakeClient(payload=payload, error=error)
    return RestrictedLLMDisambiguator(client=client, max_candidates=max_candidates), client


class TestHappyPath:
    def test_valid_choice_returned_with_audit_fields(self):
        llm, _ = _disambiguator({"choice": 0, "confidence": 0.93, "reason": "坪效是指标问句"})
        choice = llm.disambiguate("坪效和仓容比一下", CANDIDATES)
        assert choice.choice_index == 0
        assert choice.confidence == 0.93
        assert choice.reason
        assert choice.model == "fake-chat"
        assert choice.endpoint.endswith("/chat/completions")
        assert choice.elapsed_ms >= 0

    def test_undecidable_choice_is_minus_one(self):
        llm, _ = _disambiguator({"choice": -1, "confidence": 0.0, "reason": "候选都不像"})
        assert llm.disambiguate("随便问问", CANDIDATES).choice_index == -1

    def test_missing_confidence_falls_back_not_fails(self):
        llm, _ = _disambiguator({"choice": 1, "reason": "仓容是对象词"})
        assert llm.disambiguate("坪效和仓容比一下", CANDIDATES).confidence == 0.9


class TestCandidateClosure:
    def test_prompt_only_lists_visible_candidates(self):
        llm, client = _disambiguator({"choice": 0, "reason": "ok"})
        llm.disambiguate("坪效和仓容比一下", CANDIDATES)
        assert "0. 表面形式=坪效" in client.seen_prompt
        assert "1. 表面形式=仓容" in client.seen_prompt
        # 约束写在 system prompt 里：只能从给定候选里选
        assert "只能从给定候选中选择一个" in client.seen_system
        assert "禁止引入候选之外的意图" in client.seen_system

    def test_candidates_truncated_to_max(self):
        llm, client = _disambiguator({"choice": 0, "reason": "ok"}, max_candidates=1)
        llm.disambiguate("坪效和仓容比一下", CANDIDATES)
        assert "0. 表面形式=坪效" in client.seen_prompt
        assert "1. 表面形式=" not in client.seen_prompt

    @pytest.mark.parametrize("payload", [
        {"choice": 5, "reason": "越界"},
        {"choice": -2, "reason": "越界"},
        {"choice": "0", "reason": "类型错"},
        {"choice": True, "reason": "布尔不是下标"},
        {"choice": None, "reason": "缺失"},
    ])
    def test_illegal_choice_is_unavailable(self, payload):
        llm, _ = _disambiguator(payload)
        with pytest.raises(LLMUnavailable):
            llm.disambiguate("坪效和仓容比一下", CANDIDATES)

    def test_empty_reason_is_unavailable(self):
        llm, _ = _disambiguator({"choice": 0, "confidence": 0.9, "reason": "   "})
        with pytest.raises(LLMUnavailable):
            llm.disambiguate("坪效和仓容比一下", CANDIDATES)


class TestUnavailablePaths:
    def test_no_client_configured(self):
        llm = RestrictedLLMDisambiguator(client=None)
        assert llm.available is False
        with pytest.raises(LLMUnavailable) as excinfo:
            llm.disambiguate("坪效和仓容比一下", CANDIDATES)
        assert "未配置" in excinfo.value.reason

    def test_no_candidates(self):
        llm, _ = _disambiguator({"choice": 0, "reason": "ok"})
        with pytest.raises(LLMUnavailable):
            llm.disambiguate("坪效和仓容比一下", [])

    def test_transport_error_surfaces_as_unavailable(self):
        llm, _ = _disambiguator(error=ConnectionError("connection refused"))
        with pytest.raises(LLMUnavailable):
            llm.disambiguate("坪效和仓容比一下", CANDIDATES)

    def test_error_code_constant_is_stable(self):
        assert INTENT_LLM_UNAVAILABLE == "INTENT_LLM_UNAVAILABLE"


class TestClientEndpoint:
    def test_endpoint_with_v1_suffix(self):
        client = OpenAICompatClient("http://127.0.0.1:1234/v1", "m")
        assert client.endpoint == "http://127.0.0.1:1234/v1/chat/completions"

    def test_endpoint_without_v1_suffix(self):
        client = OpenAICompatClient("http://127.0.0.1:1234/", "m")
        assert client.endpoint == "http://127.0.0.1:1234/v1/chat/completions"


class TestDefaultWiring:
    """默认装配必须「未显式配置就不启用」——否则每次低置信查询都会真的去连外网。"""

    @staticmethod
    def _patch(monkeypatch, api_key: str):
        import odap.infra.config_composer as cfg

        values = {
            "llm.api_base": "https://api.openai.com/v1",
            "llm.model": "gpt-4",
            "llm.embedder_model": "text-embedding-3-small",
            "llm.api_key": api_key,
        }
        monkeypatch.setattr(cfg, "get_config",
                            lambda key, default=None: values.get(key, default))

    def test_missing_api_key_keeps_l3_off(self, monkeypatch):
        from odap.biz.core.ontology.orchestration.impl.intent_llm import (
            build_default_disambiguator,
        )

        self._patch(monkeypatch, api_key="")
        assert build_default_disambiguator().available is False

    def test_configured_endpoint_builds_client(self, monkeypatch):
        from odap.biz.core.ontology.orchestration.impl.intent_llm import (
            build_default_disambiguator,
        )

        self._patch(monkeypatch, api_key="sk-test")
        llm = build_default_disambiguator()
        assert llm.available is True
        assert llm.endpoint.endswith("/chat/completions")

    def test_missing_api_key_keeps_vector_recall_off(self, monkeypatch):
        from odap.biz.core.ontology.orchestration.impl.intent_embedding import (
            build_default_recall,
        )

        self._patch(monkeypatch, api_key="")
        assert build_default_recall({"退货率": {"canonical": "退货率"}}) is None

    def test_configured_endpoint_builds_recall(self, monkeypatch):
        from odap.biz.core.ontology.orchestration.impl.intent_embedding import (
            build_default_recall,
        )

        self._patch(monkeypatch, api_key="sk-test")
        recall = build_default_recall({"退货率": {"canonical": "退货率"}})
        assert recall is not None
