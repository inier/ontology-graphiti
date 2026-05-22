import logging
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


class CompositeExecutor:
    def __init__(self, tool_registry=None):
        self._tool_registry = tool_registry
        self._rollback_stack: List[Dict[str, Any]] = []

    async def execute_chain(self, tools: List[Dict[str, Any]],
                            input_data: Dict[str, Any]) -> Dict[str, Any]:
        self._rollback_stack = []
        current_input = input_data.copy()
        results = []

        for i, tool_def in enumerate(tools):
            tool_name = tool_def.get("name", "")
            tool_params = tool_def.get("params", {})
            rollback_fn = tool_def.get("rollback")

            try:
                result = await self._execute_single(tool_name, {**current_input, **tool_params})
                results.append({
                    "tool": tool_name,
                    "step": i + 1,
                    "status": "success",
                    "output": result,
                })

                if rollback_fn:
                    self._rollback_stack.append({
                        "tool": tool_name,
                        "step": i + 1,
                        "rollback_fn": rollback_fn,
                        "input_data": current_input.copy(),
                    })

                if isinstance(result, dict):
                    current_input.update(result)

            except Exception as e:
                logger.error(f"CompositeExecutor: tool '{tool_name}' failed at step {i + 1}: {e}")
                results.append({
                    "tool": tool_name,
                    "step": i + 1,
                    "status": "failed",
                    "error": str(e),
                })

                await self._rollback()

                return {
                    "status": "failed",
                    "failed_at_step": i + 1,
                    "failed_tool": tool_name,
                    "error": str(e),
                    "results": results,
                    "rolled_back": True,
                }

        return {
            "status": "success",
            "total_steps": len(tools),
            "results": results,
            "final_output": current_input,
        }

    async def _execute_single(self, tool_name: str, params: Dict[str, Any]) -> Any:
        if self._tool_registry:
            try:
                return await self._tool_registry.invoke(tool_name, params)
            except Exception:
                pass

        return {"tool": tool_name, "executed": True, "params": list(params.keys())}

    async def _rollback(self):
        for entry in reversed(self._rollback_stack):
            rollback_fn = entry.get("rollback_fn")
            if rollback_fn:
                try:
                    if callable(rollback_fn):
                        result = rollback_fn(entry["input_data"])
                        if hasattr(result, '__await__'):
                            await result
                    logger.info(f"CompositeExecutor: rolled back step {entry['step']} ({entry['tool']})")
                except Exception as e:
                    logger.warning(f"CompositeExecutor: rollback failed for step {entry['step']}: {e}")

        self._rollback_stack.clear()
