"""
技能包初始化文件
实现技能的自动注册机制

双模式兼容：
- 旧模式：SKILL_CATALOG (dict) — 用于 orchestrator._parse_query() 调用链
- 新模式：SkillRegistry — 用于 BaseSkill 子类注册
两个注册表保持同步。
"""
import logging

# 先定义全局技能目录（旧模式，保持向后兼容）
SKILL_CATALOG = {}

# 延迟导入，避免循环导入
from odap.tools.base import (
    BaseSkill,
    SkillInput,
    SkillOutput,
    SkillMetadata,
    SkillRegistry,
    LegacySkillAdapter,
    get_registry,
)

logger = logging.getLogger(__name__)


def register_skill(name, description, handler, category="legacy"):
    """
    注册技能（旧接口，保持向后兼容）

    同时写入 SKILL_CATALOG 和 SkillRegistry。
    """
    SKILL_CATALOG[name] = {
        "description": description,
        "handler": handler,
        "category": category,
    }
    get_registry().register_legacy(name, description, handler, category=category)
    logger.info(f'技能注册成功: {name} - {description}')


# 暴露新 API
__all__ = [
    "SKILL_CATALOG",
    "register_skill",
    "BaseSkill",
    "SkillInput",
    "SkillOutput",
    "SkillMetadata",
    "SkillRegistry",
    "LegacySkillAdapter",
    "get_registry",
]
