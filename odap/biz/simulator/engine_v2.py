"""
模拟推演引擎 v2 - What-if 分析 + 方案版本管理增强

功能：
- What-if 分析
- 方案版本管理增强
- 事件模板管理
- 时间控制
"""

import sys
import os
import json
import time
import asyncio
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import deque

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator.engine import SimulationEngine as SimulationEngineV1, SandboxState, ScenarioVersion, SimulationResult


class WhatIfType(Enum):
    """What-If 分析类型"""
    PARAMETER_CHANGE = "parameter_change"
    SCENARIO_INJECTION = "scenario_injection"
    FORCE_COMPARISON = "force_comparison"
    THREAT_ASSESSMENT = "threat_assessment"


@dataclass
class WhatIfScenario:
    """What-If 场景"""
    scenario_id: str
    what_if_type: str
    description: str
    parameter_changes: Dict[str, Any]
    expected_outcome: str
    actual_outcome: Optional[str] = None
    deviation: Optional[float] = None
    created_at: str = ""


@dataclass
class WhatIfResult:
    """What-If 分析结果"""
    baseline_result: SimulationResult
    what_if_result: SimulationResult
    comparison: Dict[str, Any]
    deviation_analysis: List[Dict[str, Any]]


class EventTemplate:
    """事件模板"""

    def __init__(self, template_id: str, name: str, description: str, parameters: Dict):
        self.template_id = template_id
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'EventTemplate':
        return cls(
            template_id=data["template_id"],
            name=data["name"],
            description=data["description"],
            parameters=data["parameters"]
        )


class EventTemplateManager:
    """事件模板管理器"""

    def __init__(self):
        self._templates: Dict[str, EventTemplate] = {}
        self._init_default_templates()

    def _init_default_templates(self):
        """初始化默认模板"""
        self.register(EventTemplate(
            template_id="contact_event",
            name="接触事件",
            description="双方部队接触",
            parameters={
                "type": "contact",
                "probability": 0.7,
                "escalation_factor": 1.2
            }
        ))

        self.register(EventTemplate(
            template_id="air_strike_event",
            name="空袭事件",
            description="空中打击",
            parameters={
                "type": "air_strike",
                "damage_range": [10, 50],
                "success_rate": 0.8
            }
        ))

        self.register(EventTemplate(
            template_id="reinforcement_event",
            name="增援事件",
            description="部队增援",
            parameters={
                "type": "reinforcement",
                "strength_increase": 20,
                "arrival_time_hours": 2
            }
        ))

        self.register(EventTemplate(
            template_id="retreat_event",
            name="撤退事件",
            description="部队撤退",
            parameters={
                "type": "retreat",
                "strength_loss": 30,
                "morale_impact": -0.2
            }
        ))

    def register(self, template: EventTemplate):
        """注册模板"""
        self._templates[template.template_id] = template

    def get(self, template_id: str) -> Optional[EventTemplate]:
        """获取模板"""
        return self._templates.get(template_id)

    def list_templates(self) -> List[EventTemplate]:
        """列出所有模板"""
        return list(self._templates.values())

    def create_event(self, template_id: str, **overrides) -> Dict[str, Any]:
        """从模板创建事件"""
        template = self.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        event = template.parameters.copy()
        event.update(overrides)
        event["template_id"] = template_id
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        return event


