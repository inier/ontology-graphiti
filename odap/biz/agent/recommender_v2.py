"""
决策推荐引擎 v2 - Decision Recommendation Engine
WR-14: 决策推荐引擎 (StrikePlan + 风险评估 + 多策略对比 + OPA校验)

功能：
- StrikePlan 生成
- 风险评估模型
- 多策略对比
- OPA 策略校验
- 决策解释生成
"""

import sys
import os
import json
import time
import threading
import hashlib
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class StrategyType(Enum):
    """策略类型"""
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    BALANCED = "balanced"
    COVERT = "covert"
    OVERWHELMING = "overwhelming"


class RecommendationStatus(Enum):
    """推荐状态"""
    PENDING = "pending"
    EVALUATED = "evaluated"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


@dataclass
class RiskFactor:
    """风险因子"""
    name: str
    description: str
    weight: float
    value: float
    impact: str


@dataclass
class RiskAssessment:
    """风险评估结果"""
    overall_risk: RiskLevel
    risk_score: float
    risk_factors: List[RiskFactor]
    civilian_risk: float
    collateral_damage_probability: float
    escalation_potential: float
    recommendations: List[str]


@dataclass
class StrategyComparison:
    """策略对比"""
    strategy_id: str
    strategy_name: str
    strategy_type: StrategyType
    effectiveness_score: float
    risk_assessment: RiskAssessment
    resource_requirements: Dict[str, float]
    timeline: str
    success_probability: float
    pros: List[str]
    cons: List[str]


@dataclass
class StrikePlan:
    """打击计划"""
    plan_id: str
    name: str
    description: str
    objective: str
    target_id: str
    target_name: str
    target_type: str
    strategy_type: StrategyType
    phases: List[Dict[str, Any]]
    resources: Dict[str, Any]
    timeline: Dict[str, str]
    expected_outcome: str
    fallback_plan: Optional[str] = None
    authorization_required: bool = True
    estimated_duration_minutes: int = 30
    risk_assessment: Optional[RiskAssessment] = None


@dataclass
class DecisionRecommendation:
    """决策推荐"""
    recommendation_id: str
    title: str
    description: str
    situation_summary: str
    strike_plan: StrikePlan
    risk_assessment: RiskAssessment
    alternatives: List[StrategyComparison]
    recommended_strategy: str
    reasoning: List[str]
    supporting_intelligence: List[Dict]
    constraints: List[str]
    status: RecommendationStatus
    created_at: str
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    opa_verified: bool = False
    opa_verification_result: Optional[Dict] = None


