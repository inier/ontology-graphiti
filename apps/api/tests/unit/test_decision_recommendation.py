import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.decision.decision_recommendation.engine import DecisionRecommendationEngine
from odap.biz.decision.decision_recommendation.models import (
    RecommendationRequest,
    OptionStatus,
    RiskLevel,
)


class TestGenerateRecommendations:
    @pytest.fixture
    def engine(self):
        return DecisionRecommendationEngine(graphiti_client=None, opa_manager=None)

    @pytest.mark.asyncio
    async def test_generate_recommendations_basic(self, engine):
        result = await engine.generate_recommendations({
            "analysis_result": {"value_score": 75, "success_rate": 0.8, "recommended_action": "proceed"},
            "available_options": [
                {"id": "opt-1", "name": "方案A", "action": "execute_a"},
                {"id": "opt-2", "name": "方案B", "action": "execute_b"},
            ],
            "constraints": {"max_cost": 100},
        })
        assert result["recommendation_id"] is not None
        assert len(result["options"]) == 2
        assert result["recommended_option_id"] is not None
        assert result["confidence"] >= 0

    @pytest.mark.asyncio
    async def test_generate_recommendations_no_options(self, engine):
        result = await engine.generate_recommendations({
            "analysis_result": {"recommended_action": "analyze"},
        })
        assert len(result["options"]) == 1
        assert result["options"][0]["name"] == "默认行动方案"

    @pytest.mark.asyncio
    async def test_generate_recommendations_persists_history(self, engine):
        await engine.generate_recommendations({
            "analysis_result": {"value_score": 60},
            "available_options": [{"id": "opt-1", "name": "方案1", "action": "test"}],
        })
        history = engine.get_history()
        assert len(history) == 1
        assert history[0]["recommendation_id"] is not None


class TestAssessRisks:
    @pytest.fixture
    def engine(self):
        return DecisionRecommendationEngine(graphiti_client=None, opa_manager=None)

    @pytest.mark.asyncio
    async def test_assess_risks_basic(self, engine):
        recommendation = {
            "recommendation_id": "rec-test",
            "options": [
                {"option_id": "opt-1", "name": "方案A", "estimated_success_rate": 0.7, "expected_cost": 40},
                {"option_id": "opt-2", "name": "方案B", "estimated_success_rate": 0.5, "expected_cost": 60},
            ],
        }
        result = await engine.assess_risks(recommendation)
        assert len(result["risk_assessments"]) == 2
        assert result["highest_risk_option"] is not None
        assert result["lowest_risk_option"] is not None
        assert result["highest_risk_option"]["overall_score"] >= result["lowest_risk_option"]["overall_score"]

    @pytest.mark.asyncio
    async def test_assess_risks_empty_options(self, engine):
        result = await engine.assess_risks({"recommendation_id": "rec-empty", "options": []})
        assert result["risk_assessments"] == []
        assert result["highest_risk_option"] is None
        assert result["lowest_risk_option"] is None


class TestRankRecommendations:
    @pytest.fixture
    def engine(self):
        return DecisionRecommendationEngine(graphiti_client=None, opa_manager=None)

    def test_rank_recommendations(self, engine):
        recommendations = [
            {
                "recommendation_id": "rec-1",
                "confidence": 0.7,
                "options": [
                    {"option_id": "opt-1", "name": "A", "priority_score": 60, "estimated_success_rate": 0.6, "expected_cost": 40},
                ],
            },
            {
                "recommendation_id": "rec-2",
                "confidence": 0.9,
                "options": [
                    {"option_id": "opt-2", "name": "B", "priority_score": 80, "estimated_success_rate": 0.8, "expected_cost": 30},
                ],
            },
        ]
        result = engine.rank_recommendations(recommendations)
        assert len(result) == 2
        assert result[0]["confidence"] >= result[1]["confidence"]
        assert result[0]["options"][0]["status"] == OptionStatus.RECOMMENDED.value


class TestExplainRecommendation:
    @pytest.fixture
    def engine(self):
        return DecisionRecommendationEngine(graphiti_client=None, opa_manager=None)

    @pytest.mark.asyncio
    async def test_explain_existing_recommendation(self, engine):
        result = await engine.generate_recommendations({
            "analysis_result": {"value_score": 75},
            "available_options": [{"id": "opt-1", "name": "方案1", "action": "test"}],
        })
        rec_id = result["recommendation_id"]
        explanation = engine.explain_recommendation(rec_id)
        assert explanation["recommendation_id"] == rec_id
        assert "explanation" in explanation
        assert explanation["found"] is not False

    def test_explain_nonexistent_recommendation(self, engine):
        explanation = engine.explain_recommendation("nonexistent-id")
        assert explanation["found"] is False
        assert "未找到" in explanation["explanation"]


