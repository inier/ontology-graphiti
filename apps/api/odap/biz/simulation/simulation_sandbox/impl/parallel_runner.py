import asyncio
import logging
import uuid
from collections import deque
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..sandbox import get_simulation_sandbox
from ..schemas import WhatIfScenario

logger = logging.getLogger(__name__)

MAX_PARALLEL = 10


class ScenarioQueue:
    """推演方案 FIFO 队列

    当推演方案数量超过 MAX_PARALLEL 时，将多余的方案放入队列等待执行。
    当某个方案完成后，自动从队列中取出下一个方案执行。
    """

    def __init__(self, max_parallel: int = MAX_PARALLEL):
        self._queue: deque = deque()
        self._running: int = 0
        self._max_parallel = max_parallel
        self._positions: Dict[str, int] = {}  # scenario_id -> queue position
        self._results: Dict[str, Dict[str, Any]] = {}  # scenario_id -> result
        self._completion_events: Dict[str, asyncio.Event] = {}
        self._avg_duration_seconds: float = 5.0  # 默认估计每个方案5秒

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def running_count(self) -> int:
        return self._running

    def enqueue(self, scenario_id: str, scenario_data: Dict[str, Any]) -> Dict[str, Any]:
        """将方案加入队列

        Args:
            scenario_id: 方案ID
            scenario_data: 方案数据

        Returns:
            入队结果，包含状态和队列位置信息
        """
        if self._running < self._max_parallel:
            self._running += 1
            return {"status": "ready", "position": 0}

        position = len(self._queue) + 1
        self._queue.append({
            "scenario_id": scenario_id,
            "scenario_data": scenario_data,
        })
        self._positions[scenario_id] = position

        estimated_wait = position * self._avg_duration_seconds
        return {
            "status": "queued",
            "position": position,
            "estimated_wait": f"~{estimated_wait:.0f}s",
        }

    def dequeue(self) -> Optional[Dict[str, Any]]:
        """从队列中取出下一个方案

        Returns:
            下一个方案数据，如果队列为空则返回 None
        """
        if not self._queue:
            return None

        item = self._queue.popleft()
        scenario_id = item["scenario_id"]

        # 更新剩余方案的队列位置
        self._positions.pop(scenario_id, None)
        for i, queued_item in enumerate(self._queue):
            self._positions[queued_item["scenario_id"]] = i + 1

        self._running += 1
        return item

    def complete(self, scenario_id: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """标记方案完成，自动启动队列中的下一个方案

        Args:
            scenario_id: 完成的方案ID
            result: 方案执行结果

        Returns:
            下一个待执行的方案数据，如果没有则返回 None
        """
        self._running = max(0, self._running - 1)
        self._results[scenario_id] = result

        # 通知等待的协程
        event = self._completion_events.get(scenario_id)
        if event:
            event.set()

        # 自动启动下一个
        return self.dequeue()

    def get_position(self, scenario_id: str) -> int:
        """获取方案在队列中的位置"""
        return self._positions.get(scenario_id, 0)

    def get_result(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        """获取已完成方案的结果"""
        return self._results.get(scenario_id)

    def get_completion_event(self, scenario_id: str) -> asyncio.Event:
        """获取方案完成事件，用于异步等待"""
        if scenario_id not in self._completion_events:
            self._completion_events[scenario_id] = asyncio.Event()
        return self._completion_events[scenario_id]

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "queue_size": len(self._queue),
            "running_count": self._running,
            "max_parallel": self._max_parallel,
            "queued_scenarios": [
                {
                    "scenario_id": item["scenario_id"],
                    "position": self._positions.get(item["scenario_id"], 0),
                }
                for item in self._queue
            ],
        }


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
        self._scenario_queue = ScenarioQueue(max_parallel=MAX_PARALLEL)
        self._initialized = True

    async def _notify_queue_position(self, scenario_id: str, position: int, estimated_wait: str):
        """通过 WebSocket 通知队列位置更新"""
        try:
            from odap.infra.events.event_bus import get_event_bus
            bus = get_event_bus()
            await bus.emit("simulation:queue_update", {
                "scenario_id": scenario_id,
                "position": position,
                "estimated_wait": estimated_wait,
            })
        except Exception as e:
            logger.debug(f"WebSocket 通知失败（非关键）: {e}")

    async def _run_scenario_with_queue(
        self,
        scenario: WhatIfScenario,
        queue_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行单个方案，支持排队等待

        Args:
            scenario: 方案对象
            queue_info: 入队信息

        Returns:
            方案执行结果
        """
        scenario_id = scenario.scenario_id

        # 如果在队列中，通知位置并等待
        if queue_info["status"] == "queued":
            position = queue_info["position"]
            estimated_wait = queue_info.get("estimated_wait", "unknown")
            await self._notify_queue_position(scenario_id, position, estimated_wait)

            # 等待轮到该方案执行
            event = self._scenario_queue.get_completion_event(scenario_id)
            await event.wait()

        # 执行方案
        sim_sandbox = get_simulation_sandbox()
        try:
            result = await sim_sandbox.simulate(scenario)
            processed = {
                "scenario_id": result.scenario_id,
                "name": scenario.name,
                "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
                "baseline_metrics": result.baseline_metrics,
                "projected_metrics": result.projected_metrics,
                "metric_changes": [mc.model_dump() for mc in result.metric_changes],
                "risk_assessment": result.risk_assessment,
                "recommendation": result.recommendation,
                "confidence": result.confidence,
            }
        except Exception as e:
            processed = {
                "scenario_id": scenario_id,
                "name": scenario.name,
                "status": "failed",
                "error": str(e),
            }

        # 标记完成，自动启动下一个
        next_item = self._scenario_queue.complete(scenario_id, processed)

        # 如果有下一个方案，启动它
        if next_item:
            next_scenario_data = next_item["scenario_data"]
            next_id = next_item["scenario_id"]
            # 通知位置更新（现在是第0位，即将执行）
            await self._notify_queue_position(next_id, 0, "starting")

        return processed

    async def run_parallel(self, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not scenarios:
            return {"status": "error", "message": "No scenarios provided"}

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

        # 使用排队机制：超过 MAX_PARALLEL 的方案自动排队
        queue_infos = []
        for ws in whatif_scenarios:
            info = self._scenario_queue.enqueue(
                ws.scenario_id,
                {"scenario": ws},
            )
            queue_infos.append(info)

        # 收集排队信息
        queued_count = sum(1 for info in queue_infos if info["status"] == "queued")
        if queued_count > 0:
            logger.info(f"推演排队: {queued_count} 个方案在队列中等待")

        # 启动所有任务（排队机制内部会控制并发）
        tasks = [
            self._run_scenario_with_queue(ws, qi)
            for ws, qi in zip(whatif_scenarios, queue_infos)
        ]
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
                processed_results.append(result)

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
            "queued_count": queued_count,
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

        # 使用排队机制
        queue_infos = []
        for ws in scenarios:
            info = self._scenario_queue.enqueue(
                ws.scenario_id,
                {"scenario": ws},
            )
            queue_infos.append(info)

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

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return self._scenario_queue.get_queue_status()

    def _build_comparison(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        metrics_comparison: Optional[Dict[str, List[Dict[str, Any]]]] = None
        if metrics_comparison is None:
            metrics_comparison = {}
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
