# Decision Recommendation 决策推荐模块设计文档

## 1. 模块概述

### 1.1 模块定位

`decision_recommendation` 是战场决策支持系统，基于 Graphiti 知识图谱的 RAG 增强推理，为 Commander Agent 提供打击方案推荐和决策支持。

### 1.2 核心职责

| 职责 | 描述 |
|------|------|
| 方案生成 | 基于历史案例生成打击方案 |
| 风险评估 | 多维度风险分析 |
| 方案排序 | 综合评分和优先级排序 |
| 解释生成 | 决策理由的可解释性 |

---

## 2. 接口设计

### 2.1 决策服务

```python
# core/decision_recommendation/engine.py
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class RecommendationType(str, Enum):
    """推荐类型"""
    ATTACK_PLAN = "attack_plan"
    TARGET_PRIORITY = "target_priority"
    WEAPON_RECOMMENDATION = "weapon_recommendation"
    ROUTE_PLAN = "route_plan"

class StrikePlan(BaseModel):
    """打击方案"""
    plan_id: str
    target_id: str
    target_name: str
    weapon_type: str
    weapon_id: Optional[str] = None
    priority_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    estimated_success_rate: float = Field(ge=0, le=1)
    estimated_casualties: int = 0
    estimated_cost: float = 0.0
    rationale: str
    supporting_evidence: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    alternative_plans: List[str] = Field(default_factory=list)

class RiskAssessment(BaseModel):
    """风险评估"""
    overall_risk_score: float
    risk_factors: List[Dict[str, Any]]
    mitigation_suggestions: List[str]

class DecisionRecommendationEngine:
    """决策推荐引擎"""

    def __init__(self, graphiti_client, opa_manager):
        self.graphiti = graphiti_client
        self.opa = opa_manager

    async def generate_strike_plans(
        self,
        targets: List[Dict[str, Any]],
        constraints: Dict[str, Any]
    ) -> List[StrikePlan]:
        """生成打击方案"""
        pass

    async def assess_risks(
        self,
        plan: StrikePlan,
        context: Dict[str, Any]
    ) -> RiskAssessment:
        """评估方案风险"""
        pass

    async def rank_plans(
        self,
        plans: List[StrikePlan]
    ) -> List[StrikePlan]:
        """排序打击方案"""
        pass

    async def generate_rationale(
        self,
        plan: StrikePlan
    ) -> str:
        """生成决策理由"""
        pass
```

---

## 3. 核心实现

### 3.1 方案生成

```python
# core/decision_recommendation/plan_generator.py

class StrikePlanGenerator:
    """打击方案生成器"""

    def __init__(self, graphiti_client, weapon_db):
        self.graphiti = graphiti_client
        self.weapon_db = weapon_db

    async def generate(
        self,
        target: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> StrikePlan:
        """生成打击方案"""

        # 1. 查找相似历史案例
        historical_cases = await self._find_similar_cases(target)

        # 2. 选择合适武器
        weapon = await self._select_weapon(target, constraints)

        # 3. 计算优先级评分
        priority_score = await self._calculate_priority(target, historical_cases)

        # 4. 评估成功率
        success_rate = await self._estimate_success_rate(target, weapon)

        # 5. 生成理由
        rationale = await self._generate_rationale(target, weapon, historical_cases)

        return StrikePlan(
            plan_id=str(uuid.uuid4()),
            target_id=target["id"],
            target_name=target["name"],
            weapon_type=weapon["type"],
            priority_score=priority_score,
            estimated_success_rate=success_rate,
            rationale=rationale,
            supporting_evidence=[c["id"] for c in historical_cases[:3]]
        )

    async def _find_similar_cases(
        self,
        target: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """查找相似历史案例（RAG 查询）"""
        query = f"""
        Find historical strikes similar to target {target['name']}
        with target type {target['target_type']}
        and threat level {target['threat_level']}
        """
        return await self.graphiti.rag_search(query, limit=5)

    async def _select_weapon(
        self,
        target: Dict[str, Any],
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """选择最优武器"""
        available_weapons = [
            w for w in self.weapon_db
            if w["status"] == "available"
            and w["effective_range"] >= target["distance"]
        ]

        if not available_weapons:
            raise ValueError("No suitable weapon available")

        # 按多准则排序选择
        return max(
            available_weapons,
            key=lambda w: self._weapon_score(w, target)
        )

    def _weapon_score(self, weapon, target) -> float:
        """武器评分"""
        range_score = min(weapon["effective_range"] / target["distance"], 1.0)
        accuracy_score = weapon["accuracy"]
        payload_score = weapon["payload"] / 500  # 标准化

        return 0.4 * range_score + 0.4 * accuracy_score + 0.2 * payload_score
```