class RiskAssessmentModel:
    """风险评估模型"""

    def __init__(self):
        self._risk_weights = {
            "civilian_proximity": 0.3,
            "collateral_damage": 0.25,
            "escalation": 0.2,
            "resource_constraint": 0.15,
            "time_pressure": 0.1
        }
        self._risk_thresholds = {
            RiskLevel.CRITICAL: 0.8,
            RiskLevel.HIGH: 0.6,
            RiskLevel.MEDIUM: 0.4,
            RiskLevel.LOW: 0.2,
            RiskLevel.NEGLIGIBLE: 0.0
        }

    def assess_risk(self, situation: Dict[str, Any],
                   target: Dict[str, Any],
                   civilians_nearby: List[Dict] = None) -> RiskAssessment:
        """
        评估风险

        Args:
            situation: 当前态势
            target: 目标信息
            civilians_nearby: 附近平民设施

        Returns:
            RiskAssessment
        """
        risk_factors = []

        civilian_risk = self._assess_civilian_risk(target, civilians_nearby)
        risk_factors.append(RiskFactor(
            name="civilian_risk",
            description="平民风险",
            weight=self._risk_weights["civilian_proximity"],
            value=civilian_risk,
            impact="negative" if civilian_risk > 0.3 else "neutral"
        ))

        collateral_prob = self._assess_collateral_damage(target, civilians_nearby)
        risk_factors.append(RiskFactor(
            name="collateral_damage",
            description="附带损伤概率",
            weight=self._risk_weights["collateral_damage"],
            value=collateral_prob,
            impact="negative" if collateral_prob > 0.2 else "neutral"
        ))

        escalation = self._assess_escalation_potential(situation, target)
        risk_factors.append(RiskFactor(
            name="escalation",
            description="升级潜力",
            weight=self._risk_weights["escalation"],
            value=escalation,
            impact="negative" if escalation > 0.5 else "neutral"
        ))

        resource_risk = self._assess_resource_constraint(situation)
        risk_factors.append(RiskFactor(
            name="resource",
            description="资源约束",
            weight=self._risk_weights["resource_constraint"],
            value=resource_risk,
            impact="negative" if resource_risk > 0.7 else "neutral"
        ))

        time_risk = self._assess_time_pressure(situation)
        risk_factors.append(RiskFactor(
            name="time",
            description="时间压力",
            weight=self._risk_weights["time_pressure"],
            value=time_risk,
            impact="negative" if time_risk > 0.6 else "neutral"
        ))

        overall_score = sum(f.value * f.weight for f in risk_factors)
        overall_risk = self._calculate_overall_risk(overall_score)

        recommendations = self._generate_risk_recommendations(risk_factors, overall_risk)

        return RiskAssessment(
            overall_risk=overall_risk,
            risk_score=overall_score,
            risk_factors=risk_factors,
            civilian_risk=civilian_risk,
            collateral_damage_probability=collateral_prob,
            escalation_potential=escalation,
            recommendations=recommendations
        )

    def _assess_civilian_risk(self, target: Dict, civilians: List[Dict]) -> float:
        """评估平民风险"""
        if not civilians:
            return 0.0

        target_area = target.get("properties", {}).get("area", "")

        civilians_in_area = [c for c in civilians if c.get("properties", {}).get("area") == target_area]

        if len(civilians_in_area) > 10:
            return 0.9
        elif len(civilians_in_area) > 5:
            return 0.6
        elif len(civilians_in_area) > 0:
            return 0.3
        return 0.1

    def _assess_collateral_damage(self, target: Dict, civilians: List[Dict]) -> float:
        """评估附带损伤概率"""
        if not civilians:
            return 0.0

        target_type = target.get("properties", {}).get("type", "")
        target_power = target.get("properties", {}).get("power_rating", 0)

        if target_power > 1000:
            return 0.4

        return 0.1

    def _assess_escalation_potential(self, situation: Dict, target: Dict) -> float:
        """评估升级潜力"""
        threat_level = situation.get("threat_level", "low")

        if threat_level == "critical":
            return 0.8
        elif threat_level == "high":
            return 0.6
        elif threat_level == "medium":
            return 0.4
        return 0.2

    def _assess_resource_constraint(self, situation: Dict) -> float:
        """评估资源约束"""
        available = situation.get("available_resources", {})
        required = situation.get("required_resources", {})

        if not required:
            return 0.0

        utilization = {
            k: required.get(k, 0) / max(available.get(k, 1), 1)
            for k in required.keys()
        }

        return max(utilization.values()) if utilization else 0.0

    def _assess_time_pressure(self, situation: Dict) -> float:
        """评估时间压力"""
        time_available = situation.get("time_available_minutes", 60)
        time_required = situation.get("time_required_minutes", 30)

        if time_available < time_required:
            return 0.9
        elif time_available < time_required * 1.5:
            return 0.6
        return 0.2

    def _calculate_overall_risk(self, score: float) -> RiskLevel:
        """计算整体风险等级"""
        for level, threshold in sorted(self._risk_thresholds.items(),
                                      key=lambda x: x[1], reverse=True):
            if score >= threshold:
                return level
        return RiskLevel.NEGLIGIBLE

    def _generate_risk_recommendations(self, factors: List[RiskFactor],
                                     overall: RiskLevel) -> List[str]:
        """生成风险建议"""
        recommendations = []

        for factor in factors:
            if factor.value > 0.6 and factor.impact == "negative":
                if factor.name == "civilian_risk":
                    recommendations.append("建议增加目标确认程序以降低平民风险")
                elif factor.name == "collateral_damage":
                    recommendations.append("建议使用精确制导武器减少附带损伤")
                elif factor.name == "escalation":
                    recommendations.append("建议准备外交渠道以防局势升级")

        if overall in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
            recommendations.insert(0, "此行动风险较高，需要上级额外授权")

        return recommendations


