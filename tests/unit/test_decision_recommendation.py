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
