"""ODAP Tools Package - Domain Tools Layer"""
import logging

from .base import BaseSkill, SkillInput, SkillOutput
from .registry import (
    SKILL_CATALOG,
    register_skill,
    SkillRegistry,
    get_registry
)

logger = logging.getLogger(__name__)

# 导入 Agent 工具集（自动注册到 SKILL_CATALOG）
try:
    from .agent_tools import (
        query_entities,
        query_relations,
        analyze_graph,
        search_graph,
        get_entity_details,
        list_workspaces,
        get_workspace_info,
        create_workspace_summary,
    )
    logger.info('[OK] Agent tools loaded')
except Exception as e:
    logger.info(f'[WARN] Agent tools load failed: {e}')

# 导入 Web 数据采集技能集（自动注册到 SKILL_CATALOG）
try:
    from . import web  # noqa: F401
    logger.info('[OK] Web tools loaded')
except Exception as e:
    logger.info(f'[WARN] Web tools load failed: {e}')

# 导入 NL 查询技能集（自动注册到 SKILL_CATALOG）
try:
    from .query.nl_query_skills import register_nl_query_skills
    register_nl_query_skills()
    logger.info('[OK] NL query skills loaded')
except Exception as e:
    logger.info(f'[WARN] NL query skills load failed: {e}')

# 导入情报技能集（自动注册到 SKILL_CATALOG）
try:
    from . import intelligence  # noqa: F401
    logger.info('[OK] Intelligence skills loaded')
except Exception as e:
    logger.info(f'[WARN] Intelligence skills load failed: {e}')

# 导入执行技能集（自动注册到 SKILL_CATALOG）
try:
    from . import operations  # noqa: F401
    logger.info('[OK] Operations skills loaded')
except Exception as e:
    logger.info(f'[WARN] Operations skills load failed: {e}')

# 导入分析技能集（自动注册到 SKILL_CATALOG）
try:
    from . import analysis  # noqa: F401
    logger.info('[OK] Analysis skills loaded')
except Exception as e:
    logger.info(f'[WARN] Analysis skills load failed: {e}')

# 导入计算推理技能集（自动注册到 SKILL_CATALOG）
try:
    from . import computation  # noqa: F401
    logger.info('[OK] Computation skills loaded')
except Exception as e:
    logger.info(f'[WARN] Computation skills load failed: {e}')

# 导入推荐技能集（自动注册到 SKILL_CATALOG）
try:
    from . import recommendation  # noqa: F401
    logger.info('[OK] Recommendation skills loaded')
except Exception as e:
    logger.info(f'[WARN] Recommendation skills load failed: {e}')

# 导入规划编排技能集（自动注册到 SKILL_CATALOG）
try:
    from . import planning  # noqa: F401
    logger.info('[OK] Planning skills loaded')
except Exception as e:
    logger.info(f'[WARN] Planning skills load failed: {e}')

# 导入策略技能集（自动注册到 SKILL_CATALOG）
try:
    from . import policy  # noqa: F401
    logger.info('[OK] Policy skills loaded')
except Exception as e:
    logger.info(f'[WARN] Policy skills load failed: {e}')

# 导入可视化技能集（自动注册到 SKILL_CATALOG）
try:
    from . import visualization  # noqa: F401
    logger.info('[OK] Visualization skills loaded')
except Exception as e:
    logger.info(f'[WARN] Visualization skills load failed: {e}')

# 导入任务管理技能集（自动注册到 SKILL_CATALOG）
try:
    from . import task_management  # noqa: F401
    logger.info('[OK] Task management skills loaded')
except Exception as e:
    logger.info(f'[WARN] Task management skills load failed: {e}')

__all__ = [
    'BaseSkill',
    'SkillInput',
    'SkillOutput',
    'SkillRegistry',
    'register_skill',
    'SKILL_CATALOG',
    'get_registry',
]
