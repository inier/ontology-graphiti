import logging
import uuid
import copy
from typing import List, Optional, Dict, Any

from .schemas import (
    WhatIfScenario, WhatIfResult, WhatIfComparison,
    MetricChange, SimulationStatus,
)

logger = logging.getLogger(__name__)


class SimulationSandbox:
    def __init__(self):
        self._graph_manager = None
        self._oms = None
        self._llm_client = None
        self._plan_versions: Dict[str, List[Dict[str, Any]]] = {}
        self._plan_branches: Dict[str, str] = {}

    @property
    def graph(self):
        if self._graph_manager is None:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    @property
    def oms(self):
        if self._oms is None:
            from odap.biz.core.ontology.oms.services import get_oms_service
            self._oms = get_oms_service()
        return self._oms

    @property
    def llm_client(self):
        if self._llm_client is None:
            try:
                from odap.infra.llm.llm_service import ZhipuAIClient
                from graphiti_core.llm_client.config import LLMConfig
                import os
                api_key = os.getenv('OPENAI_API_KEY', '')
                api_base = os.getenv('OPENAI_API_BASE', 'https://open.bigmodel.cn/api/paas/v4')
                model = os.getenv('OPENAI_MODEL', 'glm-4')
                if api_key:
                    config = LLMConfig(model=model, api_key=api_key, base_url=api_base, temperature=0.3)
                    self._llm_client = ZhipuAIClient(config=config)
                else:
                    self._llm_client = None
            except Exception as e:
                logger.warning(f"SimulationSandbox: LLM client init failed: {e}")
                self._llm_client = None
        return self._llm_client

    async def simulate(self, scenario: WhatIfScenario) -> WhatIfResult:
        scenario_id = scenario.scenario_id or f"sim_{uuid.uuid4().hex[:12]}"

        baseline = await self._capture_baseline(scenario.target_object_id, scenario.target_object_type)

        projected = await self._project_impact(
            scenario.target_object_id,
            scenario.target_object_type,
            scenario.action_type_id,
            scenario.parameters,
        )

        if scenario.variant_parameters:
            for i, variant in enumerate(scenario.variant_parameters):
                variant_result = await self._project_impact(
                    scenario.target_object_id,
                    scenario.target_object_type,
                    scenario.action_type_id,
                    variant,
                )
                projected.append({
                    'variant': i + 1,
                    'parameters': variant,
                    'metrics': variant_result,
                })

        changes = self._compute_metric_changes(baseline, projected[0] if projected else {})

        risk = self._assess_risk(scenario.action_type_id, changes)

        recommendation = self._generate_recommendation(changes, risk)

        return WhatIfResult(
            scenario_id=scenario_id,
            status=SimulationStatus.COMPLETED,
            baseline_metrics=baseline,
            projected_metrics=projected,
            metric_changes=changes,
            risk_assessment=risk,
            recommendation=recommendation,
            confidence=0.6,
        )

    async def compare(self, scenarios: List[WhatIfScenario]) -> WhatIfComparison:
        results = []
        for scenario in scenarios:
            result = await self.simulate(scenario)
            results.append(result)

        best_id = None
        if results:
            best = min(results, key=lambda r: r.risk_assessment.get('overall_risk', 1.0))
            best_id = best.scenario_id

        summary_parts = []
        for r in results:
            risk_level = r.risk_assessment.get('overall_risk', 'unknown')
            summary_parts.append(f"方案 {r.scenario_id}: 风险={risk_level}, 推荐={r.recommendation[:50]}")

        return WhatIfComparison(
            scenarios=results,
            best_scenario_id=best_id,
            summary="\n".join(summary_parts),
        )

    async def _capture_baseline(self, target_id: str, target_type: str) -> Dict[str, Any]:
        baseline = {'target_id': target_id, 'target_type': target_type}
        try:
            entities = self.graph.query_entities(entity_type=target_type)
            for entity in entities[:20]:
                e_dict = entity.to_dict() if hasattr(entity, 'to_dict') else dict(entity)
                eid = e_dict.get('id', '')
                if eid == target_id:
                    props = e_dict.get('properties', {})
                    for key in ('combat_power', 'morale', 'supply_level', 'strength', 'status'):
                        if key in props:
                            baseline[key] = props[key]
                    break

            type_def = self.oms.get_object_type(target_type)
            if type_def:
                for prop in type_def.get('properties', []):
                    if prop.get('category') == 'statistical_properties':
                        pname = prop.get('name', '')
                        if pname and pname not in baseline:
                            baseline[pname] = 0
        except Exception as e:
            logger.warning(f"Capture baseline failed: {e}")

        return baseline

    async def _project_impact(
        self,
        target_id: str,
        target_type: str,
        action_type_id: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        projected = {'target_id': target_id, 'action': action_type_id, 'parameters': parameters}

        action_def = self.oms.get_action_type(action_type_id)
        if not action_def:
            projected['error'] = f"Action type {action_type_id} not found"
            return projected

        impact_rules = self._load_impact_rules(action_type_id)
        projected['estimated_impact'] = impact_rules

        llm_impact = await self._project_impact_with_llm(
            target_id, target_type, action_type_id, parameters, impact_rules
        )
        if llm_impact:
            projected['llm_impact'] = llm_impact
            for metric, delta in llm_impact.items():
                if metric not in impact_rules:
                    impact_rules[metric] = delta
            projected['estimated_impact'] = impact_rules

        return projected

    async def _project_impact_with_llm(
        self,
        target_id: str,
        target_type: str,
        action_type_id: str,
        parameters: Dict[str, Any],
        rule_based_impact: Dict[str, float],
    ) -> Optional[Dict[str, float]]:
        if not self.llm_client:
            return None

    def create_plan_branch(self, plan_id: str, parent_version: Optional[str] = None) -> Dict[str, Any]:
        if plan_id not in self._plan_versions:
            self._plan_versions[plan_id] = [{"version": "v1", "data": {}, "timestamp": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}]

        versions = self._plan_versions[plan_id]
        parent = parent_version or versions[-1]["version"]
        new_version = f"v{len(versions) + 1}"
        branch_id = f"{plan_id}_branch_{new_version}"

        self._plan_versions[plan_id].append({
            "version": new_version,
            "parent": parent,
            "branch": True,
            "data": copy.deepcopy(versions[-1].get("data", {})),
            "timestamp": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        })
        self._plan_branches[branch_id] = plan_id

        logger.info(f"Created plan branch: {branch_id} from {parent}")
        return {"branch_id": branch_id, "version": new_version, "parent": parent}

    def rollback_plan(self, plan_id: str, target_version: str) -> Dict[str, Any]:
        if plan_id not in self._plan_versions:
            return {"error": f"Plan '{plan_id}' not found"}

        versions = self._plan_versions[plan_id]
        target = None
        for v in versions:
            if v["version"] == target_version:
                target = v
                break

        if not target:
            return {"error": f"Version '{target_version}' not found in plan '{plan_id}'"}

        self._plan_versions[plan_id] = [v for v in versions if v["version"] <= target_version]

        logger.info(f"Rolled back plan '{plan_id}' to version {target_version}")
        return {"plan_id": plan_id, "current_version": target_version, "available_versions": [v["version"] for v in self._plan_versions[plan_id]]}

    def list_plan_versions(self, plan_id: str) -> List[Dict[str, Any]]:
        return self._plan_versions.get(plan_id, [])

    async def _project_impact_with_llm(self, target_id, target_type, action_type_id, parameters, rule_based_impact):
        import asyncio
        import json

        prompt = (
            f"你是一个军事行动效果推演专家。请根据以下信息，推演该行动对各指标的影响。\n\n"
            f"目标对象: {target_id} (类型: {target_type})\n"
            f"行动类型: {action_type_id}\n"
            f"行动参数: {json.dumps(parameters, ensure_ascii=False)}\n"
            f"基于规则的影响: {json.dumps(rule_based_impact, ensure_ascii=False)}\n\n"
            f"请推演该行动可能产生的其他影响，特别是规则未覆盖的间接影响和连锁反应。\n"
            f"返回 JSON 格式，键为指标名(英文)，值为影响系数(负数表示下降，正数表示上升，范围-1到1)。\n"
            f"仅返回规则未覆盖的额外指标影响，不要重复已有指标。\n"
            f"如果没有额外影响，返回空对象 {{}}。"
        )

        try:
            from graphiti_core.prompts.models import Message

            messages = [
                Message(role="system", content="你是一个军事推演分析专家，擅长评估行动的间接影响和连锁反应。只返回JSON。"),
                Message(role="user", content=prompt),
            ]

            async def call_llm():
                response, _, _ = await self.llm_client._generate_response(messages)
                return response

            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = await loop.run_in_executor(
                            pool, lambda: asyncio.run(call_llm())
                        )
                else:
                    result = await call_llm()
            except RuntimeError:
                result = await call_llm()

            if isinstance(result, dict):
                extra_impact = {}
                for k, v in result.items():
                    if isinstance(v, (int, float)) and -1 <= v <= 1:
                        extra_impact[k] = float(v)
                if extra_impact:
                    logger.debug(f"LLM projected extra impact: {extra_impact}")
                    return extra_impact

            return None
        except Exception as e:
            logger.debug(f"LLM impact projection failed: {e}")
            return None

    def _load_impact_rules(self, action_type_id: str) -> Dict[str, float]:
        import json
        import os

        rules_path = os.path.join('config', 'simulation_impact_rules.json')
        if os.path.exists(rules_path):
            try:
                with open(rules_path, 'r', encoding='utf-8') as f:
                    all_rules = json.load(f)
                return all_rules.get(action_type_id, {})
            except Exception as e:
                logger.warning(f"Failed to load impact rules from {rules_path}: {e}")

        try:
            action_def = self.oms.get_action_type(action_type_id)
            if action_def and action_def.get('parameters'):
                rules = {}
                for param in action_def.get('parameters', []):
                    pname = param.get('name', '')
                    if 'supply' in pname.lower() or 'cost' in pname.lower():
                        rules['supply_level'] = -0.1
                    elif 'speed' in pname.lower():
                        rules['morale'] = -0.05
                if rules:
                    return rules
        except Exception:
            pass

        DEFAULT_IMPACT_RULES = {
            'move': {'supply_level': -0.1, 'morale': -0.05},
            'attack': {'combat_power': -0.2, 'morale': -0.15, 'supply_level': -0.3, 'casualty_rate': 0.15},
            'defend': {'combat_power': -0.05, 'morale': 0.1, 'supply_level': -0.1},
            'reinforce': {'strength': 0.3, 'morale': 0.15, 'supply_level': -0.15},
            'retreat': {'morale': -0.25, 'combat_power': -0.1},
            'observe': {'supply_level': -0.02},
            'communicate': {},
        }
        return DEFAULT_IMPACT_RULES.get(action_type_id, {})

    def _compute_metric_changes(self, baseline: Dict[str, Any], projected: Dict[str, Any]) -> List[MetricChange]:
        changes = []
        impact = projected.get('estimated_impact', {})

        for metric_name, delta in impact.items():
            before = baseline.get(metric_name)
            if before is not None and isinstance(before, (int, float)):
                after = before + delta * (before if before > 1 else 1)
                changes.append(MetricChange(
                    metric_name=metric_name,
                    before=before,
                    after=round(after, 2),
                    delta=round(delta, 3),
                ))
            elif delta != 0:
                changes.append(MetricChange(
                    metric_name=metric_name,
                    before=before,
                    after=None,
                    delta=round(delta, 3),
                ))

        return changes

    def _assess_risk(self, action_type_id: str, changes: List[MetricChange]) -> Dict[str, Any]:
        risk_config = self._load_risk_config()
        action_risk_level = risk_config.get(action_type_id, 'low')

        if action_risk_level == 'high':
            overall_risk = 'high'
        elif action_risk_level == 'medium':
            overall_risk = 'medium'
        else:
            overall_risk = 'low'

        negative_changes = [c for c in changes if c.delta is not None and c.delta < 0]
        risk_factors = []
        for c in negative_changes:
            severity = 'high' if abs(c.delta) > 0.2 else 'medium' if abs(c.delta) > 0.1 else 'low'
            risk_factors.append({
                'metric': c.metric_name,
                'delta': c.delta,
                'severity': severity,
            })

        if any(f['severity'] == 'high' for f in risk_factors):
            overall_risk = 'high'
        elif any(f['severity'] == 'medium' for f in risk_factors) and overall_risk != 'high':
            overall_risk = 'medium'

        return {
            'overall_risk': overall_risk,
            'risk_factors': risk_factors,
            'negative_impact_count': len(negative_changes),
        }

    def _load_risk_config(self) -> Dict[str, str]:
        import json
        import os

        rules_path = os.path.join('config', 'simulation_risk_config.json')
        if os.path.exists(rules_path):
            try:
                with open(rules_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load risk config from {rules_path}: {e}")

        try:
            action_types = self.oms.list_action_types()
            risk_config = {}
            for at in action_types:
                at_id = at.get('action_type_id', '')
                params = at.get('parameters', [])
                has_combat_param = any(
                    'combat' in p.get('name', '').lower() or 'weapon' in p.get('name', '').lower()
                    for p in params
                )
                has_movement_param = any(
                    'speed' in p.get('name', '').lower() or 'route' in p.get('name', '').lower()
                    for p in params
                )
                if has_combat_param:
                    risk_config[at_id] = 'high'
                elif has_movement_param:
                    risk_config[at_id] = 'medium'
                else:
                    risk_config[at_id] = 'low'
            if risk_config:
                return risk_config
        except Exception:
            pass

        DEFAULT_RISK_CONFIG = {
            'attack': 'high',
            'retreat': 'high',
            'reinforce': 'medium',
            'move': 'medium',
            'defend': 'medium',
            'observe': 'low',
            'communicate': 'low',
        }
        return DEFAULT_RISK_CONFIG

    def _generate_recommendation(self, changes: List[MetricChange], risk: Dict[str, Any]) -> str:
        overall = risk.get('overall_risk', 'unknown')
        rule_rec = ""
        if overall == 'high':
            rule_rec = "高风险操作，建议谨慎执行。需要指挥官审批。"
        elif overall == 'medium':
            rule_rec = "中等风险操作，建议评估后执行。"
        else:
            rule_rec = "低风险操作，可以安全执行。"

        llm_rec = self._generate_recommendation_with_llm(changes, risk, rule_rec)
        return llm_rec or rule_rec

    def _generate_recommendation_with_llm(
        self, changes: List[MetricChange], risk: Dict[str, Any], rule_rec: str
    ) -> Optional[str]:
        if not self.llm_client:
            return None

        try:
            import asyncio
            import json

            change_desc = []
            for c in changes:
                direction = "上升" if c.delta and c.delta > 0 else "下降" if c.delta and c.delta < 0 else "不变"
                change_desc.append(f"- {c.metric_name}: {c.before} → {c.after} ({direction} {abs(c.delta):.1%})")

            risk_factors = risk.get('risk_factors', [])
            risk_desc = []
            for f in risk_factors:
                risk_desc.append(f"- {f['metric']}: 严重度={f['severity']}, 变化={f['delta']}")

            prompt = (
                f"你是军事行动决策顾问。请根据以下推演结果，给出详细的行动建议。\n\n"
                f"指标变化:\n{chr(10).join(change_desc) if change_desc else '无显著变化'}\n\n"
                f"风险因素:\n{chr(10).join(risk_desc) if risk_desc else '无显著风险'}\n"
                f"总体风险等级: {risk.get('overall_risk', 'unknown')}\n"
                f"基础建议: {rule_rec}\n\n"
                f"请给出更详细的建议，包括：1)是否建议执行 2)注意事项 3)备选方案。"
                f"用简洁的中文回答，不超过200字。"
            )

            from graphiti_core.prompts.models import Message

            messages = [
                Message(role="system", content="你是军事决策顾问，给出简洁专业的行动建议。"),
                Message(role="user", content=prompt),
            ]

            async def call_llm():
                response, _, _ = await self.llm_client._generate_response(messages)
                return response

            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = pool.submit(lambda: asyncio.run(call_llm())).result(timeout=15)
                else:
                    result = asyncio.run(call_llm())
            except RuntimeError:
                result = asyncio.run(call_llm())

            if isinstance(result, dict) and 'content' in result:
                return result['content']
            elif isinstance(result, str):
                return result
            return None
        except Exception as e:
            logger.debug(f"LLM recommendation generation failed: {e}")
            return None


_sandbox_instance = None


def get_simulation_sandbox() -> SimulationSandbox:
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = SimulationSandbox()
    return _sandbox_instance
