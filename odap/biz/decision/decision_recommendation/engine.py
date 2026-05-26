"""
Decision Recommendation Engine 决策推荐引擎

OADP 决策阶段核心引擎：
- 接收理解阶段的分析结果
- 生成决策建议方案
- 与 OPA 策略校验集成
- 支持 RAG 增强推理
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING
import logging
from datetime import datetime

from .models import (
    RecommendationRequest,
    DecisionRecommendation,
    DecisionOption,
    RiskAssessment,
    RiskFactor,
    RiskLevel,
    OptionStatus,
    RecommendationType,
    DecisionFeedback,
)

if TYPE_CHECKING:
    from odap.infra.graph import GraphitiClient
    from odap.infra.opa import OPAManager

logger = logging.getLogger(__name__)


class DecisionRecommendationEngine:
    """
    决策推荐引擎

    核心职责：
    1. 接收并验证分析结果
    2. 生成候选方案
    3. 评估方案优先级和风险
    4. 策略校验
    5. 输出推荐结论
    """

    def __init__(
        self,
        graphiti_client: Optional["GraphitiClient"] = None,
        opa_manager: Optional["OPAManager"] = None,
    ):
        """
        初始化决策推荐引擎

        Args:
            graphiti_client: Graphiti 客户端（用于 RAG 增强）
            opa_manager: OPA 管理器（用于策略校验）
        """
        self.graphiti = graphiti_client
        self.opa = opa_manager
        self._initialized = True
        logger.info("DecisionRecommendationEngine 初始化完成")

    async def generate_recommendation(
        self,
        request: RecommendationRequest,
    ) -> DecisionRecommendation:
        """
        生成决策推荐

        主要流程：
        1. 验证分析结果
        2. 生成或扩展候选方案
        3. 评估每个方案
        4. 策略校验
        5. 排序并输出推荐

        Args:
            request: 决策请求

        Returns:
            DecisionRecommendation: 决策推荐结果
        """
        logger.info(f"生成决策推荐: {request.request_id}")

        # 1. 生成或获取候选方案
        options = await self._generate_options(request)

        # 2. 评估每个方案
        evaluated_options = []
        for option in options:
            evaluated = await self._evaluate_option(option, request)
            evaluated_options.append(evaluated)

        # 3. 策略校验
        validated_options = await self._validate_with_policy(evaluated_options, request)

        # 4. 排序
        ranked_options = self._rank_options(validated_options)

        # 5. 生成推荐
        recommended = ranked_options[0] if ranked_options else None
        alternatives = ranked_options[1:]

        # 构建决策摘要
        summary = self._generate_summary(ranked_options, recommended, request)

        recommendation = DecisionRecommendation(
            request_id=request.request_id,
            type=self._infer_recommendation_type(request),
            options=ranked_options,
            recommended_option=recommended,
            alternatives=alternatives,
            decision_summary=summary,
            confidence=self._calculate_confidence(ranked_options, request),
        )

        logger.info(
            f"决策推荐生成完成: {recommendation.recommendation_id}, "
            f"候选方案: {len(ranked_options)}, "
            f"推荐方案: {recommended.option_id if recommended else 'None'}"
        )

        return recommendation

    async def _generate_options(
        self,
        request: RecommendationRequest,
    ) -> List[DecisionOption]:
        """
        生成候选方案

        如果请求中已有方案，直接使用；否则基于分析结果生成
        """
        if request.available_options:
            return [
                DecisionOption(
                    option_id=opt.get("id", f"opt-{i}"),
                    name=opt.get("name", "Unnamed Option"),
                    description=opt.get("description", ""),
                    action=opt.get("action", ""),
                    parameters=opt.get("parameters", {}),
                    rationale="用户提供方案",
                )
                for i, opt in enumerate(request.available_options)
            ]

        # 基于分析结果生成默认方案
        analysis = request.analysis_result
        return [
            DecisionOption(
                option_id=f"default-{request.request_id}",
                name="默认行动方案",
                description="基于分析结果生成的默认行动方案",
                action=analysis.get("recommended_action", "analyze"),
                parameters=analysis.get("action_parameters", {}),
                rationale="基于当前分析结果的默认推荐",
            )
        ]

    async def _evaluate_option(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> DecisionOption:
        """
        评估单个方案

        计算优先级评分、预期收益/成本、成功率
        """
        # 计算优先级评分（简单加权模型）
        priority_score = await self._calculate_priority(option, request)
        option.priority_score = priority_score

        # 计算预期收益
        option.expected_benefit = await self._estimate_benefit(option, request)

        # 计算预期成本
        option.expected_cost = await self._estimate_cost(option, request)

        # 评估成功率
        option.estimated_success_rate = await self._estimate_success_rate(
            option, request
        )

        # 风险评估
        option.risk_assessment = await self._assess_risk(option, request)

        # 生成理由
        option.rationale = await self._generate_rationale(option, request)

        # RAG 增强：查找支撑证据
        if self.graphiti:
            option.supporting_evidence = await self._find_evidence(option, request)

        return option

    async def _calculate_priority(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> float:
        """
        计算优先级评分

        基于收益、成本、成功率加权计算
        """
        benefit_weight = 0.5
        cost_weight = 0.2
        success_weight = 0.3

        benefit_score = option.expected_benefit
        cost_score = 100 - option.expected_cost  # 成本越低越好
        success_score = option.estimated_success_rate * 100

        priority = (
            benefit_weight * benefit_score +
            cost_weight * cost_score +
            success_weight * success_score
        )

        return round(priority, 2)

    async def _estimate_benefit(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> float:
        """估算预期收益"""
        # 基于分析结果中的价值评估
        analysis = request.analysis_result
        base_benefit = analysis.get("value_score", 50)

        # 考虑方案特定因素
        benefit_modifier = 1.0
        if "high_impact" in option.description.lower():
            benefit_modifier = 1.2

        return min(100, base_benefit * benefit_modifier)

    async def _estimate_cost(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> float:
        """估算预期成本"""
        # 基于约束条件
        constraints = request.constraints

        if "max_cost" in constraints:
            return min(100, (option.expected_cost or 50) / constraints["max_cost"] * 100)

        return 50.0  # 默认中等成本

    async def _estimate_success_rate(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> float:
        """估算成功率"""
        # 基于历史数据或默认值
        analysis = request.analysis_result
        base_rate = analysis.get("success_rate", 0.7)

        # 考虑约束条件
        if request.constraints.get("strict_mode"):
            base_rate *= 0.8

        return min(1.0, max(0.0, base_rate))

    async def _assess_risk(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> RiskAssessment:
        """
        评估方案风险

        多维度风险分析
        """
        factors = []

        # 1. 执行风险
        execution_risk = RiskFactor(
            factor_name="execution_risk",
            score=50 * (1 - option.estimated_success_rate),
            weight=0.3,
            level=RiskLevel.MEDIUM,
            description="执行失败的可能性",
            mitigation="增加备选方案和回滚机制",
        )
        factors.append(execution_risk)

        # 2. 资源风险
        resource_risk = RiskFactor(
            factor_name="resource_risk",
            score=option.expected_cost / 2,
            weight=0.25,
            level=RiskLevel.MEDIUM,
            description="资源消耗超预期风险",
            mitigation="预留资源缓冲",
        )
        factors.append(resource_risk)

        # 3. 时间风险
        time_risk = RiskFactor(
            factor_name="time_risk",
            score=request.constraints.get("time_pressure", 50),
            weight=0.2,
            level=RiskLevel.MEDIUM,
            description="时间紧迫导致的决策风险",
            mitigation="制定时间缓冲计划",
        )
        factors.append(time_risk)

        # 4. 外部风险
        external_risk = RiskFactor(
            factor_name="external_risk",
            score=30,  # 简化处理
            weight=0.25,
            level=RiskLevel.LOW,
            description="外部环境变化风险",
            mitigation="持续监控和快速响应",
        )
        factors.append(external_risk)

        # 计算综合风险评分
        overall_score = sum(f.score * f.weight for f in factors)
        overall_level = self._score_to_level(overall_score)

        # 生成缓解建议
        mitigations = [f.mitigation for f in factors if f.mitigation]

        return RiskAssessment(
            overall_score=round(overall_score, 2),
            overall_level=overall_level,
            factors=factors,
            mitigation_suggestions=mitigations,
        )

    def _score_to_level(self, score: float) -> RiskLevel:
        """将评分转换为风险等级"""
        if score < 30:
            return RiskLevel.LOW
        elif score < 60:
            return RiskLevel.MEDIUM
        elif score < 80:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    async def _validate_with_policy(
        self,
        options: List[DecisionOption],
        request: RecommendationRequest,
    ) -> List[DecisionOption]:
        """
        OPA 策略校验

        检查方案是否符合组织策略
        """
        if not self.opa:
            logger.warning("OPA 管理器未配置，跳过策略校验")
            return options

        validated = []
        for option in options:
            # 构造 OPA 请求
            opa_input = {
                "action": option.action,
                "parameters": option.parameters,
                "context": request.context,
                "constraints": request.constraints,
            }

            try:
                # 调用 OPA 校验
                result = await self.opa.validate(opa_input)

                if result.allowed:
                    if option.estimated_success_rate >= 0.5:
                        option.status = OptionStatus.RECOMMENDED
                    else:
                        option.status = OptionStatus.ALTERNATIVE
                else:
                    option.status = OptionStatus.REJECTED
                    option.rationale += f" [策略拒绝: {result.reason}]"

            except Exception as e:
                logger.error(f"OPA 校验失败: {e}")
                # 校验失败时保留方案但标记
                option.status = OptionStatus.PENDING

            validated.append(option)

        return validated

    def _rank_options(
        self,
        options: List[DecisionOption],
    ) -> List[DecisionOption]:
        """
        方案排序

        按优先级评分降序排列
        """
        # 过滤已拒绝的方案
        valid = [o for o in options if o.status != OptionStatus.REJECTED]

        # 按优先级排序
        ranked = sorted(
            valid,
            key=lambda o: (
                o.priority_score,
                o.estimated_success_rate,
            ),
            reverse=True,
        )

        # 更新状态
        for i, option in enumerate(ranked):
            if i == 0:
                option.status = OptionStatus.RECOMMENDED
            else:
                option.status = OptionStatus.ALTERNATIVE

        return ranked

    async def _generate_rationale(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> str:
        """生成决策理由"""
        analysis = request.analysis_result
        reasons = []

        # 基于分析结果
        if "summary" in analysis:
            reasons.append(f"基于分析: {analysis['summary'][:50]}...")

        # 基于评估指标
        reasons.append(f"预期收益: {option.expected_benefit:.0f}/100")
        reasons.append(f"预估成功率: {option.estimated_success_rate:.0%}")

        # 基于风险评估
        if option.risk_assessment:
            reasons.append(
                f"综合风险等级: {option.risk_assessment.overall_level.value}"
            )

        return "; ".join(reasons)

    async def _find_evidence(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> List[str]:
        """RAG 增强：查找支撑证据"""
        try:
            # 使用 Graphiti 进行相似性搜索
            query = f"{option.name} {option.description}"
            results = await self.graphiti.search_episodes(
                query=query,
                limit=3,
            )
            return [r.entity_id for r in results] if results else []
        except Exception as e:
            logger.warning(f"RAG 查询失败: {e}")
            return []

    def _infer_recommendation_type(
        self,
        request: RecommendationRequest,
    ) -> RecommendationType:
        """推断推荐类型"""
        context = request.context

        if "action_plan" in context:
            return RecommendationType.ACTION_PLAN
        elif "resource_allocation" in context:
            return RecommendationType.RESOURCE_ALLOCATION
        elif "priority_ranking" in context:
            return RecommendationType.PRIORITY_RANKING
        elif "alternative_selection" in context:
            return RecommendationType.ALTERNATIVE_SELECTION
        else:
            return RecommendationType.ACTION_PLAN

    def _generate_summary(
        self,
        options: List[DecisionOption],
        recommended: Optional[DecisionOption],
        request: RecommendationRequest,
    ) -> str:
        """生成决策摘要"""
        if not options:
            return "无可用方案，请提供更多上下文信息。"

        if not recommended:
            return "所有候选方案均未通过策略校验或风险评估。"

        return (
            f"推荐执行「{recommended.name}」，"
            f"优先级评分 {recommended.priority_score:.1f}/100，"
            f"预估成功率 {recommended.estimated_success_rate:.0%}，"
            f"综合风险 {recommended.risk_assessment.overall_level.value if recommended.risk_assessment else '未知'}。"
        )

    def _calculate_confidence(
        self,
        options: List[DecisionOption],
        request: RecommendationRequest,
    ) -> float:
        """计算决策置信度"""
        if not options:
            return 0.0

        # 基于方案数量、推荐方案评分、证据充分度
        option_count_factor = min(1.0, len(options) / 3) * 0.2
        score_factor = (
            options[0].priority_score / 100 * 0.5 if options else 0
        )
        evidence_factor = (
            min(1.0, len(options[0].supporting_evidence) / 3) * 0.3
            if options else 0
        )

        confidence = option_count_factor + score_factor + evidence_factor

        return round(min(1.0, max(0.0, confidence)), 2)

    async def record_feedback(
        self,
        feedback: DecisionFeedback,
    ) -> bool:
        """
        记录决策反馈

        用于 OADP 闭环反馈机制

        Args:
            feedback: 决策反馈

        Returns:
            bool: 是否记录成功
        """
        logger.info(
            f"记录决策反馈: {feedback.recommendation_id} -> "
            f"{feedback.executed_option_id} ({feedback.actual_outcome})"
        )

        # 如果有 Graphiti，可以将反馈写入知识图谱
        if self.graphiti:
            try:
                # 创建反馈事件
                await self.graphiti.add_episode(
                    name=f"decision_feedback_{feedback.recommendation_id}",
                    episode_body=json.dumps({
                        "type": "decision_feedback",
                        "recommendation_id": feedback.recommendation_id,
                        "executed_option": feedback.executed_option_id,
                        "outcome": feedback.actual_outcome,
                        "lessons": feedback.lessons_learned,
                        "timestamp": feedback.feedback_timestamp.isoformat(),
                    }, ensure_ascii=False),
                    source_description="DecisionRecommendationEngine: feedback",
                    reference_time=datetime.now(timezone.utc),
                )
                logger.info("反馈已写入知识图谱")
                return True
            except Exception as e:
                logger.error(f"反馈写入失败: {e}")
                return False

        return True


# 便捷函数
async def create_recommendation(
    analysis_result: Dict[str, Any],
    graphiti_client: Optional["GraphitiClient"] = None,
    opa_manager: Optional["OPAManager"] = None,
) -> DecisionRecommendation:
    """
    创建决策推荐的便捷函数

    Args:
        analysis_result: 理解阶段的分析结果
        graphiti_client: Graphiti 客户端
        opa_manager: OPA 管理器

    Returns:
        DecisionRecommendation: 决策推荐结果
    """
    engine = DecisionRecommendationEngine(
        graphiti_client=graphiti_client,
        opa_manager=opa_manager,
    )

    request = RecommendationRequest(analysis_result=analysis_result)

    return await engine.generate_recommendation(request)