class TestGetHistory:
    @pytest.fixture
    def engine(self):
        return DecisionRecommendationEngine(graphiti_client=None, opa_manager=None)

    @pytest.mark.asyncio
    async def test_get_history_empty(self, engine):
        history = engine.get_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_get_history_after_recommendation(self, engine):
        await engine.generate_recommendations({
            "analysis_result": {"value_score": 60},
            "available_options": [{"id": "opt-1", "name": "方案1", "action": "test"}],
        })
        history = engine.get_history()
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_get_history_with_limit(self, engine):
        for _ in range(5):
            await engine.generate_recommendations({
                "analysis_result": {"value_score": 60},
                "available_options": [{"id": "opt-1", "name": "方案1", "action": "test"}],
            })
        history = engine.get_history(limit=3)
        assert len(history) == 3


# ── D4 成功路径：graphiti_client 注入 + _find_evidence 真跑 ──────────

class TestFindEvidenceD4SuccessPath:
    """D4：_find_evidence 曾调用幻影方法 search_episodes + 访问不存在的 entity_id 属性，
    导致每次调用 AttributeError 被 except 吞掉 → supporting_evidence 恒空 → confidence
    evidence_factor 恒为 0。修复后调用真实 search(query, num_results) 并提取 uuid。
    """

    def _make_option(self, **overrides):
        from odap.biz.decision.decision_recommendation.models import DecisionOption
        defaults = dict(option_id="opt-1", name="方案A", description="测试方案",
                        action="test_action", rationale="测试理由")
        defaults.update(overrides)
        return DecisionOption(**defaults)

    @pytest.mark.asyncio
    async def test_find_evidence_calls_real_search_not_phantom(self):
        """_find_evidence 必须调用 graphiti.search (非 search_episodes)"""
        from unittest.mock import AsyncMock, MagicMock

        mock_graphiti = MagicMock()
        mock_result = MagicMock()
        mock_result.uuid = "edge-uuid-001"
        mock_graphiti.search = AsyncMock(return_value=[mock_result])

        engine = DecisionRecommendationEngine(graphiti_client=mock_graphiti)
        option = self._make_option()
        request = RecommendationRequest(analysis_result={})

        evidence = await engine._find_evidence(option, request)

        mock_graphiti.search.assert_called_once()
        call_kwargs = mock_graphiti.search.call_args
        assert call_kwargs.kwargs.get("query") or call_kwargs[1].get("query")
        assert "edge-uuid-001" in evidence

    @pytest.mark.asyncio
    async def test_find_evidence_returns_empty_when_no_client(self):
        """graphiti_client=None 时必须显式返回空列表（非 AttributeError）"""
        engine = DecisionRecommendationEngine(graphiti_client=None)
        option = self._make_option()
        request = RecommendationRequest(analysis_result={})

        evidence = await engine._find_evidence(option, request)

        assert evidence == []

    def test_confidence_evidence_factor_nonzero_when_evidence_present(self):
        """supporting_evidence 非空时 confidence 的 evidence_factor 必须 > 0"""
        engine = DecisionRecommendationEngine(graphiti_client=None)
        option = self._make_option(
            priority_score=80,
            supporting_evidence=["evidence-1", "evidence-2", "evidence-3"],
        )
        request = RecommendationRequest(analysis_result={})

        confidence = engine._calculate_confidence([option], request)

        option_count_factor = min(1.0, 1 / 3) * 0.2
        score_factor = 80 / 100 * 0.5
        evidence_factor = min(1.0, 3 / 3) * 0.3
        expected = round(option_count_factor + score_factor + evidence_factor, 2)
        assert confidence == expected
        assert evidence_factor > 0

    @pytest.mark.asyncio
    async def test_pipeline_injects_graphiti_client(self):
        """DecisionPipeline.decision_engine 必须注入 graphiti_client（非 None 当 GraphManager 可用）"""
        from unittest.mock import MagicMock, patch

        mock_graphiti = MagicMock()
        mock_gm = MagicMock()
        mock_gm.graph = mock_graphiti

        with patch("odap.infra.graph.graph_service.GraphManager", return_value=mock_gm):
            from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
            pipeline = DecisionPipeline()
            engine = pipeline.decision_engine

            assert engine is not None
            assert engine.graphiti is mock_graphiti
