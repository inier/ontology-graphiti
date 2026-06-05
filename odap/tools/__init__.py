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

__all__ = [
    'BaseSkill',
    'SkillInput',
    'SkillOutput',
    'SkillRegistry',
    'register_skill',
    'SKILL_CATALOG',
    'get_registry',
]
