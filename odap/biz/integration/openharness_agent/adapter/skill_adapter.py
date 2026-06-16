"""DEPRECATED: This adapter delegates to odap.infra.openharness.*.
Use infra-layer imports directly in new code.

Biz 层 SkillAdapter — 委托给 infra 层 SkillAdapter

保留 skill_id 键控的本地注册表（biz 层需求），
OH 注册委托给 infra.openharness.skill_adapter.SkillAdapter。
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("skill_adapter")


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
        self._infra_adapter = None
        self._initialized = True
        self._init_infra_adapter()

    def _init_infra_adapter(self):
        """尝试获取 infra 层 SkillAdapter"""
        try:
            from odap.infra.openharness.skill_adapter import get_skill_adapter
            self._infra_adapter = get_skill_adapter()
        except Exception as e:
            logger.debug("infra SkillAdapter not available: %s", e)
            self._infra_adapter = None

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

        registered_in_oh = False
        if self._infra_adapter and handler:
            try:
                result = self._infra_adapter.register_skill(
                    name=name,
                    description=description,
                    handler=handler,
                    category=category,
                )
                registered_in_oh = result.get("registered", False)
            except Exception as e:
                logger.warning("Register skill in infra SkillAdapter failed: %s", e)

        return {"status": "success", "skill_id": skill_id, "registered_in_openharness": registered_in_oh}

    def unregister_skill(self, skill_id: str) -> Dict[str, Any]:
        if skill_id not in self._skills:
            return {"status": "error", "message": f"Skill {skill_id} not found"}

        skill = self._skills.pop(skill_id)

        # 同步到 infra 层
        if self._infra_adapter:
            try:
                self._infra_adapter.unregister_skill(skill.get("name", skill_id))
            except Exception as e:
                logger.debug("Unregister from infra SkillAdapter failed: %s", e)

        return {"status": "success", "skill_id": skill_id}

    def discover_skills(self, query: Optional[str] = None) -> Dict[str, Any]:
        results = []
        for skill_id, skill in self._skills.items():
            entry = {
                "skill_id": skill_id,
                "name": skill.get("name"),
                "description": skill.get("description"),
                "category": skill.get("category"),
                "status": skill.get("status"),
            }
            if query:
                if (
                    query.lower() in skill.get("name", "").lower()
                    or query.lower() in skill.get("description", "").lower()
                    or query.lower() in skill.get("category", "").lower()
                ):
                    results.append(entry)
            else:
                results.append(entry)

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
