"""QA 路由诚实化回归测试（圆桌结论·代码实证版 P1 门禁）。

背景：`/api/qa/ask` 曾在路由层凭空编造字段并丢弃引擎算出的真实结果——
  · intent={"type": "query", "confidence": 0.85}   假精确值，与问题内容无关
  · sources_used=["graphiti", "rag"]               谎报数据源（实际可能一个都没命中）
  · suggested_actions / reasoning_chain            QAEngineV2.ask() 真实算出却被整个丢掉

修复后 intent 复用 pipeline 栈里已被大量测试覆盖的确定性 IntentRecognizer，
两个真实字段透传。sources_used 字段被**移除**而非改算：QAEngineV2 的
SourceTrace.source 是条目可读标签（"西游人物:孙悟空"，缺失时甚至是 episode 正文），
引擎内不存在"检索通道"信号，该字段只能是 sources 的名不副实副本。

另修：IntentRecognizer 的 KEYWORD_LOOKUP 规则曾漏掉中文最高频查询动词
「查询」「检索」，导致真实问题几乎恒定落到 0.3 兜底——字段诚实但功能失效。

规则（AGENTS.md）：
- 规则 14：失败必须显式——识别器不可用时返回 unknown/None，绝不回填假精确值
- Mock 外部服务（QAEngineV2），不 mock 被测的派生逻辑本身
- async 路由用 FastAPI TestClient + dependency_overrides
"""

import pytest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


# ── _recognize_intent：真实规则置信度，非恒定 0.85 ────────────────────

class TestRecognizeIntent:
    """intent.confidence 曾恒为 0.85，无论问什么。修复后由确定性规则算出，
    不同意图必须给出不同置信度——若有人回退成常量，这些断言必须变红。
    """

    def test_keyword_lookup_intent(self):
        from odap.biz.data.qa.api.routes import _recognize_intent

        result = _recognize_intent("查找孙悟空")
        assert result["type"] == "keyword_lookup"
        assert result["confidence"] == 0.8

    def test_action_intent_has_higher_confidence(self):
        from odap.biz.data.qa.api.routes import _recognize_intent

        result = _recognize_intent("执行部署任务")
        assert result["type"] == "action"
        assert result["confidence"] == 0.9

    def test_complex_analysis_intent(self):
        from odap.biz.data.qa.api.routes import _recognize_intent

        result = _recognize_intent("分析各方势力对比")
        assert result["type"] == "complex_analysis"
        assert result["confidence"] == 0.8

    def test_no_rule_match_yields_low_confidence(self):
        """无规则命中 → 识别器确定性兜底 0.3（低置信度），不是 0.85"""
        from odap.biz.data.qa.api.routes import _recognize_intent

        result = _recognize_intent("嗯")
        assert result["confidence"] == 0.3

    def test_confidence_is_not_a_constant(self):
        """核心变异锚点：不同问题必须得到不同 confidence。

        注意 0.85 本身是 graph_traverse/temporal_query 的合法真实权重——
        要断言的不是"0.85 不出现"，而是"confidence 随问题变化"。
        """
        from odap.biz.data.qa.api.routes import _recognize_intent

        confidences = {
            _recognize_intent(q)["confidence"]
            for q in ["查找X", "执行Y", "分析Z的趋势", "嗯"]
        }
        assert len(confidences) >= 3
        assert confidences == {0.8, 0.9, 0.3}

    def test_recognizer_failure_degrades_to_unknown(self):
        """识别器炸了必须显式报 unknown/None，绝不编造假值（规则 14）"""
        import odap.biz.data.qa.api.routes as routes_mod

        original = routes_mod._intent_recognizer
        routes_mod._intent_recognizer = MagicMock()
        routes_mod._intent_recognizer.recognize.side_effect = RuntimeError("boom")
        try:
            result = routes_mod._recognize_intent("查找孙悟空")
            assert result == {"type": "unknown", "confidence": None}
        finally:
            routes_mod._intent_recognizer = original


# ── intent 规则覆盖：高频查询动词不得掉进 0.3 兜底 ────────────────────

class TestIntentRuleCoverage:
    """KEYWORD_LOOKUP 规则曾漏掉「查询」「检索」——中文最高频的查询动词。

    后果不是报错，而是 intent 字段对绝大多数真实问题恒定返回同一个兜底值
    (semantic_search, 0.3)：字段"诚实"但功能失效，属于另一种伪绿灯。
    """

    def test_chaxun_hits_keyword_lookup(self):
        from odap.biz.data.qa.api.routes import _recognize_intent

        result = _recognize_intent("查询曹操的势力范围")
        assert result["type"] == "keyword_lookup"
        assert result["confidence"] == 0.8

    def test_jiansuo_hits_keyword_lookup(self):
        from odap.biz.data.qa.api.routes import _recognize_intent

        result = _recognize_intent("检索西游记相关人物")
        assert result["type"] == "keyword_lookup"
        assert result["confidence"] == 0.8

    def test_realistic_query_does_not_fall_to_default(self):
        """核心变异锚点：典型业务问题不得落到 0.3 无命中兜底"""
        from odap.biz.data.qa.api.routes import _recognize_intent

        for q in ["查询曹操的势力范围", "检索传感器列表", "查找孙悟空", "搜索三国事件"]:
            assert _recognize_intent(q)["confidence"] != 0.3, q