### 3.2 风险评估

```python
# core/decision_recommendation/risk_assessor.py

class RiskAssessor:
    """风险评估器"""

    async def assess(
        self,
        plan: StrikePlan,
        context: Dict[str, Any]
    ) -> RiskAssessment:
        """评估方案风险"""

        risk_factors = []

        # 1. 附带损伤风险
        collateral_risk = await self._assess_collateral_risk(plan)
        risk_factors.append(collateral_risk)

        # 2. 反击风险
        counterattack_risk = await self._assess_counterattack_risk(plan)
        risk_factors.append(counterattack_risk)

        # 3. 天气影响
        weather_risk = await self._assess_weather_risk(plan, context)
        risk_factors.append(weather_risk)

        # 4. 技术风险
        technical_risk = await self._assess_technical_risk(plan)
        risk_factors.append(technical_risk)

        # 计算总体风险
        overall_score = sum(rf["score"] * rf["weight"] for rf in risk_factors)

        # 生成缓解建议
        suggestions = self._generate_mitigations(risk_factors)

        return RiskAssessment(
            overall_risk_score=overall_score,
            risk_factors=risk_factors,
            mitigation_suggestions=suggestions
        )

    async def _assess_collateral_risk(
        self,
        plan: StrikePlan
    ) -> Dict[str, Any]:
        """评估附带损伤风险"""
        nearby_protected = await self.graphiti.search_episodes(
            query=f"protected targets near {plan.target_id}",
            categories=["target"]
        )

        if nearby_protected:
            distance = nearby_protected[0].get("distance", 1000)
            return {
                "factor": "collateral_damage",
                "score": max(0, 100 - distance / 10),
                "weight": 0.3,
                "description": f"Protected target within {distance}m"
            }

        return {
            "factor": "collateral_damage",
            "score": 10,
            "weight": 0.3,
            "description": "Low collateral risk"
        }
```

---

## 4. RAG 增强推理

### 4.1 上下文构建

```python
# core/decision_recommendation/context_builder.py

class DecisionContextBuilder:
    """决策上下文构建器"""

    def __init__(self, graphiti_client):
        self.graphiti = graphiti_client

    async def build_context(
        self,
        question: str,
        target_id: Optional[str] = None
    ) -> str:
        """构建决策上下文"""

        context_parts = []

        # 1. 目标信息
        if target_id:
            target_info = await self._get_target_info(target_id)
            context_parts.append(f"## Target Information\n{target_info}")

        # 2. 历史相似案例
        similar_cases = await self.graphiti.rag_search(
            question,
            context_entities=[target_id] if target_id else None,
            limit=5
        )
        context_parts.append(f"## Historical Cases\n{self._format_cases(similar_cases)}")

        # 3. 关联情报
        intel = await self._get_relevant_intelligence(target_id)
        context_parts.append(f"## Intelligence\n{intel}")

        # 4. 时序变化
        timeline = await self._get_target_timeline(target_id)
        context_parts.append(f"## Timeline\n{timeline}")

        return "\n\n".join(context_parts)

    async def _get_target_info(self, target_id: str) -> str:
        """获取目标信息"""
        facts = await self.graphiti.get_temporal_facts(target_id)
        return json.dumps(facts, indent=2, default=str)

    async def _format_cases(self, cases: List[Dict]) -> str:
        """格式化历史案例"""
        lines = []
        for case in cases:
            lines.append(f"- {case['name']}: {case['episode_body'][:200]}")
        return "\n".join(lines) if lines else "No similar cases found"
```

---

## 5. 配置示例

```yaml
# config/decision_recommendation.yaml
decision_recommendation:
  # 方案生成
  plan_generation:
    max_plans_per_target: 3
    min_success_rate: 0.6
    consider_alternatives: true

  # 风险评估
  risk_assessment:
    weights:
      collateral_damage: 0.3
      counterattack: 0.25
      weather: 0.2
      technical: 0.25
    thresholds:
      low: 30
      medium: 60
      high: 80

  # RAG 配置
  rag:
    max_context_tokens: 4000
    similar_cases_limit: 5
    relevance_threshold: 0.7
```

---

## 6. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
