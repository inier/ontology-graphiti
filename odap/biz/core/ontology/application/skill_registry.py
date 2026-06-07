"""
AppSkillRegistry — 本体应用 skill 注册表。

独立于全局 odap.tools.get_registry()，提供：
- 按 ontology_id + engine_name 唯一索引
- 查询 / 列出 / 注销
- bind_engine 一站式调用

使用方式：
    from odap.biz.core.ontology.application.skill_registry import get_app_skill_registry

    reg = get_app_skill_registry()
    reg.register(RuntimeSkillAdapter(...))
    reg.bind_engine("runtime", runtime_engine_instance)
    skills = reg.list(workspace_id="ws-001", ontology_id="ont-001")
"""
import logging
from typing import Any, Dict, List, Optional

from odap.tools import get_registry as get_global_skill_registry

from .ontology_app_skill import OntologyAppSkill

logger = logging.getLogger(__name__)


class AppSkillRegistry:
    """本体应用 skill 注册表（与全局 SkillRegistry 双向同步）。"""

    def __init__(self) -> None:
        self._skills: Dict[str, OntologyAppSkill] = {}

    def register(self, skill: OntologyAppSkill) -> None:
        """注册到本地 + 全局 registry。"""
        name = skill.metadata.name
        if name in self._skills:
            logger.warning("App skill '%s' already registered, overwriting", name)
        self._skills[name] = skill
        get_global_skill_registry().register(skill)
        logger.info(
            "Registered app skill '%s' (engine=%s, ws=%s, ont=%s)",
            name, skill._engine_name, skill.workspace_id, skill.ontology_id,
        )

    def bind_engine(self, skill_name: str, engine: Any) -> bool:
        """为已注册的 skill 绑定原生引擎。"""
        skill = self._skills.get(skill_name)
        if not skill:
            logger.warning("Cannot bind engine: skill '%s' not registered", skill_name)
            return False
        try:
            skill.bind_engine(engine)
            return True
        except Exception as e:
            logger.warning("Engine bind failed for skill '%s': %s", skill_name, e)
            return False

    def get(self, name: str) -> Optional[OntologyAppSkill]:
        return self._skills.get(name)

    def list(
        self,
        workspace_id: Optional[str] = None,
        ontology_id: Optional[str] = None,
    ) -> List[OntologyAppSkill]:
        items = list(self._skills.values())
        if workspace_id:
            items = [s for s in items if s.workspace_id == workspace_id]
        if ontology_id:
            items = [s for s in items if s.ontology_id == ontology_id]
        return items

    def names(self) -> List[str]:
        return list(self._skills.keys())


_app_skill_registry_instance: Optional[AppSkillRegistry] = None


def get_app_skill_registry() -> AppSkillRegistry:
    """获取全局本体应用 skill 注册表单例。"""
    global _app_skill_registry_instance
    if _app_skill_registry_instance is None:
        _app_skill_registry_instance = AppSkillRegistry()
    return _app_skill_registry_instance


__all__ = ["AppSkillRegistry", "get_app_skill_registry"]