class StrategyGenerator:
    """策略生成器"""

    def __init__(self):
        self._strategy_templates = {
            StrategyType.AGGRESSIVE: {
                "name": "突击策略",
                "description": "快速、强力打击，优先考虑速度",
                "effectiveness_base": 0.8,
                "risk_base": 0.6
            },
            StrategyType.DEFENSIVE: {
                "name": "防御策略",
                "description": "稳扎稳打，优先考虑安全",
                "effectiveness_base": 0.6,
                "risk_base": 0.3
            },
            StrategyType.BALANCED: {
                "name": "平衡策略",
                "description": "权衡效果与风险",
                "effectiveness_base": 0.7,
                "risk_base": 0.4
            },
            StrategyType.COVERT: {
                "name": "隐秘策略",
                "description": "低调行动，减少暴露",
                "effectiveness_base": 0.5,
                "risk_base": 0.2
            },
            StrategyType.OVERWHELMING: {
                "name": "压倒性策略",
                "description": "全力投入确保成功",
                "effectiveness_base": 0.95,
                "risk_base": 0.8
            }
        }

    def generate_strategies(self, situation: Dict[str, Any],
                          target: Dict[str, Any],
                          risk_assessment: RiskAssessment) -> List[StrategyComparison]:
        """生成策略对比"""
        strategies = []

        for strategy_type in StrategyType:
            comparison = self._generate_strategy_comparison(
                strategy_type, situation, target, risk_assessment
            )
            strategies.append(comparison)

        return sorted(strategies, key=lambda s: s.effectiveness_score, reverse=True)

    def _generate_strategy_comparison(self, strategy_type: StrategyType,
                                    situation: Dict,
                                    target: Dict,
                                    risk: RiskAssessment) -> StrategyComparison:
        """生成单个策略对比"""
        template = self._strategy_templates[strategy_type]

        effectiveness = template["effectiveness_base"]
        if risk.overall_risk == RiskLevel.HIGH:
            effectiveness *= 0.7
        elif risk.overall_risk == RiskLevel.LOW:
            effectiveness *= 1.1

        risk_score = template["risk_base"]
        if risk.civilian_risk > 0.5:
            risk_score += 0.2

        resources = self._calculate_resource_requirements(strategy_type, target)

        timeline = self._calculate_timeline(strategy_type)

        success_prob = effectiveness * (1 - risk_score)

        pros, cons = self._generate_pros_cons(strategy_type, target, risk)

        return StrategyComparison(
            strategy_id=str(uuid.uuid4()),
            strategy_name=template["name"],
            strategy_type=strategy_type,
            effectiveness_score=min(1.0, effectiveness),
            risk_assessment=risk,
            resource_requirements=resources,
            timeline=timeline,
            success_probability=max(0, min(1, success_prob)),
            pros=pros,
            cons=cons
        )

    def _calculate_resource_requirements(self, strategy: StrategyType,
                                        target: Dict) -> Dict[str, float]:
        """计算资源需求"""
        base = {
            "personnel": 10,
            "aircraft": 2,
            "ammunition": 100,
            "fuel": 500
        }

        multiplier = {
            StrategyType.AGGRESSIVE: 1.2,
            StrategyType.DEFENSIVE: 0.8,
            StrategyType.BALANCED: 1.0,
            StrategyType.COVERT: 0.6,
            StrategyType.OVERWHELMING: 2.0
        }

        return {k: v * multiplier[strategy] for k, v in base.items()}

    def _calculate_timeline(self, strategy: StrategyType) -> str:
        """计算时间线"""
        timelines = {
            StrategyType.AGGRESSIVE: "15-30分钟",
            StrategyType.DEFENSIVE: "60-120分钟",
            StrategyType.BALANCED: "30-60分钟",
            StrategyType.COVERT: "120+分钟",
            StrategyType.OVERWHELMING: "10-20分钟"
        }
        return timelines[strategy]

    def _generate_pros_cons(self, strategy: StrategyType,
                           target: Dict,
                           risk: RiskAssessment) -> tuple:
        """生成优缺点"""
        pros = []
        cons = []

        if strategy == StrategyType.AGGRESSIVE:
            pros.append("快速达成目标")
            pros.append("出其不意")
            cons.append("风险较高")
            cons.append("资源消耗大")
        elif strategy == StrategyType.DEFENSIVE:
            pros.append("安全性高")
            pros.append("可调整方案")
            cons.append("时间较长")
            cons.append("可能被预警")
        elif strategy == StrategyType.BALANCED:
            pros.append("兼顾效果和安全")
            pros.append("灵活应变")
            cons.append("可能不是最优解")
        elif strategy == StrategyType.COVERT:
            pros.append("减少敌人反应时间")
            pros.append("降低政治风险")
            cons.append("准备时间长")
            cons.append("执行复杂")
        elif strategy == StrategyType.OVERWHELMING:
            pros.append("成功率高")
            pros.append("压制敌人反击")
            cons.append("资源消耗最大")
            cons.append("政治敏感性高")

        return pros, cons


