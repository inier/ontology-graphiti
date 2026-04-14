"""
技能包初始化文件
实现技能的自动注册机制

双模式兼容：
- 旧模式：SKILL_CATALOG (dict) — 用于 orchestrator._parse_query() 调用链
- 新模式：SkillRegistry — 用于 BaseSkill 子类注册
两个注册表保持同步。
"""

from odap.tools.base import (
    BaseSkill,
    SkillInput,
    SkillOutput,
    SkillMetadata,
    SkillRegistry,
    LegacySkillAdapter,
    get_registry,
)

# 全局技能目录（旧模式，保持向后兼容）
SKILL_CATALOG = {}


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
    print(f"技能注册成功: {name} - {description}")


# 导入技能模块
# 这会触发各个模块中的 register_skill() 函数调用
from . import intelligence
from . import operations
from . import analysis
from . import recommendation
from . import task_management
# ontology_management 已移至 odap.biz.ontology, 不再从 tools 导入
# from . import ontology_management
from . import policy
from . import computation
from . import planning

# visualization_skill 有循环依赖问题，暂不自动注册
# 后续需要修复 visualization_skill.py 中的导入路径
try:
    from . import visualization
    # 如果需要显式注册可视化技能，可以取消注释下面这行
    # register_skill("visualization", "数据可视化技能", visualization.handler)
except ImportError as e:
    print(f"可视化技能模块暂不可用: {e}")

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
