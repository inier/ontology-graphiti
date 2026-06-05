import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SkillAdapter:

    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._tool_registry = None
        self._available = False
        self._init_registry()

    def _init_registry(self):
        try:
            from openharness.tools.base import ToolRegistry
            self._tool_registry = ToolRegistry()
            self._available = True
            logger.info("SkillAdapter: OpenHarness ToolRegistry available")
        except ImportError:
            logger.debug("SkillAdapter: OpenHarness ToolRegistry not available, using local registry")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def register_skill(self, name: str, description: str, handler: Callable,
                       category: str = "general", **kwargs) -> Dict[str, Any]:
        self._registry[name] = {
            "name": name,
            "description": description,
            "handler": handler,
            "category": category,
            **kwargs,
        }
        if self._available and self._tool_registry:
            try:
                from .tool_adapter import OpenHarnessToolAdapter
                tool = OpenHarnessToolAdapter(
                    name=name, description=description, handler=handler, category=category
                )
                self._tool_registry.register(tool)
            except Exception as e:
                logger.debug("SkillAdapter: failed to register with OpenHarness: %s", e)
        return {"status": "success", "skill": name, "registered": True}

    def discover_skills(self, category: str = None) -> Dict[str, Any]:
        skills = list(self._registry.values())
        if category:
            skills = [s for s in skills if s.get("category") == category]
        return {"status": "success", "skills": skills, "count": len(skills)}

    def get_skill(self, name: str) -> Dict[str, Any]:
        skill = self._registry.get(name)
        if not skill:
            return {"status": "error", "message": f"Skill not found: {name}"}
        return {"status": "success", "skill": skill}

    def unregister_skill(self, name: str) -> Dict[str, Any]:
        if name not in self._registry:
            return {"status": "error", "message": f"Skill not found: {name}"}
        del self._registry[name]
        return {"status": "success", "skill": name, "unregistered": True}

    def list_categories(self) -> Dict[str, Any]:
        categories = set(s.get("category", "general") for s in self._registry.values())
        return {"status": "success", "categories": sorted(categories)}


_skill_adapter: Optional[SkillAdapter] = None


def get_skill_adapter() -> SkillAdapter:
    global _skill_adapter
    if _skill_adapter is None:
        _skill_adapter = SkillAdapter()
    return _skill_adapter