# ── sources_used 已移除：不得被加回来继续谎报 ────────────────────────

class TestSourcesUsedRemoved:
    def test_ask_response_has_no_sources_used_field(self):
        """该字段名暗示"检索通道"，但引擎无此信号，只能是 sources 的误导性副本"""
        from odap.biz.data.qa.api.routes import AskResponse

        assert "sources_used" not in AskResponse.model_fields

    def test_route_module_has_no_derive_helper(self):
        import odap.biz.data.qa.api.routes as routes_mod

        assert not hasattr(routes_mod, "_derive_sources_used")


# ── AskResponse schema：新增透传字段 ─────────────────────────────────

class TestAskResponseSchema:
    def test_new_passthrough_fields_exist_with_empty_defaults(self):
        from odap.biz.data.qa.api.routes import AskResponse

        resp = AskResponse(session_id="s1", answer="a")
        assert resp.suggested_actions == []
        assert resp.reasoning_chain == []

    def test_fields_carry_real_payload(self):
        from odap.biz.data.qa.api.routes import AskResponse

        resp = AskResponse(
            session_id="s1",
            answer="a",
            suggested_actions=[{"action": "deploy"}],
            reasoning_chain=[{"step": "retrieval", "detail": "命中 3 条"}],
        )
        assert resp.suggested_actions[0]["action"] == "deploy"
        assert resp.reasoning_chain[0]["step"] == "retrieval"


# ── 路由级端到端：真实结果必须透传到响应 ─────────────────────────────

def _build_app():
    from odap.biz.data.qa.api.routes import router
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(router)

    async def _mock_user():
        return {"sub": "u-test", "role": "admin", "ws_id": "ws-1", "ws_role": "owner"}

    app.dependency_overrides[get_current_user] = _mock_user
    return app


class TestAskRoutePassthrough:
    """路由层曾丢弃引擎算出的 suggested_actions/reasoning_chain，并伪造 intent 与
    sources_used。本类用 TestClient 打真实路由，断言真实字段透传、伪造字段消失。
    """

    def _engine_result(self):
        return {
            "session_id": "sess-1",
            "answer": "孙悟空是唐僧的大徒弟。",
            "sources": [
                {"source": "西游人物:孙悟空", "excerpt": "西游记第一回", "confidence": 0.82},
            ],
            "dialog_state": "completed",
            "suggested_actions": [{"action_id": "a1", "label": "查看师徒关系"}],
            "reasoning_chain": [{"step": "retrieval", "detail": "bm25 命中"}],
        }

    def test_ask_passes_through_real_engine_results(self):
        app = _build_app()
        mock_engine = MagicMock()
        mock_engine.ask = MagicMock(return_value=self._engine_result())

        with patch("odap.biz.data.qa.api.routes._get_qa_engine", return_value=mock_engine):
            with TestClient(app) as client:
                resp = client.post("/api/qa/ask", json={"question": "查找孙悟空"})

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        body = resp.json()
        # 真实字段透传（曾被整个丢弃）
        assert body["suggested_actions"] == [{"action_id": "a1", "label": "查看师徒关系"}]
        assert body["reasoning_chain"] == [{"step": "retrieval", "detail": "bm25 命中"}]
        # intent 由确定性识别器算出（曾恒为 {"type": "query", "confidence": 0.85}）
        assert body["intent"]["type"] == "keyword_lookup"
        assert body["intent"]["confidence"] == 0.8
        # 谎报字段已移除（曾恒为 ["graphiti", "rag"]）
        assert "sources_used" not in body

    def test_ask_reports_no_sources_when_engine_found_none(self):
        """引擎没检索到任何东西时，sources 必须如实为空，不得凭空捏造溯源"""
        app = _build_app()
        result = self._engine_result()
        result["sources"] = []
        mock_engine = MagicMock()
        mock_engine.ask = MagicMock(return_value=result)

        with patch("odap.biz.data.qa.api.routes._get_qa_engine", return_value=mock_engine):
            with TestClient(app) as client:
                resp = client.post("/api/qa/ask", json={"question": "查找孙悟空"})

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["sources"] == []
