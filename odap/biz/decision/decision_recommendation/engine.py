"""
Decision Recommendation Engine 决策推荐引擎

OADP 决策阶段核心引擎：
- 接收理解阶段的分析结果
- 生成决策建议方案
- 与 OPA 策略校验集成
- 支持 RAG 增强推理
- 历史推荐经验沉淀到知识图谱
"""

import json
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from datetime import datetime, timezone

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
    from odap.infra.query.graph_write_proxy import GraphWriteProxy as GraphitiClient
    from odap.infra.opa import OPAManager

logger = logging.getLogger(__name__)


class DecisionRecommendationEngine:
    def __init__(
        self,
        graphiti_client: Optional["GraphitiClient"] = None,
        opa_manager: Optional["OPAManager"] = None,
    ):
        self.graphiti = graphiti_client
        self.opa = opa_manager
        self._initialized = True
        self._history: List[Dict[str, Any]] = []
        logger.info("DecisionRecommendationEngine 初始化完成")

    async def generate_recommendations(
        self,
        simulation_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        analysis_result = simulation_results.get("analysis_result", simulation_results)
        available_options = simulation_results.get("available_options", [])
        constraints = simulation_results.get("constraints", {})

        request = RecommendationRequest(
            analysis_result=analysis_result,
            available_options=available_options,
            constraints=constraints,
            context=simulation_results.get("context", {}),
        )

        recommendation = await self.generate_recommendation(request)

        self._history.append({
            "recommendation_id": recommendation.recommendation_id,
            "type": recommendation.type.value,
            "summary": recommendation.decision_summary,
            "confidence": recommendation.confidence,
            "option_count": len(recommendation.options),
            "created_at": recommendation.created_at.isoformat(),
        })

        if self.graphiti:
            try:
                await self.graphiti.add_episode(
                    name=f"recommendation_{recommendation.recommendation_id}",
                    episode_body=json.dumps({
                        "type": "decision_recommendation",
                        "recommendation_id": recommendation.recommendation_id,
                        "summary": recommendation.decision_summary,
                        "confidence": recommendation.confidence,
                        "recommended_option": recommendation.recommended_option.option_id if recommendation.recommended_option else None,
                    }, ensure_ascii=False),
                    source_description="DecisionRecommendationEngine: recommendation",
                    reference_time=datetime.now(timezone.utc),
                )
            except Exception as e:
                logger.warning(f"Failed to persist recommendation to graph: {e}")

        return {
            "recommendation_id": recommendation.recommendation_id,
            "type": recommendation.type.value,
            "options": [
                {
                    "option_id": o.option_id,
                    "name": o.name,
                    "description": o.description,
                    "priority_score": o.priority_score,
                    "expected_benefit": o.expected_benefit,
                    "expected_cost": o.expected_cost,
                    "estimated_success_rate": o.estimated_success_rate,
                    "status": o.status.value,
                    "rationale": o.rationale,
                }
                for o in recommendation.options
            ],
            "recommended_option_id": recommendation.recommended_option.option_id if recommendation.recommended_option else None,
            "decision_summary": recommendation.decision_summary,
            "confidence": recommendation.confidence,
        }

    async def assess_risks(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        options = recommendation.get("options", [])
        risk_results = []

        for option in options:
            factors = []

            success_rate = option.get("estimated_success_rate", 0.5)
            factors.append(RiskFactor(
                factor_name="execution_risk",
                score=50 * (1 - success_rate),
                weight=0.3,
                level=RiskLevel.MEDIUM,
                description="执行失败的可能性",
                mitigation="增加备选方案和回滚机制",
            ))

            cost = option.get("expected_cost", 50)
            factors.append(RiskFactor(
                factor_name="resource_risk",
                score=cost / 2,
                weight=0.25,
                level=RiskLevel.MEDIUM,
                description="资源消耗超预期风险",
                mitigation="预留资源缓冲",
            ))

            factors.append(RiskFactor(
                factor_name="time_risk",
                score=recommendation.get("constraints", {}).get("time_pressure", 50),
                weight=0.2,
                level=RiskLevel.MEDIUM,
                description="时间紧迫导致的决策风险",
                mitigation="制定时间缓冲计划",
            ))

            factors.append(RiskFactor(
                factor_name="external_risk",
                score=30,
                weight=0.25,
                level=RiskLevel.LOW,
                description="外部环境变化风险",
                mitigation="持续监控和快速响应",
            ))

            overall_score = sum(f.score * f.weight for f in factors)
            overall_level = self._score_to_level(overall_score)

            risk_results.append({
                "option_id": option.get("option_id", ""),
                "option_name": option.get("name", ""),
                "overall_score": round(overall_score, 2),
                "overall_level": overall_level.value,
                "factors": [
                    {
                        "name": f.factor_name,
                        "score": f.score,
                        "weight": f.weight,
                        "level": f.level.value,
                        "description": f.description,
                        "mitigation": f.mitigation,
                    }
                    for f in factors
                ],
                "mitigation_suggestions": [f.mitigation for f in factors if f.mitigation],
            })

        return {
            "recommendation_id": recommendation.get("recommendation_id", ""),
            "risk_assessments": risk_results,
            "highest_risk_option": max(risk_results, key=lambda r: r["overall_score"]) if risk_results else None,
            "lowest_risk_option": min(risk_results, key=lambda r: r["overall_score"]) if risk_results else None,
        }

    def rank_recommendations(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for rec in recommendations:
            options = rec.get("options", [])
            for opt in options:
                priority = opt.get("priority_score", 0)
                success = opt.get("estimated_success_rate", 0)
                cost = opt.get("expected_cost", 50)
                opt["_ranking_score"] = priority * 0.5 + success * 100 * 0.3 + (100 - cost) * 0.2

            sorted_options = sorted(options, key=lambda o: o.get("_ranking_score", 0), reverse=True)
            for i, opt in enumerate(sorted_options):
                opt.pop("_ranking_score", None)
                if i == 0:
                    opt["status"] = OptionStatus.RECOMMENDED.value
                else:
                    opt["status"] = OptionStatus.ALTERNATIVE.value

            rec["options"] = sorted_options
            if sorted_options:
                rec["recommended_option_id"] = sorted_options[0].get("option_id")

        return sorted(recommendations, key=lambda r: r.get("confidence", 0), reverse=True)

    def explain_recommendation(self, recommendation_id: str) -> Dict[str, Any]:
        for rec in self._history:
            if rec.get("recommendation_id") == recommendation_id:
                return {
                    "recommendation_id": recommendation_id,
                    "found": True,
                    "type": rec.get("type", ""),
                    "summary": rec.get("summary", ""),
                    "confidence": rec.get("confidence", 0),
                    "option_count": rec.get("option_count", 0),
                    "created_at": rec.get("created_at", ""),
                    "explanation": (
                        f"该推荐方案类型为{rec.get('type', '行动方案')}，"
                        f"置信度为{rec.get('confidence', 0):.0%}，"
                        f"共评估了{rec.get('option_count', 0)}个候选方案。"
                        f"决策摘要：{rec.get('summary', '无')}"
                    ),
                }

        return {
            "recommendation_id": recommendation_id,
            "explanation": "未找到该推荐记录",
            "found": False,
        }

    def get_history(self, ontology_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        history = self._history
        if ontology_id:
            history = [h for h in history if h.get("ontology_id") == ontology_id]
        return history[-limit:]

    async def generate_recommendation(
        self,
        request: RecommendationRequest,
    ) -> DecisionRecommendation:
        logger.info(f"生成决策推荐: {request.request_id}")

        options = await self._generate_options(request)

        evaluated_options = []
        for option in options:
            evaluated = await self._evaluate_option(option, request)
            evaluated_options.append(evaluated)

        validated_options = await self._validate_with_policy(evaluated_options, request)

        ranked_options = self._rank_options(validated_options)

        recommended = ranked_options[0] if ranked_options else None
        alternatives = ranked_options[1:]

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
        priority_score = await self._calculate_priority(option, request)
        option.priority_score = priority_score

        option.expected_benefit = await self._estimate_benefit(option, request)
        option.expected_cost = await self._estimate_cost(option, request)
        option.estimated_success_rate = await self._estimate_success_rate(option, request)
        option.risk_assessment = await self._assess_risk(option, request)
        option.rationale = await self._generate_rationale(option, request)

        if self.graphiti:
            option.supporting_evidence = await self._find_evidence(option, request)

        return option

    async def _calculate_priority(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> float:
        benefit_weight = 0.5
        cost_weight = 0.2
        success_weight = 0.3

        benefit_score = option.expected_benefit
        cost_score = 100 - option.expected_cost
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
        analysis = request.analysis_result
        base_benefit = analysis.get("value_score", 50)

        benefit_modifier = 1.0
        if "high_impact" in option.description.lower():
            benefit_modifier = 1.2

        return min(100, base_benefit * benefit_modifier)

    async def _estimate_cost(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> float:
        constraints = request.constraints

        if "max_cost" in constraints:
            return min(100, (option.expected_cost or 50) / constraints["max_cost"] * 100)

        return 50.0

    async def _estimate_success_rate(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> float:
        analysis = request.analysis_result
        base_rate = analysis.get("success_rate", 0.7)

        if request.constraints.get("strict_mode"):
            base_rate *= 0.8

        return min(1.0, max(0.0, base_rate))

    async def _assess_risk(
        self,
        option: DecisionOption,
        request: RecommendationRequest,
    ) -> RiskAssessment:
        factors = []

        execution_risk = RiskFactor(
            factor_name="execution_risk",
            score=50 * (1 - option.estimated_success_rate),
            weight=0.3,
            level=RiskLevel.MEDIUM,
            description="执行失败的可能性",
            mitigation="增加备选方案和回滚机制",
        )
        factors.append(execution_risk)

        resource_risk = RiskFactor(
            factor_name="resource_risk",
            score=option.expected_cost / 2,
            weight=0.25,
            level=RiskLevel.MEDIUM,
            description="资源消耗超预期风险",
            mitigation="预留资源缓冲",
        )
        factors.append(resource_risk)

        time_risk = RiskFactor(
            factor_name="time_risk",
            score=request.constraints.get("time_pressure", 50),
            weight=0.2,
            level=RiskLevel.MEDIUM,
            description="时间紧迫导致的决策风险",
            mitigation="制定时间缓冲计划",
        )
        factors.append(time_risk)

        external_risk = RiskFactor(
            factor_name="external_risk",
            score=30,
            weight=0.25,
            level=RiskLevel.LOW,
            description="外部环境变化风险",
            mitigation="持续监控和快速响应",
        )
        factors.append(external_risk)

        overall_score = sum(f.score * f.weight for f in factors)
        overall_level = self._score_to_level(overall_score)

        mitigations = [f.mitigation for f in factors if f.mitigation]

        return RiskAssessment(
            overall_score=round(overall_score, 2),
            overall_level=overall_level,
            factors=factors,
            mitigation_suggestions=mitigations,
        )

    def _score_to_level(self, score: float) -> RiskLevel:
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
        if not self.opa:
            logger.warning("OPA 管理器未配置，跳过策略校验")
            return options

        validated = []
        for option in options:
            opa_input = {
                "action": option.action,
                "parameters": option.parameters,
                "context": request.context,
                "constraints": request.constraints,
            }

            try:
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
                option.status = OptionStatus.PENDING

            validated.append(option)

        return validated

    def _rank_options(
        self,
        options: List[DecisionOption],
    ) -> List[DecisionOption]:
        valid = [o for o in options if o.status != OptionStatus.REJECTED]

        ranked = sorted(
            valid,
            key=lambda o: (
                o.priority_score,
                o.estimated_success_rate,
            ),
            reverse=True,
        )

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
        analysis = request.analysis_result
        reasons = []

        if "summary" in analysis:
            reasons.append(f"基于分析: {analysis['summary'][:50]}...")

        reasons.append(f"预期收益: {option.expected_benefit:.0f}/100")
        reasons.append(f"预估成功率: {option.estimated_success_rate:.0%}")

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
        try:
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
        if not options:
            return 0.0

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
        logger.info(
            f"记录决策反馈: {feedback.recommendation_id} -> "
            f"{feedback.executed_option_id} ({feedback.actual_outcome})"
        )

        if self.graphiti:
            try:
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


async def create_recommendation(
    analysis_result: Dict[str, Any],
    graphiti_client: Optional["GraphitiClient"] = None,
    opa_manager: Optional["OPAManager"] = None,
) -> DecisionRecommendation:
    engine = DecisionRecommendationEngine(
        graphiti_client=graphiti_client,
        opa_manager=opa_manager,
    )

    request = RecommendationRequest(analysis_result=analysis_result)

    return await engine.generate_recommendation(request)
