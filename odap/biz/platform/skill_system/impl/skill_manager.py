"""Skill管理器实现

与 odap/tools/registry.py 中的 SKILL_CATALOG 双向同步：
- 初始化时从 SKILL_CATALOG 加载已有技能
- Web 注册新技能时同步写入 SKILL_CATALOG
- 激活/停用时同步更新 SKILL_CATALOG
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.skill_manager import ISkillManager
from ..models.skill import Skill, SkillStatus, SkillType, SkillVersion

logger = logging.getLogger("skill_manager")

_CATEGORY_TYPE_MAP = {
    "graph": SkillType.QUERY,
    "analysis": SkillType.QUERY,
    "intelligence": SkillType.QUERY,
    "operations": SkillType.ACTION,
    "action": SkillType.ACTION,
    "transform": SkillType.TRANSFORM,
    "integration": SkillType.INTEGRATION,
    "legacy": SkillType.ACTION,
}


def _infer_skill_type(category: str) -> SkillType:
    return _CATEGORY_TYPE_MAP.get(category, SkillType.ACTION)


class SkillManager(ISkillManager):
    """Skill管理器实现"""

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._name_index: Dict[str, str] = {}
        self._synced = False

    def sync_from_catalog(self) -> int:
        """从 SKILL_CATALOG 同步技能到管理器

        Returns:
            同步的技能数量
        """
        if self._synced:
            return 0

        try:
            from odap.tools import SKILL_CATALOG

            count = 0
            for name, entry in SKILL_CATALOG.items():
                if name in self._name_index:
                    continue

                category = entry.get("category", "general")
                description = entry.get("description", "")

                skill = Skill(
                    name=name,
                    type=_infer_skill_type(category),
                    description=description,
                    category=category,
                    status=SkillStatus.ACTIVE,
                    current_version="1.0.0",
                    config={"source": "catalog", "auto_registered": True},
                )

                self._skills[skill.id] = skill
                self._name_index[name] = skill.id
                count += 1

            self._synced = True
            if count > 0:
                logger.info(f"Synced {count} skills from SKILL_CATALOG")

            return count

        except Exception as e:
            logger.warning(f"Failed to sync from SKILL_CATALOG: {e}")
            return 0

    def register_skill(self, name: str, skill_type: SkillType,
                       description: str = "", category: str = "general",
                       tags: List[str] = None) -> Skill:
        """注册Skill（同时同步到 SKILL_CATALOG）"""
        if name in self._name_index:
            existing_id = self._name_index[name]
            return self._skills[existing_id]

        skill = Skill(
            name=name,
            type=skill_type,
            description=description,
            category=category,
            tags=tags or [],
            status=SkillStatus.DRAFT,
        )

        self._skills[skill.id] = skill
        self._name_index[name] = skill.id

        self._sync_to_catalog(name, description, category)

        return skill

    def _sync_to_catalog(self, name: str, description: str, category: str) -> None:
        """同步单个技能到 SKILL_CATALOG"""
        try:
            from odap.tools.registry import SKILL_CATALOG

            if name not in SKILL_CATALOG:
                SKILL_CATALOG[name] = {
                    "description": description,
                    "handler": lambda **kwargs: {"status": "success", "message": f"Skill {name} placeholder"},
                    "category": category,
                }
                logger.info(f"Synced skill '{name}' to SKILL_CATALOG")
        except Exception as e:
            logger.warning(f"Failed to sync skill '{name}' to SKILL_CATALOG: {e}")

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """获取Skill"""
        return self._skills.get(skill_id)

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """通过名称获取Skill"""
        skill_id = self._name_index.get(name)
        if skill_id:
            return self._skills.get(skill_id)
        return None

    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> Skill:
        """更新Skill"""
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError("Skill not found")

        for key, value in updates.items():
            if hasattr(skill, key):
                setattr(skill, key, value)

        skill.updated_at = datetime.now()
        return skill

    def delete_skill(self, skill_id: str) -> bool:
        """删除Skill"""
        if skill_id in self._skills:
            skill = self._skills[skill_id]
            self._name_index.pop(skill.name, None)
            del self._skills[skill_id]
            return True
        return False

    def list_skills(self, filters: Dict[str, Any] = None,
                    page: int = 1, page_size: int = 10) -> List[Skill]:
        """列出Skills"""
        self._ensure_synced()

        filters = filters or {}
        skills = list(self._skills.values())

        if "type" in filters:
            skills = [s for s in skills if s.type.value == filters["type"]]
        if "status" in filters:
            skills = [s for s in skills if s.status.value == filters["status"]]
        if "category" in filters:
            skills = [s for s in skills if s.category == filters["category"]]
        if "name" in filters:
            skills = [s for s in skills if filters["name"].lower() in s.name.lower()]

        start = (page - 1) * page_size
        end = start + page_size
        return skills[start:end]

    def add_version(self, skill_id: str, version: str, implementation: str,
                    schema: Dict[str, Any] = None, changelog: str = "") -> SkillVersion:
        """添加版本"""
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError("Skill not found")

        skill_version = SkillVersion(
            skill_id=skill_id,
            version=version,
            implementation=implementation,
            data_schema=schema or {},
            changelog=changelog,
        )

        skill.versions.append(skill_version)
        skill.current_version = version
        skill.updated_at = datetime.now()

        return skill_version

    def activate_skill(self, skill_id: str) -> Skill:
        """激活Skill"""
        skill = self.update_skill(skill_id, {"status": SkillStatus.ACTIVE})
        self._sync_status_to_harness(skill.name, True)
        return skill

    def deactivate_skill(self, skill_id: str) -> Skill:
        """停用Skill"""
        skill = self.update_skill(skill_id, {"status": SkillStatus.INACTIVE})
        self._sync_status_to_harness(skill.name, False)
        return skill

    def _sync_status_to_harness(self, name: str, active: bool) -> None:
        """同步技能状态到 DomainHarness"""
        try:
            from odap.infra.openharness.tool_adapter import get_domain_harness

            harness = get_domain_harness()
            if harness and hasattr(harness, '_tool_list'):
                for tool in harness._tool_list:
                    if hasattr(tool, 'name') and tool.name == name:
                        if hasattr(tool, '_active'):
                            tool._active = active
                        break
        except Exception as e:
            logger.warning(f"Failed to sync skill status to harness: {e}")

    def _ensure_synced(self) -> None:
        """确保已从 SKILL_CATALOG 同步"""
        if not self._synced:
            self.sync_from_catalog()

    def get_catalog_info(self) -> Dict[str, Any]:
        """获取 SKILL_CATALOG 信息"""
        self._ensure_synced()
        try:
            from odap.tools import SKILL_CATALOG
            return {
                "catalog_count": len(SKILL_CATALOG),
                "manager_count": len(self._skills),
                "synced": self._synced,
                "catalog_names": list(SKILL_CATALOG.keys()),
            }
        except Exception as e:
            return {"error": str(e), "synced": False}
