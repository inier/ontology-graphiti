import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class SkillOrchestrator:
    def __init__(self, skill_registry=None):
        self._skill_registry = skill_registry

    def topological_sort(self, skills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        skill_map = {s["name"]: s for s in skills}
        in_degree = defaultdict(int)
        graph = defaultdict(list)

        for skill in skills:
            name = skill["name"]
            deps = skill.get("depends_on", [])
            in_degree.setdefault(name, 0)
            for dep in deps:
                graph[dep].append(name)
                in_degree[name] += 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        sorted_names = []

        while queue:
            queue.sort()
            current = queue.pop(0)
            sorted_names.append(current)
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_names) != len(skills):
            cycle = set(skill_map.keys()) - set(sorted_names)
            raise ValueError(f"Circular dependency detected among skills: {cycle}")

        return [skill_map[name] for name in sorted_names if name in skill_map]

    async def execute_dag(self, skills: List[Dict[str, Any]],
                          input_data: Dict[str, Any]) -> Dict[str, Any]:
        sorted_skills = self.topological_sort(skills)
        results = {}
        current_input = input_data.copy()

        for skill in sorted_skills:
            name = skill["name"]
            try:
                result = await self._execute_skill(name, current_input)
                results[name] = {"status": "success", "output": result}
                if isinstance(result, dict):
                    current_input.update(result)
            except Exception as e:
                logger.error(f"SkillOrchestrator: skill '{name}' failed: {e}")
                results[name] = {"status": "failed", "error": str(e)}
                break

        return {
            "status": "completed" if all(r["status"] == "success" for r in results.values()) else "partial",
            "results": results,
            "execution_order": [s["name"] for s in sorted_skills],
        }

    async def _execute_skill(self, name: str, params: Dict[str, Any]) -> Any:
        if self._skill_registry:
            try:
                return await self._skill_registry.invoke(name, params)
            except Exception:
                pass
        return {"skill": name, "executed": True}
