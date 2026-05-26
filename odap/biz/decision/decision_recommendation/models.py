"""
Decision Recommendation 数据模型

定义 OADP 决策阶段的核心数据结构
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class RecommendationType(str, Enum):
    """推荐类型"""
    ACTION_PLAN = "action_plan"           # 行动方案
    RESOURCE_ALLOCATION = "resource_allocation"  # 资源配置
    PRIORITY_RANKING = "priority_ranking"  # 优先级排序
    ALTERNATIVE_SELECTION = "alternative_selection"  # 备选方案


class RiskLevel(str, Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OptionStatus(str, Enum):
    """方案状态"""
    RECOMMENDED = "recommended"     # 推荐
    ALTERNATIVE = "alternative"     # 备选
    REJECTED = "rejected"          # 已拒绝
    PENDING = "pending"            # 待评估


class RecommendationRequest(BaseModel):
    """
    决策推荐请求

    包含理解阶段产出的分析结果，用于生成决策建议
    """
    request_id: str = Field(
        default_factory=lambda: f"rec-{uuid.uuid4().hex[:8]}",
        description="请求追踪ID"
    )
    analysis_result: Dict[str, Any] = Field(
        description="理解阶段的分析结果"
    )
    available_options: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="可用的候选方案"
    )
    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="决策约束条件"
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="额外上下文信息"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="请求时间"
    )


class RiskFactor(BaseModel):
    """
    风险因子

    描述单个风险维度的评估结果
    """
    factor_name: str = Field(description="风险因子名称")
    score: float = Field(ge=0, le=100, description="风险评分 0-100")
    weight: float = Field(ge=0, le=1, description="权重 0-1")
    level: RiskLevel = Field(description="风险等级")
    description: str = Field(description="风险描述")
    mitigation: Optional[str] = Field(None, description="缓解建议")


class RiskAssessment(BaseModel):
    """
    风险评估结果

    多维度风险综合评估
    """
    overall_score: float = Field(ge=0, le=100, description="综合风险评分 0-100")
    overall_level: RiskLevel = Field(description="综合风险等级")
    factors: List[RiskFactor] = Field(default_factory=list, description="风险因子列表")
    mitigation_suggestions: List[str] = Field(
        default_factory=list,
        description="缓解建议列表"
    )
    assessed_at: datetime = Field(
        default_factory=datetime.now,
        description="评估时间"
    )


class DecisionOption(BaseModel):
    """
    决策选项

    单个候选方案及其评估结果
    """
    option_id: str = Field(description="方案ID")
    name: str = Field(description="方案名称")
    description: str = Field(default="", description="方案描述")
    action: str = Field(description="执行动作")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="动作参数"
    )

    # 评估指标
    priority_score: float = Field(
        default=0,
        ge=0, le=100,
        description="优先级评分 0-100"
    )
    expected_benefit: float = Field(
        default=0,
        ge=0, le=100,
        description="预期收益 0-100"
    )
    expected_cost: float = Field(
        default=0,
        ge=0, le=100,
        description="预期成本 0-100"
    )
    estimated_success_rate: float = Field(
        default=0.0,
        ge=0, le=1,
        description="预估成功率 0-1"
    )

    # 风险评估
    risk_assessment: Optional[RiskAssessment] = Field(
        None,
        description="风险评估结果"
    )

    # 状态和理由
    status: OptionStatus = Field(
        default=OptionStatus.PENDING,
        description="方案状态"
    )
    rationale: str = Field(description="决策理由")
    supporting_evidence: List[str] = Field(
        default_factory=list,
        description="支撑证据（知识图谱实体ID列表）"
    )
    alternatives: List[str] = Field(
        default_factory=list,
        description="备选方案ID列表"
    )


class DecisionRecommendation(BaseModel):
    """
    决策推荐结果

    包含多个候选方案及推荐结论
    """
    recommendation_id: str = Field(
        default_factory=lambda: f"rec-{uuid.uuid4().hex[:8]}",
        description="推荐ID"
    )
    request_id: str = Field(description="关联请求ID")
    type: RecommendationType = Field(description="推荐类型")

    # 候选方案列表
    options: List[DecisionOption] = Field(
        default_factory=list,
        description="候选方案列表"
    )

    # 推荐方案
    recommended_option: Optional[DecisionOption] = Field(
        None,
        description="推荐方案"
    )
    alternatives: List[DecisionOption] = Field(
        default_factory=list,
        description="备选方案列表"
    )

    # 综合评估
    decision_summary: str = Field(description="决策摘要")
    confidence: float = Field(
        ge=0, le=1,
        description="决策置信度 0-1"
    )

    # 审计信息
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="过期时间（用于临时决策）"
    )


class DecisionFeedback(BaseModel):
    """
    决策反馈

    用于 OADP 闭环反馈机制
    """
    recommendation_id: str = Field(description="推荐ID")
    executed_option_id: str = Field(description="执行的方案ID")

    # 执行结果
    execution_result: Dict[str, Any] = Field(
        default_factory=dict,
        description="执行结果"
    )
    actual_outcome: str = Field(description="实际结果（成功/失败/部分成功）")
    deviation_from_expected: Optional[float] = Field(
        None,
        description="与预期的偏差"
    )

    # 反馈信息
    lessons_learned: List[str] = Field(
        default_factory=list,
        description="经验教训"
    )
    improvement_suggestions: List[str] = Field(
        default_factory=list,
        description="改进建议"
    )

    # 元数据
    feedback_timestamp: datetime = Field(
        default_factory=datetime.now,
        description="反馈时间"
    )
    actor_id: str = Field(description="反馈者ID")
