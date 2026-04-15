# Decision Recommendation 决策推荐模块设计文档

> **优先级**: P1 | **相关 ADR**: ADR-001, ADR-002, ADR-004

## 1. 模块概述

### 1.1 模块定位

`decision_recommendation` 是领域决策支持系统，基于 Graphiti 知识图谱的 RAG 增强推理，为 Commander Agent 提供打击方案推荐和决策支持。

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

## 6. 模拟推演集成

### 6.1 模拟推演适配器

```python
# core/decision_recommendation/simulation_adapter.py

class SimulationDecisionAdapter:
    """
    模拟推演决策适配器 - 支持在沙箱环境中执行决策推荐
    """
    
    def __init__(
        self, 
        decision_engine: DecisionRecommendationEngine,
        simulation_client: SimulationClient
    ):
        self.engine = decision_engine
        self.sim_client = simulation_client
        
    async def simulate_decision_scenario(
        self,
        scenario_config: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> SimulationResult:
        """
        在模拟环境中执行决策场景
        """
        # 1. 创建模拟沙箱
        sandbox_id = await self.sim_client.create_sandbox(
            scenario_type="decision_analysis",
            config=scenario_config
        )
        
        try:
            # 2. 注入参数
            injected_params = await self.sim_client.inject_parameters(
                sandbox_id,
                parameters
            )
            
            # 3. 执行决策分析
            targets = injected_params.get("targets", [])
            constraints = injected_params.get("constraints", {})
            
            # 生成打击方案
            strike_plans = await self.engine.generate_strike_plans(
                targets, 
                constraints
            )
            
            # 评估风险
            risk_assessments = []
            for plan in strike_plans:
                risk = await self.engine.assess_risks(plan, constraints)
                risk_assessments.append(risk)
            
            # 排序方案
            ranked_plans = await self.engine.rank_plans(strike_plans)
            
            # 4. 捕获结果
            result = await self.sim_client.capture_result(
                sandbox_id,
                {
                    "strike_plans": [
                        p.dict() for p in strike_plans
                    ],
                    "risk_assessments": [
                        r.dict() for r in risk_assessments
                    ],
                    "ranked_plans": [
                        p.dict() for p in ranked_plans
                    ],
                    "best_plan": ranked_plans[0].dict() if ranked_plans else None
                }
            )
            
            return result
            
        finally:
            # 5. 清理沙箱
            await self.sim_client.cleanup_sandbox(sandbox_id)
    
    async def compare_decision_strategies(
        self,
        base_scenario: Dict[str, Any],
        strategy_variants: List[Dict[str, Any]]
    ) -> ComparisonResult:
        """
        对比不同决策策略的效果
        """
        simulation_tasks = []
        
        for variant in strategy_variants:
            # 合并基础配置和变体
            scenario_config = {**base_scenario, **variant}
            
            task = asyncio.create_task(
                self.simulate_decision_scenario(
                    scenario_config,
                    variant.get("parameters", {})
                )
            )
            simulation_tasks.append((variant["name"], task))
        
        # 等待所有模拟完成
        results = []
        for name, task in simulation_tasks:
            try:
                result = await task
                results.append({
                    "strategy_name": name,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "strategy_name": name,
                    "error": str(e)
                })
        
        # 对比分析
        comparison = await self._compare_results(results)
        
        return comparison
    
    async def what_if_analysis(
        self,
        base_plan: StrikePlan,
        what_if_changes: Dict[str, Any]
    ) -> WhatIfResult:
        """
        What-if分析：如果改变某些参数会怎样
        """
        # 复制基础方案并应用修改
        modified_plan = base_plan.copy(update=what_if_changes)
        
        # 重新评估风险
        modified_risk = await self.engine.assess_risks(
            modified_plan,
            base_plan.constraints
        )
        
        # 计算变化
        changes = self._calculate_changes(
            base_plan, 
            modified_plan,
            base_plan.risk_assessment,
            modified_risk
        )
        
        return WhatIfResult(
            modified_plan=modified_plan,
            modified_risk=modified_risk,
            changes=changes,
            recommendations=self._generate_recommendations(changes)
        )
```

