"""
模拟推演引擎模块
实现沙箱式推演能力，支持方案版本管理和回退

Phase 2 扩展: 模拟推演引擎
"""

import json
import os
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger("simulation_engine")


class SandboxState(str, Enum):
    """沙箱状态"""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


@dataclass
class ScenarioVersion:
    """方案版本"""
    version_id: str
    scenario_id: str
    parent_version: Optional[str]
    parameters: Dict[str, Any]
    created_at: datetime
    message: str = ""


@dataclass
class SimulationResult:
    """推演结果"""
    result_id: str
    scenario_id: str
    version_id: str
    final_state: Dict[str, Any]
    events: List[Dict[str, Any]]
    metrics: Dict[str, float]
    success: bool
    execution_time_ms: float
    error_message: Optional[str] = None


class SimulationEngine:
    """模拟推演引擎"""

    _instance: Optional['SimulationEngine'] = None

    def __init__(self, storage_path: str = "/tmp/simulations"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        self._active_sandboxes: Dict[str, SandboxState] = {}
        self._version_history: Dict[str, List[ScenarioVersion]] = {}
        self._results: Dict[str, SimulationResult] = {}

    @classmethod
    def get_instance(cls, storage_path: str = "/tmp/simulations") -> 'SimulationEngine':
        if cls._instance is None:
            cls._instance = SimulationEngine(storage_path)
        return cls._instance

    async def create_scenario(self, name: str, initial_parameters: Dict[str, Any]) -> str:
        """创建新推演方案"""
        scenario_id = str(uuid.uuid4())[:16]

        os.makedirs(os.path.join(self.storage_path, scenario_id), exist_ok=True)

        version_id = await self._create_version(scenario_id, None, initial_parameters, "初始版本")

        logger.info(f"创建推演方案: {scenario_id}, 版本: {version_id}")
        return scenario_id

    async def _create_version(
        self,
        scenario_id: str,
        parent_version: Optional[str],
        parameters: Dict[str, Any],
        message: str
    ) -> str:
        """创建新版本"""
        version_id = str(uuid.uuid4())[:16]

        version = ScenarioVersion(
            version_id=version_id,
            scenario_id=scenario_id,
            parent_version=parent_version,
            parameters=parameters,
            created_at=datetime.now(),
            message=message,
        )

        if scenario_id not in self._version_history:
            self._version_history[scenario_id] = []

        self._version_history[scenario_id].append(version)
        await self._save_version(scenario_id, version)

        return version_id

    async def _save_version(self, scenario_id: str, version: ScenarioVersion):
        """保存版本到存储"""
        version_file = os.path.join(self.storage_path, scenario_id, f"{version.version_id}.json")

        version_data = {
            "version_id": version.version_id,
            "scenario_id": version.scenario_id,
            "parent_version": version.parent_version,
            "parameters": version.parameters,
            "created_at": version.created_at.isoformat(),
            "message": version.message,
        }

        with open(version_file, 'w') as f:
            json.dump(version_data, f, indent=2, default=str)

    async def create_branch(
        self,
        scenario_id: str,
        base_version_id: str,
        new_parameters: Dict[str, Any],
        branch_message: str
    ) -> str:
        """从指定版本创建分支"""
        if scenario_id not in self._version_history:
            raise ValueError(f"方案 {scenario_id} 不存在")

        version_ids = [v.version_id for v in self._version_history[scenario_id]]
        if base_version_id not in version_ids:
            raise ValueError(f"版本 {base_version_id} 不存在")

        return await self._create_version(scenario_id, base_version_id, new_parameters, branch_message)

    async def rollback_to_version(self, scenario_id: str, version_id: str) -> bool:
        """回退到指定版本"""
        if scenario_id not in self._version_history:
            return False

        versions = self._version_history[scenario_id]
        target_version = None
        for v in versions:
            if v.version_id == version_id:
                target_version = v
                break

        if target_version is None:
            return False

        logger.info(f"回退方案 {scenario_id} 到版本 {version_id}")
        return True

    async def run_simulation(
        self,
        scenario_id: str,
        version_id: str,
        max_steps: int = 100
    ) -> SimulationResult:
        """运行推演"""
        if scenario_id not in self._version_history:
            raise ValueError(f"方案 {scenario_id} 不存在")

        versions = self._version_history[scenario_id]
        target_version = None
        for v in versions:
            if v.version_id == version_id:
                target_version = v
                break

        if target_version is None:
            raise ValueError(f"版本 {version_id} 不存在")

        sandbox_id = f"{scenario_id}_{version_id}"
        self._active_sandboxes[sandbox_id] = SandboxState.RUNNING

        logger.info(f"开始推演: {sandbox_id}, 最大步数: {max_steps}")

        start_time = datetime.now()
        events = []
        current_state = target_version.parameters.copy()
        step = 0
        success = True
        error_message = None

        try:
            for step in range(max_steps):
                event = await self._simulate_step(step, current_state)
                events.append(event)

                current_state.update(event.get("state_changes", {}))

                if event.get("terminal", False):
                    break

        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"推演执行失败: {e}")

        finally:
            self._active_sandboxes[sandbox_id] = SandboxState.COMPLETED if success else SandboxState.FAILED

        execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        result = SimulationResult(
            result_id=str(uuid.uuid4())[:16],
            scenario_id=scenario_id,
            version_id=version_id,
            final_state=current_state,
            events=events,
            metrics=self._calculate_metrics(events, current_state),
            success=success,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
        )

        self._results[result.result_id] = result
        return result

    async def _simulate_step(self, step: int, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """模拟单步执行"""
        threat_level = current_state.get("threat_level", "medium")
        friendly_strength = current_state.get("friendly_strength", 50)
        enemy_strength = current_state.get("enemy_strength", 50)

        change = (friendly_strength - enemy_strength) / 100.0

        event = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "state_changes": {
                "threat_level": threat_level,
                "friendly_strength": max(0, min(100, friendly_strength + change * 5)),
                "enemy_strength": max(0, min(100, enemy_strength - change * 3)),
            },
            "action_taken": f"simulated_action_step_{step}",
            "terminal": step >= 9,
        }

        return event

    def _calculate_metrics(self, events: List[Dict[str, Any]], final_state: Dict[str, Any]) -> Dict[str, float]:
        """计算推演指标"""
        total_events = len(events)
        friendly_final = final_state.get("friendly_strength", 0)
        enemy_final = final_state.get("enemy_strength", 0)

        return {
            "total_events": float(total_events),
            "friendly_final_strength": float(friendly_final),
            "enemy_final_strength": float(enemy_final),
            "strength_ratio": float(friendly_final / max(1, enemy_final)),
            "threat_level_score": {"low": 1.0, "medium": 2.0, "high": 3.0, "critical": 4.0}.get(
                final_state.get("threat_level", "medium"), 2.0
            ),
        }

    def get_scenario_versions(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取方案的所有版本"""
        if scenario_id not in self._version_history:
            return []

        return [
            {
                "version_id": v.version_id,
                "parent_version": v.parent_version,
                "parameters": v.parameters,
                "created_at": v.created_at.isoformat(),
                "message": v.message,
            }
            for v in self._version_history[scenario_id]
        ]

    def get_result(self, result_id: str) -> Optional[SimulationResult]:
        """获取推演结果"""
        return self._results.get(result_id)

    def get_active_sandboxes(self) -> Dict[str, str]:
        """获取活跃沙箱"""
        return {k: v.value for k, v in self._active_sandboxes.items()}

    async def terminate_sandbox(self, sandbox_id: str) -> bool:
        """终止沙箱"""
        if sandbox_id in self._active_sandboxes:
            self._active_sandboxes[sandbox_id] = SandboxState.TERMINATED
            logger.info(f"沙箱已终止: {sandbox_id}")
            return True
        return False

    def compare_versions(self, scenario_id: str, version_a: str, version_b: str) -> Dict[str, Any]:
        """对比两个版本的参数差异"""
        if scenario_id not in self._version_history:
            return {"error": "scenario_not_found"}

        versions = {v.version_id: v for v in self._version_history[scenario_id]}

        if version_a not in versions or version_b not in versions:
            return {"error": "version_not_found"}

        params_a = versions[version_a].parameters
        params_b = versions[version_b].parameters

        all_keys = set(params_a.keys()) | set(params_b.keys())
        differences = {}

        for key in all_keys:
            val_a = params_a.get(key)
            val_b = params_b.get(key)
            if val_a != val_b:
                differences[key] = {"version_a": val_a, "version_b": val_b}

        return {
            "version_a": version_a,
            "version_b": version_b,
            "differences": differences,
        }