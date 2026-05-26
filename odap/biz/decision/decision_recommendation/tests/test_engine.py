"""
Decision Recommendation Engine 测试

测试 OADP 决策阶段核心功能

注意：异步测试需要安装 pytest-asyncio
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from odap.biz.decision.decision_recommendation import (
    DecisionRecommendationEngine,
    RecommendationRequest,
    DecisionRecommendation,
    DecisionOption,
    RiskAssessment,
    RiskFactor,
    DecisionFeedback,
    RecommendationType,
    OptionStatus,
    RiskLevel,
)


class TestDecisionRecommendationEngine:
    """决策推荐引擎测试"""

    @pytest.fixture
    def engine(self):
        """创建引擎实例（无外部依赖）"""
        return DecisionRecommendationEngine(
            graphiti_client=None,
            opa_manager=None,
        )

    @pytest.fixture
    def sample_request(self):
        """创建示例请求"""
        return RecommendationRequest(
            request_id="test-001",
            analysis_result={
                "summary": "测试分析结果",
                "value_score": 75,
                "success_rate": 0.8,
                "recommended_action": "proceed",
            },
            available_options=[
                {
                    "id": "opt-1",
                    "name": "方案A",
                    "description": "高风险高收益方案",
                    "action": "execute_a",
                },
                {
                    "id": "opt-2",
                    "name": "方案B",
                    "description": "稳健方案",
                    "action": "execute_b",
                },
            ],
            constraints={
                "max_cost": 100,
                "time_pressure": 40,
            },
        )

    @pytest.mark.asyncio
    async def test_generate_recommendation_basic(self, engine, sample_request):
        """测试基本推荐生成"""
        result = await engine.generate_recommendation(sample_request)

        assert isinstance(result, DecisionRecommendation)
        assert result.request_id == "test-001"
        assert len(result.options) == 2
        assert result.recommended_option is not None
        assert result.type == RecommendationType.ACTION_PLAN

    @pytest.mark.asyncio
    async def test_generate_recommendation_no_options(self, engine):
        """测试无候选方案时的默认生成"""
        request = RecommendationRequest(
            request_id="test-002",
            analysis_result={
                "recommended_action": "analyze",
                "action_parameters": {"depth": "shallow"},
            },
            available_options=[],  # 无候选方案
        )

        result = await engine.generate_recommendation(request)

        assert len(result.options) == 1
        assert result.options[0].name == "默认行动方案"

    @pytest.mark.asyncio
    async def test_priority_calculation(self, engine):
        """测试优先级评分计算"""
        request = RecommendationRequest(
            analysis_result={
                "value_score": 80,
                "success_rate": 0.9,
            },
            available_options=[
                {
                    "id": "opt-high",
                    "name": "高收益方案",
                    "description": "high_impact solution",
                    "action": "execute",
                },
            ],
        )

        result = await engine.generate_recommendation(request)
        option = result.options[0]

        assert option.priority_score > 0
        assert option.expected_benefit > 0
        assert 0 <= option.estimated_success_rate <= 1

    @pytest.mark.asyncio
    async def test_risk_assessment(self, engine):
        """测试风险评估"""
        request = RecommendationRequest(
            analysis_result={"success_rate": 0.7},
            available_options=[
                {
                    "id": "opt-1",
                    "name": "测试方案",
                    "action": "test",
                },
            ],
            constraints={"time_pressure": 60},
        )

        result = await engine.generate_recommendation(request)
        option = result.options[0]

        assert option.risk_assessment is not None
        assert isinstance(option.risk_assessment, RiskAssessment)
        assert option.risk_assessment.overall_score >= 0
        assert len(option.risk_assessment.factors) > 0

    @pytest.mark.asyncio
    async def test_option_ranking(self, engine):
        """测试方案排序"""
        request = RecommendationRequest(
            analysis_result={"value_score": 50, "success_rate": 0.5},
            available_options=[
                {"id": "opt-1", "name": "低优先级", "action": "a"},
                {"id": "opt-2", "name": "中优先级", "action": "b"},
                {"id": "opt-3", "name": "高优先级", "action": "c"},
            ],
        )

        result = await engine.generate_recommendation(request)

        # 第一个应该是推荐方案
        assert result.recommended_option.status == OptionStatus.RECOMMENDED

        # 后续应该是备选
        for alt in result.alternatives:
            assert alt.status == OptionStatus.ALTERNATIVE

    @pytest.mark.asyncio
    async def test_confidence_calculation(self, engine):
        """测试置信度计算"""
        # 多方案 + 多证据 = 高置信度
        request = RecommendationRequest(
            analysis_result={"value_score": 90},
            available_options=[
                {"id": "opt-1", "name": "方案1", "action": "a"},
                {"id": "opt-2", "name": "方案2", "action": "b"},
                {"id": "opt-3", "name": "方案3", "action": "c"},
            ],
        )

        result = await engine.generate_recommendation(request)

        assert 0 <= result.confidence <= 1

    @pytest.mark.asyncio
    async def test_decision_summary_generation(self, engine):
        """测试决策摘要生成"""
        request = RecommendationRequest(
            analysis_result={"summary": "测试摘要内容"},
            available_options=[
                {"id": "opt-1", "name": "测试方案", "action": "test"},
            ],
        )

        result = await engine.generate_recommendation(request)

        assert len(result.decision_summary) > 0
        assert "测试方案" in result.decision_summary

    @pytest.mark.asyncio
    async def test_record_feedback(self, engine):
        """测试反馈记录"""
        feedback = DecisionFeedback(
            recommendation_id="rec-001",
            executed_option_id="opt-1",
            execution_result={"status": "success"},
            actual_outcome="success",
            lessons_learned=["Lesson 1"],
            actor_id="user-1",
        )

        # 无 Graphiti 时也应正常工作
        result = await engine.record_feedback(feedback)
        assert result is True


class TestDecisionModels:
    """决策模型测试"""

    def test_recommendation_request_validation(self):
        """测试请求模型验证"""
        request = RecommendationRequest(
            analysis_result={"key": "value"},
        )

        assert request.request_id.startswith("rec-")
        assert request.analysis_result["key"] == "value"
        assert request.timestamp is not None

    def test_decision_option_model(self):
        """测试决策选项模型"""
        option = DecisionOption(
            option_id="opt-001",
            name="测试选项",
            action="test_action",
            rationale="测试理由",
        )

        assert option.option_id == "opt-001"
        assert option.status == OptionStatus.PENDING  # 默认状态
        assert option.priority_score == 0  # 默认值
        assert option.description == ""  # 默认空描述

    def test_risk_assessment_model(self):
        """测试风险评估模型"""
        assessment = RiskAssessment(
            overall_score=45.5,
            overall_level=RiskLevel.MEDIUM,
            factors=[],
        )

        assert assessment.overall_score == 45.5
        assert assessment.overall_level == RiskLevel.MEDIUM

    def test_decision_feedback_model(self):
        """测试反馈模型"""
        feedback = DecisionFeedback(
            recommendation_id="rec-001",
            executed_option_id="opt-001",
            actual_outcome="success",
            actor_id="user-1",
        )

        assert feedback.recommendation_id == "rec-001"
        assert feedback.feedback_timestamp is not None


class TestRecommendationTypeInference:
    """推荐类型推断测试"""

    @pytest.fixture
    def engine(self):
        return DecisionRecommendationEngine()

    def test_infer_action_plan(self, engine):
        """测试行动方案类型推断"""
        request = RecommendationRequest(
            analysis_result={},  # 必填字段
            context={"action_plan": {}},
        )
        result = engine._infer_recommendation_type(request)
        assert result == RecommendationType.ACTION_PLAN

    def test_infer_resource_allocation(self, engine):
        """测试资源配置类型推断"""
        request = RecommendationRequest(
            analysis_result={},
            context={"resource_allocation": {}},
        )
        result = engine._infer_recommendation_type(request)
        assert result == RecommendationType.RESOURCE_ALLOCATION

    def test_infer_priority_ranking(self, engine):
        """测试优先级排序类型推断"""
        request = RecommendationRequest(
            analysis_result={},
            context={"priority_ranking": {}},
        )
        result = engine._infer_recommendation_type(request)
        assert result == RecommendationType.PRIORITY_RANKING

    def test_infer_default(self, engine):
        """测试默认类型"""
        request = RecommendationRequest(analysis_result={}, context={})
        result = engine._infer_recommendation_type(request)
        assert result == RecommendationType.ACTION_PLAN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
