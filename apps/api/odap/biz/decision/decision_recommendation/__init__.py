"""
Decision Recommendation 决策推荐模块

OADP 决策阶段核心组件：
- 基于理解结果（AnalysisResult）生成决策建议
- 与 OPA 策略校验集成
- RAG 增强推理支持
"""

from .engine import DecisionRecommendationEngine
from .models import (
    RecommendationRequest,
    DecisionRecommendation,
    DecisionOption,
    RiskAssessment,
    RiskFactor,
    DecisionFeedback,
    RecommendationType,
    RiskLevel,
    OptionStatus,
)

__all__ = [
    "DecisionRecommendationEngine",
    "RecommendationRequest",
    "DecisionRecommendation",
    "DecisionOption",
    "RiskAssessment",
    "RiskFactor",
    "DecisionFeedback",
    "RecommendationType",
    "RiskLevel",
    "OptionStatus",
]
