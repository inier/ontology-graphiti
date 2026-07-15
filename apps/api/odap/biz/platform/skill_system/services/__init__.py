"""Skill服务"""

from .skill_service import SkillService
from .hotplug_service import HotplugService

_skill_service_instance = None
_hotplug_service_instance = None


def get_skill_service() -> SkillService:
    global _skill_service_instance
    if _skill_service_instance is None:
        _skill_service_instance = SkillService()
    return _skill_service_instance


def get_hotplug_service() -> HotplugService:
    global _hotplug_service_instance
    if _hotplug_service_instance is None:
        _hotplug_service_instance = HotplugService()
    return _hotplug_service_instance


__all__ = [
    "SkillService",
    "HotplugService",
    "get_skill_service",
    "get_hotplug_service",
]
