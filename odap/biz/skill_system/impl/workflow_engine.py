import asyncio
import logging
from typing import Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class StepType(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


class WorkflowStep(BaseModel := type('BaseModel', (), {})):
    pass


class WorkflowEngine:
    def __init__(self, skill_registry=None):
        self._skill_registry = skill_registry

    async def execute(self, workflow_def: Dict[str, Any],
                      input_data: Dict[str, Any]) -> Dict[str, Any]:
        steps = workflow_def.get("steps", [])
        if not steps:
            return {"status": "no_steps", "results": {}}

        current_input = input_data.copy()
        results = {}

        for step in steps:
            step_type = step.get("type", "sequential")
            step_name = step.get("name", "unnamed")

            try:
                if step_type == "sequential":
                    result = await self._execute_sequential(step, current_input)
                elif step_type == "parallel":
                    result = await self._execute_parallel(step, current_input)
                elif step_type == "conditional":
                    result = await self._execute_conditional(step, current_input)
                else:
                    result = {"error": f"Unknown step type: {step_type}"}

                results[step_name] = result
                if isinstance(result, dict) and "output" in result:
                    current_input.update(result["output"])

            except Exception as e:
                logger.error(f"WorkflowEngine: step '{step_name}' failed: {e}")
                results[step_name] = {"status": "failed", "error": str(e)}
                break

        return {
            "status": "completed" if all(
                isinstance(r, dict) and r.get("status") != "failed"
                for r in results.values()
            ) else "partial",
            "results": results,
        }

    async def _execute_sequential(self, step: Dict[str, Any],
                                   input_data: Dict[str, Any]) -> Dict[str, Any]:
        actions = step.get("actions", [])
        current = input_data.copy()

        for action in actions:
            result = await self._execute_action(action, current)
            if isinstance(result, dict):
                current.update(result)

        return {"status": "success", "output": current}

    async def _execute_parallel(self, step: Dict[str, Any],
                                 input_data: Dict[str, Any]) -> Dict[str, Any]:
        actions = step.get("actions", [])
        tasks = [self._execute_action(action, input_data) for action in actions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged = {}
        for r in results:
            if isinstance(r, dict):
                merged.update(r)
            elif isinstance(r, Exception):
                logger.warning(f"WorkflowEngine: parallel action failed: {r}")

        return {"status": "success", "output": merged}

    async def _execute_conditional(self, step: Dict[str, Any],
                                    input_data: Dict[str, Any]) -> Dict[str, Any]:
        condition = step.get("condition", "")
        then_actions = step.get("then", [])
        else_actions = step.get("else", [])

        condition_met = self._evaluate_condition(condition, input_data)
        actions = then_actions if condition_met else else_actions

        current = input_data.copy()
        for action in actions:
            result = await self._execute_action(action, current)
            if isinstance(result, dict):
                current.update(result)

        return {"status": "success", "output": current, "condition_met": condition_met}

    def _evaluate_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        if not condition:
            return False

        for key, value in data.items():
            condition = condition.replace(f"{{{key}}}", str(value))

        try:
            return bool(eval(condition))
        except Exception:
            return "true" in condition.lower()

    async def _execute_action(self, action: Dict[str, Any],
                               input_data: Dict[str, Any]) -> Any:
        action_type = action.get("type", "skill")
        name = action.get("name", "")
        params = {**input_data, **action.get("params", {})}

        if action_type == "skill" and self._skill_registry:
            try:
                return await self._skill_registry.invoke(name, params)
            except Exception:
                pass

        return {"action": name, "executed": True, "type": action_type}