class SimulationEngineV2:
    """
    模拟推演引擎 v2

    增强功能：
    - What-if 分析
    - 事件模板管理
    - 方案版本管理增强
    - 时间控制
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, storage_path: str = "/tmp/simulations_v2"):
        if self._initialized:
            return

        self._v1_engine = SimulationEngineV1.get_instance(storage_path)
        self._template_manager = EventTemplateManager()
        self._what_if_history: List[WhatIfResult] = []
        self._time_scale = 1.0
        self._max_history = 100
        self._initialized = True

    @classmethod
    def get_instance(cls, storage_path: str = "/tmp/simulations_v2") -> 'SimulationEngineV2':
        if cls._instance is None:
            cls._instance = cls(storage_path)
        return cls._instance

    async def create_scenario(self, name: str, initial_parameters: Dict[str, Any]) -> str:
        """创建推演方案"""
        return await self._v1_engine.create_scenario(name, initial_parameters)

    async def create_branch(self, scenario_id: str, base_version_id: str,
                          new_parameters: Dict[str, Any],
                          branch_message: str) -> str:
        """创建分支版本"""
        return await self._v1_engine.create_branch(scenario_id, base_version_id,
                                                  new_parameters, branch_message)

    async def rollback_to_version(self, scenario_id: str, version_id: str) -> bool:
        """回退版本"""
        return await self._v1_engine.rollback_to_version(scenario_id, version_id)

    async def run_simulation(self, scenario_id: str, version_id: str,
                            max_steps: int = 100) -> SimulationResult:
        """运行推演"""
        return await self._v1_engine.run_simulation(scenario_id, version_id, max_steps)

    def get_scenario_versions(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取方案版本"""
        return self._v1_engine.get_scenario_versions(scenario_id)

    def get_result(self, result_id: str) -> Optional[SimulationResult]:
        """获取推演结果"""
        return self._v1_engine.get_result(result_id)

    def compare_versions(self, scenario_id: str, version_a: str, version_b: str) -> Dict[str, Any]:
        """对比版本"""
        return self._v1_engine.compare_versions(scenario_id, version_a, version_b)

    async def what_if_analysis(self, scenario_id: str, version_id: str,
                             parameter_changes: Dict[str, Any],
                             description: str = "",
                             max_steps: int = 100) -> WhatIfResult:
        """
        What-If 分析

        Args:
            scenario_id: 方案 ID
            version_id: 版本 ID
            parameter_changes: 参数变更
            description: 描述
            max_steps: 最大步数

        Returns:
            What-If 分析结果
        """
        versions = self.get_scenario_versions(scenario_id)
        target_version = None
        for v in versions:
            if v["version_id"] == version_id:
                target_version = v
                break

        if not target_version:
            raise ValueError(f"Version not found: {version_id}")

        baseline_params = target_version["parameters"].copy()
        baseline_result = await self.run_simulation(scenario_id, version_id, max_steps)

        what_if_params = baseline_params.copy()
        what_if_params.update(parameter_changes)

        what_if_version_id = await self._v1_engine._create_version(
            scenario_id, version_id, what_if_params, f"What-If: {description}"
        )

        what_if_result = await self.run_simulation(scenario_id, what_if_version_id, max_steps)

        comparison = self._compare_results(baseline_result, what_if_result)
        deviation_analysis = self._analyze_deviation(baseline_result, what_if_result)

        result = WhatIfResult(
            baseline_result=baseline_result,
            what_if_result=what_if_result,
            comparison=comparison,
            deviation_analysis=deviation_analysis
        )

        self._what_if_history.append(result)
        if len(self._what_if_history) > self._max_history:
            self._what_if_history.pop(0)

        return result

    def _compare_results(self, baseline: SimulationResult,
                       what_if: SimulationResult) -> Dict[str, Any]:
        """比较两个结果"""
        baseline_metrics = baseline.metrics
        what_if_metrics = what_if.metrics

        metric_diffs = {}
        for key in baseline_metrics:
            if key in what_if_metrics:
                diff = what_if_metrics[key] - baseline_metrics[key]
                pct_change = (diff / baseline_metrics[key] * 100) if baseline_metrics[key] != 0 else 0
                metric_diffs[key] = {
                    "baseline": baseline_metrics[key],
                    "what_if": what_if_metrics[key],
                    "difference": diff,
                    "percent_change": pct_change
                }

        return {
            "baseline_success": baseline.success,
            "what_if_success": what_if.success,
            "execution_time_diff_ms": what_if.execution_time_ms - baseline.execution_time_ms,
            "event_count_diff": len(what_if.events) - len(baseline.events),
            "metrics": metric_diffs
        }

    def _analyze_deviation(self, baseline: SimulationResult,
                          what_if: SimulationResult) -> List[Dict[str, Any]]:
        """分析偏差"""
        analysis = []

        friendly_diff = (what_if.final_state.get("friendly_strength", 0) -
                        baseline.final_state.get("friendly_strength", 0))
        enemy_diff = (what_if.final_state.get("enemy_strength", 0) -
                     baseline.final_state.get("enemy_strength", 0))

        analysis.append({
            "metric": "friendly_strength",
            "baseline": baseline.final_state.get("friendly_strength", 0),
            "what_if": what_if.final_state.get("friendly_strength", 0),
            "deviation": friendly_diff,
            "impact": "positive" if friendly_diff > 0 else "negative" if friendly_diff < 0 else "neutral"
        })

        analysis.append({
            "metric": "enemy_strength",
            "baseline": baseline.final_state.get("enemy_strength", 0),
            "what_if": what_if.final_state.get("enemy_strength", 0),
            "deviation": enemy_diff,
            "impact": "positive" if enemy_diff < 0 else "negative" if enemy_diff > 0 else "neutral"
        })

        return analysis

    async def what_if_parameter_sweep(self, scenario_id: str, version_id: str,
                                     parameter: str, values: List[Any],
                                     max_steps: int = 100) -> List[WhatIfResult]:
        """
        参数扫描 What-If 分析

        Args:
            scenario_id: 方案 ID
            version_id: 版本 ID
            parameter: 参数名
            values: 参数值列表
            max_steps: 最大步数

        Returns:
            每个参数值的 What-If 结果
        """
        results = []
        for value in values:
            result = await self.what_if_analysis(
                scenario_id, version_id,
                {parameter: value},
                f"Sweep {parameter}={value}",
                max_steps
            )
            results.append(result)
        return results

    def get_template_manager(self) -> EventTemplateManager:
        """获取模板管理器"""
        return self._template_manager

    def create_event_from_template(self, template_id: str, **overrides) -> Dict[str, Any]:
        """从模板创建事件"""
        return self._template_manager.create_event(template_id, **overrides)

    def set_time_scale(self, scale: float):
        """设置时间缩放"""
        self._time_scale = max(0.1, min(10.0, scale))

    def get_time_scale(self) -> float:
        """获取时间缩放"""
        return self._time_scale

    def get_what_if_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取 What-If 历史"""
        history = self._what_if_history[-limit:]
        return [{
            "baseline_result_id": r.baseline_result.result_id,
            "what_if_result_id": r.what_if_result.result_id,
            "comparison": r.comparison
        } for r in reversed(history)]

    def get_active_sandboxes(self) -> Dict[str, str]:
        """获取活跃沙箱"""
        return self._v1_engine.get_active_sandboxes()

    async def terminate_sandbox(self, sandbox_id: str) -> bool:
        """终止沙箱"""
        return await self._v1_engine.terminate_sandbox(sandbox_id)


if __name__ == "__main__":
    print("模拟推演引擎 v2 测试")

    print("\n=== 测试引擎初始化 ===")
    engine = SimulationEngineV2.get_instance()

    print("\n=== 测试方案创建 ===")

    async def test():
        scenario_id = await engine.create_scenario("测试方案", {
            "friendly_strength": 80,
            "enemy_strength": 60,
            "threat_level": "medium"
        })
        print(f"创建方案: {scenario_id}")

        versions = engine.get_scenario_versions(scenario_id)
        print(f"版本数: {len(versions)}")
        version_id = versions[0]["version_id"]

        print("\n=== 测试 What-If 分析 ===")
        what_if_result = await engine.what_if_analysis(
            scenario_id, version_id,
            {"friendly_strength": 100, "enemy_strength": 40},
            "增强红方实力",
            max_steps=10
        )

        print(f"基线结果成功: {what_if_result.baseline_result.success}")
        print(f"What-If 结果成功: {what_if_result.what_if_result.success}")

        print("\n=== 参数对比 ===")
        for metric, data in what_if_result.comparison.get("metrics", {}).items():
            print(f"  {metric}: {data['baseline']:.2f} -> {data['what_if']:.2f} ({data['percent_change']:+.1f}%)")

        print("\n=== 偏差分析 ===")
        for item in what_if_result.deviation_analysis:
            print(f"  {item['metric']}: {item['impact']} (deviation: {item['deviation']:+.2f})")

        print("\n=== 测试事件模板 ===")
        template_manager = engine.get_template_manager()
        templates = template_manager.list_templates()
        print(f"模板数量: {len(templates)}")

        event = engine.create_event_from_template("contact_event", location="A区")
        print(f"创建事件: {event['type']}")

        print("\n=== 测试参数扫描 ===")
        sweep_results = await engine.what_if_parameter_sweep(
            scenario_id, version_id,
            "friendly_strength", [60, 70, 80, 90, 100],
            max_steps=5
        )
        print(f"扫描结果数: {len(sweep_results)}")

        print("\n=== 测试时间缩放 ===")
        engine.set_time_scale(2.0)
        print(f"时间缩放: {engine.get_time_scale()}")

    asyncio.run(test())