class OPAPolicyVerifier:
    """OPA 策略验证器"""

    def __init__(self, opa_manager=None):
        self._opa_manager = opa_manager
        self._verification_cache: Dict[str, bool] = {}

    def verify_strike_plan(self, plan: StrikePlan, user: Dict) -> Dict[str, Any]:
        """
        验证打击计划

        Args:
            plan: 打击计划
            user: 用户信息

        Returns:
            验证结果
        """
        if self._opa_manager is None:
            return {
                "verified": True,
                "message": "OPA not configured, auto-approved",
                "violations": []
            }

        resource_id = plan.target_id
        action = f"strike:{plan.strategy_type.value}"

        try:
            result = self._opa_manager.check_permission(
                user.get("role", "guest"),
                action,
                {"type": "target", "id": resource_id, "risk": plan.risk_assessment.overall_risk.value}
            )

            return {
                "verified": result,
                "message": "Approved by OPA" if result else "Rejected by OPA",
                "violations": [] if result else ["OPA policy violation"]
            }

        except Exception as e:
            return {
                "verified": False,
                "message": f"OPA verification error: {str(e)}",
                "violations": [str(e)]
            }

    def verify_risk_level(self, risk: RiskLevel, user: Dict) -> bool:
        """验证风险等级权限"""
        if self._opa_manager is None:
            return True

        risk_action_map = {
            RiskLevel.CRITICAL: "strike:risk_critical",
            RiskLevel.HIGH: "strike:risk_high",
            RiskLevel.MEDIUM: "strike:risk_medium",
            RiskLevel.LOW: "strike:risk_low"
        }

        action = risk_action_map.get(risk, "strike:risk_low")

        try:
            return self._opa_manager.check_permission(
                user.get("role", "guest"),
                action,
                {}
            )
        except:
            return True


