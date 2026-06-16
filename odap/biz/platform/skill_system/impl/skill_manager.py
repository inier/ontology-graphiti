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

    LIFECYCLE_TRANSITIONS = {
        SkillStatus.DRAFT: [SkillStatus.ACTIVE, SkillStatus.ARCHIVED],
        SkillStatus.ACTIVE: [SkillStatus.INACTIVE, SkillStatus.DEPRECATED],
        SkillStatus.INACTIVE: [SkillStatus.ACTIVE, SkillStatus.DEPRECATED, SkillStatus.ARCHIVED],
        SkillStatus.DEPRECATED: [SkillStatus.ARCHIVED],
        SkillStatus.ARCHIVED: [],
    }

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._name_index: Dict[str, str] = {}
        self._synced = False
        self._skill_adapter = None
        self._storage = None
        try:
            from ..storage import SQLiteSkillStorage
            self._storage = SQLiteSkillStorage()
            self._load_from_storage()
        except Exception as e:
            logger.warning(f"SQLite存储初始化失败，使用内存存储: {e}")

    def _load_from_storage(self) -> int:
        if not self._storage:
            return 0
        try:
            rows = self._storage.list_skills()
            count = 0
            for row in rows:
                name = row.get("name", "")
                if name in self._name_index:
                    continue
                skill = Skill(
                    name=name,
                    type=_infer_skill_type(row.get("category", "general")),
                    description=row.get("description", ""),
                    category=row.get("category", "general"),
                    status=SkillStatus(row.get("status", "active")),
                    current_version=str(row.get("version", 1)),
                    config={"source": "storage", "skill_id": row.get("skill_id", "")},
                )
                self._skills[skill.id] = skill
                self._name_index[name] = skill.id
                count += 1
            if count > 0:
                logger.info(f"Loaded {count} skills from SQLite storage")
            return count
        except Exception as e:
            logger.warning(f"从SQLite加载技能失败: {e}")
            return 0

    def _persist_skill(self, skill: Skill) -> None:
        if not self._storage:
            return
        try:
            self._storage.save_skill({
                "skill_id": skill.id,
                "name": skill.name,
                "category": skill.category,
                "skill_type": skill.type.value,
                "status": skill.status.value,
                "description": skill.description,
                "enabled": skill.status == SkillStatus.ACTIVE,
                "created_at": skill.created_at.isoformat() if hasattr(skill.created_at, 'isoformat') else str(skill.created_at),
            })
        except Exception as e:
            logger.warning(f"持久化技能失败: {e}")

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
        self._persist_skill(skill)

        return skill

    def _sync_to_catalog(self, name: str, description: str, category: str) -> None:
        """同步单个技能到 SKILL_CATALOG"""
        try:
            from odap.tools.registry import SKILL_CATALOG

            if name not in SKILL_CATALOG:
                SKILL_CATALOG[name] = {
                    "description": description,
                    "handler": lambda **kwargs: {"status": "placeholder", "message": f"Skill {name} has no implementation yet"},
                    "category": category,
                    "placeholder": True,
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
        self._persist_skill(skill)
        return skill

    def delete_skill(self, skill_id: str) -> bool:
        """删除Skill"""
        if skill_id in self._skills:
            skill = self._skills[skill_id]
            self._name_index.pop(skill.name, None)
            del self._skills[skill_id]
            if self._storage:
                try:
                    self._storage.delete_skill(skill.name)
                except Exception as e:
                    logger.warning(f"从存储删除技能失败: {e}")
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

    def transition_lifecycle(self, skill_id: str, target_status: SkillStatus) -> Skill:
        skill = self._skills.get(skill_id)
        if not skill:
            raise ValueError("Skill not found")

        allowed = self.LIFECYCLE_TRANSITIONS.get(skill.status, [])
        if target_status not in allowed:
            raise ValueError(f"Cannot transition from {skill.status.value} to {target_status.value}")

        skill.status = target_status
        skill.updated_at = datetime.now()

        if target_status == SkillStatus.ACTIVE:
            self._sync_status_to_harness(skill.name, True)
            self._register_to_adapter(skill)
        elif target_status in (SkillStatus.INACTIVE, SkillStatus.DEPRECATED, SkillStatus.ARCHIVED):
            self._sync_status_to_harness(skill.name, False)
            if target_status == SkillStatus.ARCHIVED:
                self._unregister_from_adapter(skill_id)

        return skill

    def _get_skill_adapter(self):
        if self._skill_adapter is not None:
            return self._skill_adapter
        try:
            from odap.biz.integration.openharness_agent.adapter.skill_adapter import SkillAdapter
            self._skill_adapter = SkillAdapter()
        except Exception as e:
            logger.warning(f"SkillAdapter not available: {e}")
            self._skill_adapter = None
        return self._skill_adapter

    def _register_to_adapter(self, skill: Skill) -> None:
        adapter = self._get_skill_adapter()
        if not adapter:
            return
        try:
            adapter.register_skill({
                "skill_id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "category": skill.category,
            })
        except Exception as e:
            logger.warning(f"Failed to register skill to adapter: {e}")

    def _unregister_from_adapter(self, skill_id: str) -> None:
        adapter = self._get_skill_adapter()
        if not adapter:
            return
        try:
            adapter.unregister_skill(skill_id)
        except Exception as e:
            logger.warning(f"Failed to unregister skill from adapter: {e}")

    def call_skill(self, skill_name: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """调用技能，检查 placeholder 并记录警告

        Args:
            skill_name: 技能名称
            parameters: 调用参数

        Returns:
            技能执行结果
        """
        try:
            from odap.tools import SKILL_CATALOG
        except Exception as e:
            return {"status": "error", "message": f"SKILL_CATALOG not available: {e}"}

        entry = SKILL_CATALOG.get(skill_name)
        if not entry:
            return {"status": "error", "message": f"Skill '{skill_name}' not found in catalog"}

        if entry.get("placeholder"):
            logger.warning(f"Calling placeholder skill '{skill_name}' — no real implementation available")

        handler = entry.get("handler")
        if not handler or not callable(handler):
            return {"status": "error", "message": f"Skill '{skill_name}' has no callable handler"}

        try:
            result = handler(**(parameters or {}))
            if isinstance(result, dict) and entry.get("placeholder"):
                result["implementation_status"] = "placeholder"
            return result if isinstance(result, dict) else {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Skill '{skill_name}' execution failed: {e}")
            return {"status": "error", "message": str(e)}

    def discover_skills(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure_synced()
        results = []
        for skill in self._skills.values():
            if query:
                if query.lower() in skill.name.lower() or query.lower() in skill.description.lower() or query.lower() in skill.category.lower():
                    results.append({
                        "skill_id": skill.id,
                        "name": skill.name,
                        "description": skill.description,
                        "category": skill.category,
                        "status": skill.status.value,
                    })
            else:
                results.append({
                    "skill_id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "category": skill.category,
                    "status": skill.status.value,
                })
        return results