### 6.2 Web界面集成

```python
# ui/decision_simulation/components.py

class DecisionSimulationDashboard:
    """
    决策模拟推演Web界面
    """
    
    def __init__(self, api_client: APIClient):
        self.api = api_client
        
    def render_dashboard(self) -> Dashboard:
        """
        渲染模拟推演控制面板
        """
        return Dashboard(
            title="决策模拟推演系统",
            layout=[
                # 参数配置面板
                self._render_parameter_panel(),
                
                # 方案对比面板
                self._render_comparison_panel(),
                
                # 结果可视化面板
                self._render_visualization_panel(),
                
                # 版本管理面板
                self._render_version_panel()
            ]
        )
    
    def _render_parameter_panel(self) -> Component:
        """
        参数配置面板
        """
        return ParameterPanel(
            title="推演参数配置",
            parameters=[
                Parameter(
                    name="target_selection",
                    label="目标选择策略",
                    type="select",
                    options=[
                        {"value": "priority", "label": "优先级优先"},
                        {"value": "risk", "label": "风险优先"},
                        {"value": "mixed", "label": "混合策略"}
                    ],
                    default="mixed"
                ),
                Parameter(
                    name="risk_tolerance",
                    label="风险容忍度",
                    type="slider",
                    min=0,
                    max=100,
                    default=50,
                    step=5
                ),
                Parameter(
                    name="weapon_constraints",
                    label="武器使用约束",
                    type="multi-select",
                    options=[
                        {"value": "no_collateral", "label": "零附带损伤"},
                        {"value": "minimum_cost", "label": "成本最小化"},
                        {"value": "maximum_effect", "label": "效果最大化"}
                    ],
                    default=["maximum_effect"]
                )
            ],
            on_change=self._handle_parameter_change
        )
    
    def _render_comparison_panel(self) -> Component:
        """
        方案对比面板
        """
        return ComparisonPanel(
            title="多方案对比",
            metrics=[
                "success_rate",
                "risk_score", 
                "estimated_cost",
                "collateral_damage"
            ],
            on_select=self._handle_plan_selection
        )
    
    def _handle_parameter_change(self, params: Dict[str, Any]):
        """
        处理参数变更
        """
        # 创建新方案版本
        new_version = self.api.create_version({
            "parameters": params,
            "description": "参数调整版本"
        })
        
        # 执行模拟推演
        result = self.api.run_simulation(
            scenario_id=current_scenario_id,
            version_id=new_version.id
        )
        
        # 更新结果展示
        self._update_results(result)
    
    def _handle_plan_selection(self, plan_id: str):
        """
        处理方案选择
        """
        # 获取方案详情
        plan_details = self.api.get_plan_details(plan_id)
        
        # 显示详细分析
        self._show_plan_analysis(plan_details)
```

### 6.3 模拟推演配置

```yaml
# config/simulation_decision.yaml
simulation_decision:
  # 推演参数
  parameters:
    # 目标选择
    target_selection:
      strategies:
        - name: "priority_based"
          description: "基于威胁等级优先级"
          algorithm: "multi_criteria_decision"
          criteria_weights:
            threat_level: 0.4
            strategic_value: 0.3
            proximity: 0.2
            vulnerability: 0.1
        
        - name: "risk_averse"
          description: "风险规避策略"
          algorithm: "risk_minimization"
          risk_weights:
            collateral: 0.4
            counterattack: 0.3
            escalation: 0.2
            political: 0.1
    
    # 武器选择
    weapon_selection:
      optimization_goal: "maximize_effectiveness"
      constraints:
        max_cost: 1000000
        min_success_rate: 0.7
        max_collateral: 10
        
  # 推演场景
  scenarios:
    - name: "quick_strike"
      description: "快速打击场景"
      time_limit: 300  # 5分钟
      resources: "limited"
      objectives:
        - "eliminate_high_value_target"
        - "minimize_collateral"
    
    - name: "sustained_operation"
      description: "持续作领域景"
      time_limit: 1800  # 30分钟
      resources: "extended"
      objectives:
        - "multiple_targets"
        - "terrain_control"
        - "force_projection"
  
  # 评估指标
  metrics:
    primary:
      - "mission_success"
      - "risk_level"
      - "resource_efficiency"
    
    secondary:
      - "decision_quality"
      - "response_time"
      - "adaptability"
  
  # 推演参数范围
  parameter_ranges:
    risk_tolerance:
      min: 0
      max: 100
      step: 5
      default: 50
    
    weapon_constraints:
      options: ["precision", "stealth", "speed", "power"]
      default: ["precision", "stealth"]
```

