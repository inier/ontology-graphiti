import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..sandbox import get_simulation_sandbox
from ..schemas import WhatIfScenario

logger = logging.getLogger(__name__)

MAX_PARALLEL = 10


class ParallelRunner:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._comparison_cache: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

    async def run_parallel(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not scenarios:
            return {"status": "error", "message": "No scenarios provided"}
        if len(scenarios) > MAX_PARALLEL:
            return {"status": "error", "message": f"Maximum {MAX_PARALLEL} scenarios allowed"}

        run_id = f"parallel_{uuid.uuid4().hex[:12]}"
        sim_sandbox = get_simulation_sandbox()

        whatif_scenarios = []
        for i, sc in enumerate(scenarios):
            whatif_scenarios.append(WhatIfScenario(
                scenario_id=sc.get("scenario_id", f"scenario_{i}"),
                name=sc.get("name", f"Scenario {i + 1}"),
                description=sc.get("description", ""),
                action_type_id=sc.get("action_type_id", ""),
                target_object_id=sc.get("target_object_id", ""),
                target_object_type=sc.get("target_object_type", ""),
                parameters=sc.get("parameters", {}),
                variant_parameters=sc.get("variant_parameters", []),
            ))

        tasks = [sim_sandbox.simulate(s) for s in whatif_scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "scenario_id": whatif_scenarios[i].scenario_id,
                    "name": whatif_scenarios[i].name,
                    "status": "failed",
                    "error": str(result),
                })
            else:
                processed_results.append({
                    "scenario_id": result.scenario_id,
                    "name": whatif_scenarios[i].name,
                    "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
                    "baseline_metrics": result.baseline_metrics,
                    "projected_metrics": result.projected_metrics,
                    "metric_changes": [mc.model_dump() for mc in result.metric_changes],
                    "risk_assessment": result.risk_assessment,
                    "recommendation": result.recommendation,
                    "confidence": result.confidence,
                })

        best_id = None
        best_risk = float("inf")
        for r in processed_results:
            if r.get("status") == "failed":
                continue
            risk = r.get("risk_assessment", {}).get("overall_risk", "high")
            risk_score = {"low": 1, "medium": 2, "high": 3}.get(risk, 3)
            if risk_score < best_risk:
                best_risk = risk_score
                best_id = r.get("scenario_id")

        comparison = self._build_comparison(processed_results)

        output = {
            "run_id": run_id,
            "status": "completed",
            "total_scenarios": len(scenarios),
            "results": processed_results,
            "best_scenario_id": best_id,
            "comparison": comparison,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        self._comparison_cache[run_id] = output
        return output

    async def run_what_if(
        self,
        base_scenario: Dict[str, Any],
        param_variations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not param_variations:
            return {"status": "error", "message": "No parameter variations provided"}
        if len(param_variations) > MAX_PARALLEL:
            return {"status": "error", "message": f"Maximum {MAX_PARALLEL} variations allowed"}

        run_id = f"whatif_{uuid.uuid4().hex[:12]}"
        sim_sandbox = get_simulation_sandbox()

        scenarios = []
        for i, variation in enumerate(param_variations):
            merged_params = {**base_scenario.get("parameters", {}), **variation}
            scenarios.append(WhatIfScenario(
                scenario_id=f"whatif_{i}",
                name=f"What-if {i + 1}: {list(variation.keys())}",
                description=f"Variation {i + 1}: {variation}",
                action_type_id=base_scenario.get("action_type_id", ""),
                target_object_id=base_scenario.get("target_object_id", ""),
                target_object_type=base_scenario.get("target_object_type", ""),
                parameters=merged_params,
            ))

        tasks = [sim_sandbox.simulate(s) for s in scenarios]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        sensitivity = {}
        processed_results = []
        for i, result in enumerate(results):
            variation = param_variations[i]
            if isinstance(result, Exception):
                processed_results.append({
                    "scenario_id": f"whatif_{i}",
                    "status": "failed",
                    "error": str(result),
                    "variation": variation,
                })
                continue

            processed_results.append({
                "scenario_id": result.scenario_id,
                "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
                "metric_changes": [mc.model_dump() for mc in result.metric_changes],
                "risk_assessment": result.risk_assessment,
                "recommendation": result.recommendation,
                "confidence": result.confidence,
                "variation": variation,
            })

            for mc in result.metric_changes:
                metric_name = mc.metric_name
                if metric_name not in sensitivity:
                    sensitivity[metric_name] = []
                sensitivity[metric_name].append({
                    "variation": variation,
                    "delta": mc.delta,
                })

        output = {
            "run_id": run_id,
            "status": "completed",
            "base_scenario": base_scenario,
            "total_variations": len(param_variations),
            "results": processed_results,
            "sensitivity_analysis": sensitivity,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        self._comparison_cache[run_id] = output
        return output

    def get_comparison(self, run_id: str) -> Dict[str, Any]:
        result = self._comparison_cache.get(run_id)
        if not result:
            return {"status": "error", "message": f"Comparison {run_id} not found"}
        return result

    def compare_by_ids(self, ids: List[str]) -> Dict[str, Any]:
        results = []
        for rid in ids:
            cached = self._comparison_cache.get(rid)
            if cached:
                results.append(cached)
        if not results:
            return {"status": "error", "message": "No valid run IDs found"}

        all_scenario_results = []
        for r in results:
            all_scenario_results.extend(r.get("results", []))

        comparison = self._build_comparison(all_scenario_results)
        return {
            "status": "completed",
            "run_ids": ids,
            "total_results": len(all_scenario_results),
            "comparison": comparison,
        }

    def _build_comparison(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        metrics_comparison: Dict[str, List[Dict[str, Any]]] = {}
        for r in results:
            if r.get("status") == "failed":
                continue
            scenario_id = r.get("scenario_id", "unknown")
            for mc in r.get("metric_changes", []):
                metric_name = mc.get("metric_name", "")
                if metric_name not in metrics_comparison:
                    metrics_comparison[metric_name] = []
                metrics_comparison[metric_name].append({
                    "scenario_id": scenario_id,
                    "before": mc.get("before"),
                    "after": mc.get("after"),
                    "delta": mc.get("delta"),
                })

        highlighted = []
        for metric_name, values in metrics_comparison.items():
            if len(values) < 2:
                continue
            deltas = [v["delta"] for v in values if v.get("delta") is not None]
            if not deltas:
                continue
            max_delta = max(deltas, key=abs)
            min_delta = min(deltas, key=abs)
            spread = abs(max_delta - min_delta) if max_delta != min_delta else 0
            if spread > 0.1:
                highlighted.append({
                    "metric_name": metric_name,
                    "spread": round(spread, 4),
                    "values": values,
                })

        return {
            "metrics_comparison": metrics_comparison,
            "highlighted_differences": highlighted,
        }


def get_parallel_runner() -> ParallelRunner:
    return ParallelRunner()
