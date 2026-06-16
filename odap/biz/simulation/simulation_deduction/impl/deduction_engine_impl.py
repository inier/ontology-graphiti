import logging
import uuid
import copy
from typing import List, Dict, Any, Optional
from datetime import datetime

from odap.biz.simulation.simulation_deduction.interfaces.deduction_engine import IDeductionEngine
from odap.biz.simulation.simulation_deduction.models.deduction import (
    DeductionScenario, ExecutionChain, ChainStep, SimulationCondition,
    ChainResult, MetricImpact, RuleViolation, DeductionStatus,
    ChainStatus, ConditionType,
)
from odap.biz.simulation.simulation_deduction.storage import Storage

logger = logging.getLogger(__name__)


class DeductionEngineImpl(IDeductionEngine):
    def __init__(self, storage=None):
        self._storage = storage or Storage()
        self._graph_manager = None
        self._oms = None

    @property
    def graph(self):
        if self._graph_manager is None:
            try:
                from odap.infra.query import get_graph_write_proxy
                self._graph_manager = get_graph_write_proxy()
            except Exception as e:
                logger.warning(f"GraphWriteProxy init failed: {e}")
                self._graph_manager = None
        return self._graph_manager

    @property
    def oms(self):
        if self._oms is None:
            try:
                from odap.biz.core.ontology.application.oms.services import OMSService
                self._oms = OMSService.get_instance()
            except Exception as e:
                logger.warning(f"OMS init failed: {e}")
                self._oms = None
        return self._oms

    async def create_scenario(self, name: str, description: str,
                              source_recommendation_id: Optional[str] = None,
                              source_analysis_id: Optional[str] = None,
                              target_object_id: str = "",
                              target_object_type: str = "") -> Dict[str, Any]:
        scenario = DeductionScenario(
            name=name,
            description=description,
            source_recommendation_id=source_recommendation_id,
            source_analysis_id=source_analysis_id,
            target_object_id=target_object_id,
            target_object_type=target_object_type,
        )
        baseline = await self._capture_baseline(target_object_id, target_object_type)
        scenario.baseline_metrics = baseline
        scenario.status = DeductionStatus.CONFIGURING
        self._storage.save_scenario(scenario.model_dump(mode="json"))
        return scenario.model_dump(mode="json")

    async def load_ontology_conditions(self, scenario_id: str) -> Dict[str, Any]:
        data = self._storage.get_scenario(scenario_id)
        if not data:
            return {"status": "error", "message": "Scenario not found"}

        conditions = []
        rules = await self._load_rules(data.get("target_object_type", ""))
        for rule in rules:
            cond = SimulationCondition(
                name=rule.get("description", rule.get("rule_type", "")),
                condition_type=ConditionType.RULE_BASED,
                description=rule.get("description", ""),
                source_rule_id=rule.get("rule_id", ""),
                expression=rule.get("condition", ""),
                parameters=rule.get("consequence", {}),
            )
            conditions.append(cond.model_dump(mode="json"))

        constraints = await self._load_constraints(data.get("target_object_type", ""))
        for constraint in constraints:
            cond = SimulationCondition(
                name=constraint.get("description", constraint.get("constraint_type", "")),
                condition_type=ConditionType.CONSTRAINT_BASED,
                description=constraint.get("description", ""),
                source_constraint_id=constraint.get("constraint_id", ""),
                expression=constraint.get("scope", {}),
                parameters={"violation_consequence": constraint.get("violation_consequence", "warning")},
            )
            conditions.append(cond.model_dump(mode="json"))

        data["available_conditions"] = conditions
        data["updated_at"] = datetime.now().isoformat()
        self._storage.save_scenario(data)
        return {"scenario_id": scenario_id, "conditions": conditions, "total": len(conditions)}

    async def add_execution_chain(self, scenario_id: str, name: str,
                                   description: str, steps: List[Dict[str, Any]],
                                   conditions: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = self._storage.get_scenario(scenario_id)
        if not data:
            return {"status": "error", "message": "Scenario not found"}

        chain = ExecutionChain(
            name=name,
            description=description,
            steps=[ChainStep(**s) for s in steps],
            conditions=[SimulationCondition(**c) for c in (conditions or [])],
        )
        chains = data.get("chains", [])
        chains.append(chain.model_dump(mode="json"))
        data["chains"] = chains
        data["updated_at"] = datetime.now().isoformat()
        self._storage.save_scenario(data)
        return chain.model_dump(mode="json")

    async def delete_chain(self, scenario_id: str, chain_id: str) -> Dict[str, Any]:
        data = self._storage.get_scenario(scenario_id)
        if not data:
            return {"status": "error", "message": "Scenario not found"}

        chains = data.get("chains", [])
        original_len = len(chains)
        chains = [c for c in chains if c.get("chain_id") != chain_id]
        if len(chains) == original_len:
            return {"status": "error", "message": "Chain not found"}

        data["chains"] = chains
        results = data.get("results", [])
        data["results"] = [r for r in results if r.get("chain_id") != chain_id]
        if data.get("best_chain_id") == chain_id:
            data["best_chain_id"] = None
        data["updated_at"] = datetime.now().isoformat()
        self._storage.save_scenario(data)
        return {"status": "ok", "chain_id": chain_id}

    async def update_chain(self, scenario_id: str, chain_id: str,
                            name: str = None, description: str = None,
                            steps: List[Dict[str, Any]] = None,
                            conditions: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = self._storage.get_scenario(scenario_id)
        if not data:
            return {"status": "error", "message": "Scenario not found"}

        chain_data = None
        for c in data.get("chains", []):
            if c.get("chain_id") == chain_id:
                chain_data = c
                break

        if not chain_data:
            return {"status": "error", "message": "Chain not found"}

        if name is not None:
            chain_data["name"] = name
        if description is not None:
            chain_data["description"] = description
        if steps is not None:
            chain_data["steps"] = [ChainStep(**s).model_dump(mode="json") for s in steps]
        if conditions is not None:
            chain_data["conditions"] = [SimulationCondition(**c).model_dump(mode="json") for c in conditions]

        chain_data["status"] = ChainStatus.PENDING.value
        data["updated_at"] = datetime.now().isoformat()
        self._storage.save_scenario(data)
        return chain_data

    async def update_condition(self, scenario_id: str, condition_id: str,
                                value: Any) -> Dict[str, Any]:
        data = self._storage.get_scenario(scenario_id)
        if not data:
            return {"status": "error", "message": "Scenario not found"}

        updated = False
        for chain in data.get("chains", []):
            for cond in chain.get("conditions", []):
                if cond.get("condition_id") == condition_id:
                    cond["value"] = value
                    cond["is_active"] = True
                    updated = True
                    break
            if updated:
                break

        if not updated:
            for cond in data.get("available_conditions", []):
                if cond.get("condition_id") == condition_id:
                    cond["value"] = value
                    cond["is_active"] = True
                    updated = True
                    break

        if not updated:
            return {"status": "error", "message": "Condition not found"}

        data["updated_at"] = datetime.now().isoformat()
        self._storage.save_scenario(data)
        return {"status": "ok", "condition_id": condition_id, "value": value}

    async def simulate_chain(self, scenario_id: str, chain_id: str) -> Dict[str, Any]:
        data = self._storage.get_scenario(scenario_id)
        if not data:
            return {"status": "error", "message": "Scenario not found"}

        chain_data = None
        for c in data.get("chains", []):
            if c.get("chain_id") == chain_id:
                chain_data = c
                break

        if not chain_data:
            return {"status": "error", "message": "Chain not found"}

        chain_data["status"] = ChainStatus.SIMULATING.value
        data["status"] = DeductionStatus.RUNNING.value
        self._storage.save_scenario(data)

        try:
            baseline = data.get("baseline_metrics", {})
            projected = copy.deepcopy(baseline)
            all_impacts = []
            all_violations = []

            for step in chain_data.get("steps", []):
                step_impacts = await self._simulate_step(step, projected, chain_data.get("conditions", []))
                all_impacts.extend(step_impacts)
                for impact in step_impacts:
                    metric = impact.get("metric_name", "")
                    delta = impact.get("delta", 0)
                    if metric in projected and isinstance(projected[metric], (int, float)):
                        projected[metric] = projected[metric] + delta * (projected[metric] if projected[metric] > 1 else 1)

                violations = self._check_rule_violations(step, chain_data.get("conditions", []), projected)
                all_violations.extend(violations)

            risk_score = self._calculate_risk_score(all_impacts, all_violations)
            risk_level = "low" if risk_score < 30 else "medium" if risk_score < 60 else "high" if risk_score < 80 else "critical"
            recommendation = self._generate_chain_recommendation(all_impacts, all_violations, risk_level)
            confidence = self._compute_chain_confidence(baseline, chain_data, all_violations)

            result = ChainResult(
                chain_id=chain_id,
                status=ChainStatus.COMPLETED,
                metric_impacts=[MetricImpact(**m) for m in all_impacts],
                risk_level=risk_level,
                risk_score=risk_score,
                rule_violations=[RuleViolation(**v) for v in all_violations],
                recommendation=recommendation,
                confidence=confidence,
                projected_state=projected,
            )

            results = data.get("results", [])
            existing_idx = None
            for i, r in enumerate(results):
                if r.get("chain_id") == chain_id:
                    existing_idx = i
                    break
            result_dict = result.model_dump(mode="json")
            if existing_idx is not None:
                results[existing_idx] = result_dict
            else:
                results.append(result_dict)

            chain_data["status"] = ChainStatus.COMPLETED.value
            data["results"] = results
            data["status"] = DeductionStatus.COMPLETED.value
            data["updated_at"] = datetime.now().isoformat()
            self._storage.save_scenario(data)
            return result_dict

        except Exception as e:
            logger.error(f"Simulate chain failed: {e}")
            chain_data["status"] = ChainStatus.FAILED.value
            data["status"] = DeductionStatus.FAILED.value
            self._storage.save_scenario(data)
            return {"status": "error", "message": str(e)}

    async def simulate_all_chains(self, scenario_id: str) -> Dict[str, Any]:
        data = self._storage.get_scenario(scenario_id)
        if not data:
            return {"status": "error", "message": "Scenario not found"}

        results = []
        for chain in data.get("chains", []):
            result = await self.simulate_chain(scenario_id, chain.get("chain_id", ""))
            if result.get("status") != "error":
                results.append(result)

        best_chain_id = None
        if results:
            best = min(results, key=lambda r: r.get("risk_score", 100))
            best_chain_id = best.get("chain_id")

        data = self._storage.get_scenario(scenario_id)
        if data:
            data["best_chain_id"] = best_chain_id
            data["updated_at"] = datetime.now().isoformat()
            self._storage.save_scenario(data)

        return {
            "scenario_id": scenario_id,
            "results": results,
            "best_chain_id": best_chain_id,
            "total_chains": len(data.get("chains", [])) if data else 0,
        }

    async def compare_chains(self, scenario_id: str,
                              chain_ids: List[str]) -> Dict[str, Any]:
        data = self._storage.get_scenario(scenario_id)
        if not data:
            return {"status": "error", "message": "Scenario not found"}

        results = []
        for chain_id in chain_ids:
            chain_result = None
            for r in data.get("results", []):
                if r.get("chain_id") == chain_id:
                    chain_result = r
                    break
            if not chain_result:
                result = await self.simulate_chain(scenario_id, chain_id)
                if result.get("status") != "error":
                    chain_result = result
            if chain_result:
                results.append(chain_result)

        comparison = []
        if results:
            metrics_set = set()
            for r in results:
                for m in r.get("metric_impacts", []):
                    metrics_set.add(m.get("metric_name", ""))

            for metric in sorted(metrics_set):
                values = {}
                for r in results:
                    for m in r.get("metric_impacts", []):
                        if m.get("metric_name") == metric:
                            values[r.get("chain_id", "")] = m.get("delta", 0)
                comparison.append({"metric_name": metric, "values": values})

        best_chain_id = None
        if results:
            best = min(results, key=lambda r: r.get("risk_score", 100))
            best_chain_id = best.get("chain_id")

        return {
            "scenario_id": scenario_id,
            "comparison": comparison,
            "results": results,
            "best_chain_id": best_chain_id,
        }

    async def get_scenario(self, scenario_id: str) -> Dict[str, Any]:
        data = self._storage.get_scenario(scenario_id)
        if not data:
            return {"status": "error", "message": "Scenario not found"}
        return data

    async def list_scenarios(self, filters: Dict[str, Any] = None,
                              page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        return self._storage.list_scenarios(filters=filters, page=page, page_size=page_size)

    async def delete_scenario(self, scenario_id: str) -> Dict[str, Any]:
        deleted = self._storage.delete_scenario(scenario_id)
        if not deleted:
            return {"status": "error", "message": "Scenario not found"}
        return {"status": "ok", "scenario_id": scenario_id}

    async def _capture_baseline(self, target_id: str, target_type: str) -> Dict[str, Any]:
        baseline = {"target_id": target_id, "target_type": target_type}
        try:
            from odap.infra.query import get_query_service
            query_service = get_query_service()
            result = query_service.execute(
                workspace_id="default",
                query=f".entity with(type='{target_type}') list()",
                limit=20,
            )
            for entity in result.rows[:20]:
                eid = entity.get('id', '')
                if eid == target_id:
                    props = entity.get('properties', {})
                    for key in ('capability_index', 'readiness', 'resource_level', 'personnel', 'status'):
                        if key in props:
                            baseline[key] = props[key]
                    break
        except Exception as e:
            logger.warning(f"Capture baseline from graph failed: {e}")

        try:
            if self.oms:
                type_def = self.oms.get_object_type(target_type)
                if type_def:
                    for prop in type_def.get('properties', []):
                        if prop.get('category') == 'statistical_properties':
                            pname = prop.get('name', '')
                            if pname and pname not in baseline:
                                baseline[pname] = 0
        except Exception as e:
            logger.warning(f"Capture baseline from OMS failed: {e}")

        return baseline

    async def _load_rules(self, target_type: str) -> List[Dict[str, Any]]:
        rules = []
        try:
            if self.oms:
                action_types = self.oms.list_action_types()
                for at in action_types:
                    if at.get('target_object_type', '') == target_type:
                        rules.append({
                            'rule_id': f"rule-action-{at.get('action_type_id', '')}",
                            'rule_type': 'action_constraint',
                            'description': f"动作类型约束: {at.get('display_name', at.get('name', ''))}",
                            'condition': f"action_type == '{at.get('action_type_id', '')}'",
                            'consequence': {'required_roles': at.get('required_roles', [])},
                        })
        except Exception as e:
            logger.warning(f"Load rules from OMS failed: {e}")
        return rules

    async def _load_constraints(self, target_type: str) -> List[Dict[str, Any]]:
        constraints = []
        try:
            if self.oms:
                type_def = self.oms.get_object_type(target_type)
                if type_def:
                    for prop in type_def.get('properties', []):
                        prop_constraints = prop.get('constraints', {})
                        if prop_constraints:
                            constraints.append({
                                'constraint_id': f"cst-prop-{prop.get('name', '')}",
                                'constraint_type': 'property_constraint',
                                'description': f"属性约束: {prop.get('name', '')}",
                                'scope': {'property': prop.get('name', ''), 'type': prop.get('property_type', '')},
                                'violation_consequence': 'warning',
                            })
        except Exception as e:
            logger.warning(f"Load constraints from OMS failed: {e}")
        return constraints

    async def _simulate_step(self, step: Dict[str, Any], current_state: Dict[str, Any],
                              chain_conditions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        impacts = []
        action_type_id = step.get("action_type_id", "")

        try:
            from odap.biz.simulation.simulation_sandbox.sandbox import get_simulation_sandbox
            sandbox = get_simulation_sandbox()
            impact_rules = sandbox._load_impact_rules(action_type_id)
            for metric, delta in impact_rules.items():
                before = current_state.get(metric)
                if before is not None and isinstance(before, (int, float)):
                    after = before + delta * (before if before > 1 else 1)
                    impacts.append({
                        "metric_name": metric,
                        "before": before,
                        "after": round(after, 2),
                        "delta": round(delta, 3),
                        "unit": "",
                        "confidence": 0.6,
                    })
                elif delta != 0:
                    impacts.append({
                        "metric_name": metric,
                        "before": before,
                        "after": None,
                        "delta": round(delta, 3),
                        "unit": "",
                        "confidence": 0.4,
                    })
        except Exception as e:
            logger.warning(f"Load impact rules for step failed: {e}")

        for cond in chain_conditions:
            if cond.get("is_active", True) and cond.get("value") is not None:
                cond_impact = self._apply_condition_impact(cond, current_state)
                impacts.extend(cond_impact)

        propagation_impacts = self._compute_propagation_impacts(action_type_id, step, current_state)
        impacts.extend(propagation_impacts)

        return impacts

    def _compute_propagation_impacts(self, action_type_id: str, step: Dict[str, Any], current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        impacts = []
        try:
            from odap.biz.core.ontology.application.runtime.services.runtime_service import OntologyRuntimeService
            service = OntologyRuntimeService.get_instance()
            contract_result = service.get_contract_by_action(action_type_id)
            if contract_result.get("status") == "error":
                return impacts
            side_effects = contract_result.get("side_effect_set", [])
            overall_magnitude = 0.05
            try:
                if self.oms:
                    action_def = self.oms.get_action_type(action_type_id)
                    if action_def and action_def.get('parameters'):
                        for p in action_def.get('parameters', []):
                            default_val = p.get('default')
                            if default_val is not None:
                                try:
                                    overall_magnitude = max(overall_magnitude, abs(float(default_val)) / (abs(float(default_val)) + 1) * 0.1)
                                except (ValueError, TypeError):
                                    pass
            except Exception as e:
                logger.debug("OMS fallback: %s", e)
            for se in side_effects:
                obj_type = se.get("object_type", "")
                prop = se.get("property_name", "")
                if obj_type and prop:
                    current_val = current_state.get(prop)
                    magnitude = se.get("magnitude")
                    direction = se.get("direction", "negative")
                    if magnitude is not None:
                        try:
                            mag_val = float(magnitude)
                            estimated_delta = mag_val if direction == "positive" else -abs(mag_val)
                        except (ValueError, TypeError):
                            estimated_delta = -overall_magnitude
                    else:
                        estimated_delta = -overall_magnitude if direction != "positive" else overall_magnitude
                    impacts.append({
                        "metric_name": f"{obj_type}.{prop}",
                        "before": current_val,
                        "after": None,
                        "delta": round(estimated_delta, 3),
                        "unit": "",
                        "confidence": 0.3,
                        "propagation_type": "side_effect",
                    })
        except Exception as e:
            logger.debug(f"Propagation impact computation skipped: {e}")
        return impacts

    def _apply_condition_impact(self, condition: Dict[str, Any],
                                 current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        impacts = []
        cond_type = condition.get("condition_type", "custom")
        value = condition.get("value")

        if cond_type == "rule_based" and isinstance(value, dict):
            for metric, delta in value.items():
                if isinstance(delta, (int, float)):
                    impacts.append({
                        "metric_name": metric,
                        "before": current_state.get(metric),
                        "after": None,
                        "delta": round(delta, 3),
                        "unit": "",
                        "confidence": 0.5,
                    })
        elif cond_type == "constraint_based" and isinstance(value, (int, float)):
            scope = condition.get("expression", {})
            prop_name = scope.get("property", "") if isinstance(scope, dict) else ""
            if prop_name:
                before = current_state.get(prop_name)
                impacts.append({
                    "metric_name": prop_name,
                    "before": before,
                    "after": value,
                    "delta": round(value - (before if isinstance(before, (int, float)) else 0), 3),
                    "unit": "",
                    "confidence": 0.7,
                })

        return impacts

    def _check_rule_violations(self, step: Dict[str, Any],
                                conditions: List[Dict[str, Any]],
                                projected_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        violations = []
        for cond in conditions:
            if not cond.get("is_active", True):
                continue
            cond_type = cond.get("condition_type", "custom")
            if cond_type == "constraint_based":
                scope = cond.get("expression", {})
                if isinstance(scope, dict):
                    prop_name = scope.get("property", "")
                    if prop_name:
                        current_val = projected_state.get(prop_name)
                        min_val = cond.get("min_value")
                        max_val = cond.get("max_value")
                        if min_val is not None and isinstance(current_val, (int, float)) and current_val < min_val:
                            violations.append({
                                "rule_id": cond.get("source_constraint_id", ""),
                                "rule_type": "constraint_violation",
                                "description": f"属性 {prop_name} 值 {current_val} 低于最小值 {min_val}",
                                "severity": cond.get("parameters", {}).get("violation_consequence", "warning"),
                                "violated_condition": cond.get("name", ""),
                            })
                        if max_val is not None and isinstance(current_val, (int, float)) and current_val > max_val:
                            violations.append({
                                "rule_id": cond.get("source_constraint_id", ""),
                                "rule_type": "constraint_violation",
                                "description": f"属性 {prop_name} 值 {current_val} 超过最大值 {max_val}",
                                "severity": cond.get("parameters", {}).get("violation_consequence", "warning"),
                                "violated_condition": cond.get("name", ""),
                            })
        return violations

    def _calculate_risk_score(self, impacts: List[Dict[str, Any]],
                               violations: List[Dict[str, Any]]) -> float:
        score = 0.0
        for impact in impacts:
            delta = impact.get("delta", 0)
            if delta is not None and delta < 0:
                score += abs(delta) * 50
        for violation in violations:
            severity = violation.get("severity", "warning")
            if severity == "critical":
                score += 30
            elif severity == "warning":
                score += 10
            else:
                score += 5
        return min(score, 100.0)

    def _compute_chain_confidence(self, baseline: Dict[str, Any], chain_data: Dict[str, Any], violations: List[Dict[str, Any]]) -> float:
        confidence = 0.5
        real_data_keys = [k for k in ('capability_index', 'readiness', 'resource_level', 'personnel', 'status') if k in baseline and baseline[k] is not None and baseline[k] != 0]
        if real_data_keys:
            confidence += 0.1
        try:
            if self.oms:
                for step in chain_data.get("steps", []):
                    action_type_id = step.get("action_type_id", "")
                    action_def = self.oms.get_action_type(action_type_id)
                    if action_def and action_def.get('parameters'):
                        confidence += 0.05
                        break
        except Exception as e:
            logger.debug("OMS fallback: %s", e)
        if not violations:
            confidence += 0.1
        steps_with_data = 0
        for step in chain_data.get("steps", []):
            step_params = step.get("parameters", {})
            if step_params:
                steps_with_data += 1
        confidence += min(0.1, steps_with_data * 0.05)
        return min(0.95, confidence)

    def _generate_chain_recommendation(self, impacts: List[Dict[str, Any]],
                                        violations: List[Dict[str, Any]],
                                        risk_level: str) -> str:
        negative = [i for i in impacts if i.get("delta", 0) is not None and i["delta"] < 0]
        positive = [i for i in impacts if i.get("delta", 0) is not None and i["delta"] > 0]

        parts = []
        if risk_level == "critical":
            parts.append("极高风险，强烈不建议执行。")
        elif risk_level == "high":
            parts.append("高风险操作，建议谨慎评估后执行。")
        elif risk_level == "medium":
            parts.append("中等风险，建议评估后执行。")
        else:
            parts.append("低风险，可以安全执行。")

        if negative:
            metrics = ", ".join(f"{i['metric_name']}({i['delta']:.1%})" for i in negative[:3])
            parts.append(f"负面指标: {metrics}。")
        if positive:
            metrics = ", ".join(f"{i['metric_name']}(+{i['delta']:.1%})" for i in positive[:3])
            parts.append(f"正面指标: {metrics}。")
        if violations:
            parts.append(f"存在 {len(violations)} 项规则/约束违反。")

        return "".join(parts)