### 6.4 测试用例

```python
# tests/decision_simulation/test_simulation.py

class TestDecisionSimulation:
    
    async def test_simulation_decision_scenario(self):
        """测试模拟推演决策场景"""
        engine = DecisionRecommendationEngine(
            graphiti_client=mock_graphiti,
            opa_manager=mock_opa
        )
        
        adapter = SimulationDecisionAdapter(
            decision_engine=engine,
            simulation_client=mock_simulation
        )
        
        # 执行模拟推演
        result = await adapter.simulate_decision_scenario(
            scenario_config={
                "name": "test_strike",
                "type": "precision_strike"
            },
            parameters={
                "targets": [
                    {"id": "t1", "name": "Target A", "threat_level": 8}
                ],
                "constraints": {
                    "risk_tolerance": 60,
                    "time_limit": 600
                }
            }
        )
        
        # 验证结果
        assert result.status == "completed"
        assert "strike_plans" in result.data
        assert len(result.data["strike_plans"]) > 0
        
        # 验证最佳方案
        best_plan = result.data.get("best_plan")
        assert best_plan is not None
        assert best_plan["priority_score"] >= 0
        assert best_plan["risk_score"] >= 0
    
    async def test_compare_decision_strategies(self):
        """测试决策策略对比"""
        adapter = SimulationDecisionAdapter(
            decision_engine=mock_engine,
            simulation_client=mock_simulation
        )
        
        # 定义策略变体
        strategies = [
            {
                "name": "aggressive",
                "parameters": {
                    "risk_tolerance": 80,
                    "target_selection": "priority"
                }
            },
            {
                "name": "conservative", 
                "parameters": {
                    "risk_tolerance": 30,
                    "target_selection": "risk"
                }
            }
        ]
        
        # 执行对比
        comparison = await adapter.compare_decision_strategies(
            base_scenario={
                "targets": test_targets,
                "resources": test_resources
            },
            strategy_variants=strategies
        )
        
        # 验证对比结果
        assert len(comparison.results) == 2
        assert "aggressive" in comparison.results
        assert "conservative" in comparison.results
        assert comparison.best_strategy in ["aggressive", "conservative"]
        
        # 验证分析报告
        assert comparison.analysis is not None
        assert "insights" in comparison.analysis
        assert "recommendations" in comparison.analysis
    
    async def test_what_if_analysis(self):
        """测试What-if分析"""
        engine = DecisionRecommendationEngine(
            graphiti_client=mock_graphiti,
            opa_manager=mock_opa
        )
        
        # 生成基础方案
        base_plan = await engine.generate_strike_plans(
            targets=test_targets,
            constraints=test_constraints
        )[0]
        
        adapter = SimulationDecisionAdapter(
            decision_engine=engine,
            simulation_client=mock_simulation
        )
        
        # 执行What-if分析
        what_if_result = await adapter.what_if_analysis(
            base_plan=base_plan,
            what_if_changes={
                "weapon_type": "guided_missile",
                "attack_range": 500
            }
        )
        
        # 验证结果
        assert what_if_result.modified_plan is not None
        assert what_if_result.changes is not None
        assert "risk_score_change" in what_if_result.changes
        assert "success_rate_change" in what_if_result.changes
        assert len(what_if_result.recommendations) > 0
```

---

## 7. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
| 1.1.0 | 2026-04-12 | 新增模拟推演集成支持，包括适配器、Web界面和测试用例 |

---

**相关文档**:
- [Graphiti 客户端模块设计](../graphiti_client/DESIGN.md)
- [Ontology 本体管理层设计](../ontology/DESIGN.md)
- [Swarm 编排模块设计](../swarm_orchestrator/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)
