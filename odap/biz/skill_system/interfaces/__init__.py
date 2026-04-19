"""Skill系统接口"""

from .skill_manager import ISkillManager
from .hotplug import IHotplugManager
from .registry import ISkillRegistry

__all__ = [
    "ISkillManager",
    "IHotplugManager",
    "ISkillRegistry"
]