class DecisionRecommendationEngine:
    """
    决策推荐引擎 v2
    完整的打击决策推荐系统
    """

    def __init__(self, opa_manager=None):
        self._risk_model = RiskAssessmentModel()
        self._strategy_generator = StrategyGenerator()
        self._opa_verifier = OPAPolicyVerifier(opa_manager)
        self._recommendations: Dict[str, DecisionRecommendation] = {}
        self._history: List[DecisionRecommendation] = []
        self._max_history = 1000
        self._lock = threading.RLock()

    def generate_recommendation(self,
                               situation: Dict[str, Any],
                               target: Dict[str, Any],
                               user: Dict,
                               intelligence: List[Dict] = None) -> DecisionRecommendation:
        """
        生成决策推荐

        Args:
            situation: 当前态势
            target: 目标信息
            user: 用户信息
            intelligence: 情报信息

        Returns:
            DecisionRecommendation
        """
        civilians = situation.get("civilians_nearby", [])

        risk = self._risk_model.assess_risk(situation, target, civilians)

        strategies = self._strategy_generator.generate_strategies(
            situation, target, risk
        )

        recommended = strategies[0] if strategies else None

        strike_plan = self._create_strike_plan(target, recommended, risk, situation)

        opa_result = self._opa_verifier.verify_strike_plan(strike_plan, user)

        recommendation = DecisionRecommendation(
            recommendation_id=str(uuid.uuid4()),
            title=f"打击目标 {target.get('properties', {}).get('name', '未知')}",
            description=f"针对 {target.get('properties', {}).get('type', '目标')} 的打击行动",
            situation_summary=self._generate_situation_summary(situation),
            strike_plan=strike_plan,
            risk_assessment=risk,
            alternatives=strategies[1:] if len(strategies) > 1 else [],
            recommended_strategy=recommended.strategy_id if recommended else "",
            reasoning=self._generate_reasoning(target, risk, recommended),
            supporting_intelligence=intelligence or [],
            constraints=self._generate_constraints(situation, risk),
            status=RecommendationStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by=user.get("user_id", "system"),
            opa_verified=opa_result["verified"],
            opa_verification_result=opa_result
        )

        with self._lock:
            self._recommendations[recommendation.recommendation_id] = recommendation

        return recommendation

    def _create_strike_plan(self, target: Dict,
                           strategy: StrategyComparison,
                           risk: RiskAssessment,
                           situation: Dict) -> StrikePlan:
        """创建打击计划"""
        target_props = target.get("properties", {})

        phases = [
            {
                "phase": 1,
                "name": "侦察阶段",
                "duration_minutes": 10,
                "actions": ["无人机侦察", "信号情报收集"]
            },
            {
                "phase": 2,
                "name": "打击阶段",
                "duration_minutes": int(strategy.timeline.split("-")[0].replace("+", "")) if strategy else 30,
                "actions": [f"使用{strategy.strategy_name}" if strategy else "发起打击"]
            },
            {
                "phase": 3,
                "name": "评估阶段",
                "duration_minutes": 15,
                "actions": ["损害评估", "战场整理"]
            }
        ]

        return StrikePlan(
            plan_id=str(uuid.uuid4()),
            name=f"打击计划-{target_props.get('name', '目标')}",
            description=f"针对 {target_props.get('name', '目标')} 的 {strategy.strategy_name if strategy else '标准'} 打击",
            objective=f"摧毁或削弱 {target_props.get('type', '目标')} 能力",
            target_id=target.get("entity_id", target.get("id", "")),
            target_name=target_props.get("name", "未知目标"),
            target_type=target_props.get("type", "unknown"),
            strategy_type=strategy.strategy_type if strategy else StrategyType.BALANCED,
            phases=phases,
            resources=strategy.resource_requirements if strategy else {},
            timeline={
                "start": datetime.now(timezone.utc).isoformat(),
                "estimated_end": (datetime.now(timezone.utc).timestamp() + 3600)
            },
            expected_outcome=self._generate_expected_outcome(target, strategy),
            risk_assessment=risk
        )

    def _generate_situation_summary(self, situation: Dict) -> str:
        """生成态势摘要"""
        threat = situation.get("threat_level", "unknown")
        summary = f"当前威胁等级: {threat}"

        if situation.get("recent_events"):
            summary += f", 最近事件: {len(situation['recent_events'])}"

        if situation.get("enemy_units_count", 0) > 0:
            summary += f", 敌方单位: {situation['enemy_units_count']}"

        return summary

    def _generate_reasoning(self, target: Dict, risk: RiskAssessment,
                          strategy: StrategyComparison) -> List[str]:
        """生成推理过程"""
        reasoning = []

        target_name = target.get("properties", {}).get("name", "目标")
        reasoning.append(f"目标 {target_name} 被识别为高价值目标")

        if risk.overall_risk in [RiskLevel.LOW, RiskLevel.MEDIUM]:
            reasoning.append(f"风险等级 {risk.overall_risk.value} 可接受")
        else:
            reasoning.append(f"警告: 风险等级 {risk.overall_risk.value} 需要额外审批")

        if strategy:
            reasoning.append(f"推荐策略: {strategy.strategy_name}")
            reasoning.append(f"预期成功率: {strategy.success_probability:.0%}")

        return reasoning

    def _generate_constraints(self, situation: Dict, risk: RiskAssessment) -> List[str]:
        """生成约束条件"""
        constraints = []

        if risk.civilian_risk > 0.3:
            constraints.append("必须完成平民保护确认程序")

        if risk.escalation_potential > 0.5:
            constraints.append("需要外交部门协调")

        if situation.get("weather", {}).get("condition") == "poor":
            constraints.append("天气条件不佳，需要额外评估")

        return constraints

    def _generate_expected_outcome(self, target: Dict, strategy: StrategyComparison) -> str:
        """生成预期结果"""
        target_name = target.get("properties", {}).get("name", "目标")
        success_rate = strategy.success_probability if strategy else 0.7

        return f"预期以 {success_rate:.0%} 的成功率摧毁 {target_name}"

    def approve_recommendation(self, recommendation_id: str,
                              approver: str) -> bool:
        """批准推荐"""
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if not rec:
                return False

            if not rec.opa_verified:
                return False

            rec.status = RecommendationStatus.APPROVED
            rec.approved_by = approver
            rec.approved_at = datetime.now(timezone.utc).isoformat()

            self._history.append(rec)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

            return True

    def reject_recommendation(self, recommendation_id: str,
                             reason: str) -> bool:
        """拒绝推荐"""
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if not rec:
                return False

            rec.status = RecommendationStatus.REJECTED
            self._history.append(rec)

            return True

    def get_recommendation(self, recommendation_id: str) -> Optional[DecisionRecommendation]:
        """获取推荐"""
        return self._recommendations.get(recommendation_id)

    def get_pending_recommendations(self) -> List[DecisionRecommendation]:
        """获取待处理推荐"""
        return [r for r in self._recommendations.values()
               if r.status == RecommendationStatus.PENDING]

    def get_history(self, limit: int = 100) -> List[DecisionRecommendation]:
        """获取历史推荐"""
        return self._history[-limit:]


