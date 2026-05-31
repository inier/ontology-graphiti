import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("skill_adapter")

try:
    from odap.infra.openharness.tool_adapter import OPENHARNESS_AVAILABLE, DomainHarness
    _OH_AVAILABLE = OPENHARNESS_AVAILABLE
except ImportError:
    _OH_AVAILABLE = False


class SkillAdapter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._skills: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

    def register_skill(self, skill_def: Dict[str, Any]) -> Dict[str, Any]:
        skill_id = skill_def.get("skill_id", str(uuid.uuid4()))
        name = skill_def.get("name", "unnamed")
        description = skill_def.get("description", "")
        handler = skill_def.get("handler")
        category = skill_def.get("category", "general")

        self._skills[skill_id] = {
            "skill_id": skill_id,
            "name": name,
            "description": description,
            "handler": handler,
            "category": category,
            "status": "active",
        }

        if _OH_AVAILABLE and handler:
            try:
                from odap.infra.openharness.tool_adapter import OpenHarnessToolAdapter

                adapter = OpenHarnessToolAdapter(
                    name=name,
                    description=description,
                    handler=handler,
                    category=category,
                )
                self._skills[skill_id]["oh_adapter"] = adapter
                return {
                    "status": "success",
                    "skill_id": skill_id,
                    "registered_in_openharness": True,
                }
            except Exception as e:
                logger.warning("Register skill in OpenHarness failed: %s", e)

        return {"status": "success", "skill_id": skill_id, "registered_in_openharness": False}

    def unregister_skill(self, skill_id: str) -> Dict[str, Any]:
        if skill_id not in self._skills:
            return {"status": "error", "message": f"Skill {skill_id} not found"}

        del self._skills[skill_id]
        return {"status": "success", "skill_id": skill_id}

    def discover_skills(self, query: Optional[str] = None) -> Dict[str, Any]:
        results = []
        for skill_id, skill in self._skills.items():
            if query:
                if (
                    query.lower() in skill.get("name", "").lower()
                    or query.lower() in skill.get("description", "").lower()
                    or query.lower() in skill.get("category", "").lower()
                ):
                    results.append(
                        {
                            "skill_id": skill_id,
                            "name": skill.get("name"),
                            "description": skill.get("description"),
                            "category": skill.get("category"),
                            "status": skill.get("status"),
                        }
                    )
            else:
                results.append(
                    {
                        "skill_id": skill_id,
                        "name": skill.get("name"),
                        "description": skill.get("description"),
                        "category": skill.get("category"),
                        "status": skill.get("status"),
                    }
                )

        return {"status": "success", "skills": results, "count": len(results)}

    def get_skill_status(self, skill_id: str) -> Dict[str, Any]:
        skill = self._skills.get(skill_id)
        if not skill:
            return {"status": "error", "message": f"Skill {skill_id} not found"}

        return {
            "status": "success",
            "skill_id": skill_id,
            "name": skill.get("name"),
            "skill_status": skill.get("status"),
            "category": skill.get("category"),
        }