_global_engine: Optional[DecisionRecommendationEngine] = None


def get_decision_engine(opa_manager=None) -> DecisionRecommendationEngine:
    """获取全局决策推荐引擎"""
    global _global_engine
    if _global_engine is None:
        _global_engine = DecisionRecommendationEngine(opa_manager)
    return _global_engine


if __name__ == "__main__":
    engine = get_decision_engine()

    print("=" * 60)
    print("决策推荐引擎 v2 测试")
    print("=" * 60)

    print("\n1. 生成决策推荐:")

    situation = {
        "threat_level": "high",
        "enemy_units_count": 5,
        "friend_units_count": 3,
        "available_resources": {"personnel": 100, "aircraft": 10},
        "required_resources": {"personnel": 50, "aircraft": 5},
        "time_available_minutes": 60,
        "time_required_minutes": 30,
        "civilians_nearby": []
    }

    target = {
        "entity_id": "target-001",
        "properties": {
            "name": "敌方雷达站",
            "type": "radar",
            "area": "B区",
            "power_rating": 500
        }
    }

    user = {"user_id": "commander-001", "role": "commander"}

    recommendation = engine.generate_recommendation(situation, target, user)

    print(f"   推荐ID: {recommendation.recommendation_id}")
    print(f"   标题: {recommendation.title}")
    print(f"   OPA验证: {'通过' if recommendation.opa_verified else '未通过'}")

    print("\n2. 风险评估:")
    risk = recommendation.risk_assessment
    print(f"   整体风险: {risk.overall_risk.value}")
    print(f"   风险分数: {risk.risk_score:.2f}")
    print(f"   平民风险: {risk.civilian_risk:.2f}")

    print("\n3. 策略对比:")
    print(f"   推荐策略: {recommendation.strike_plan.strategy_type.value}")
    for i, alt in enumerate(recommendation.alternatives[:2], 1):
        print(f"   备选{i}: {alt.strategy_name} (成功率: {alt.success_probability:.0%})")

    print("\n4. 打击计划:")
    plan = recommendation.strike_plan
    print(f"   计划名: {plan.name}")
    print(f"   目标: {plan.target_name}")
    print(f"   阶段数: {len(plan.phases)}")

    print("\n" + "=" * 60)
    print("决策推荐引擎 v2 测试完成")
    print("=" * 60)