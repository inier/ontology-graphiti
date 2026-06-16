"""
Agent 工具集 - 为 OpenHarness Agent 提供的知识图谱操作工具

包含：
- 实体查询工具
- 关系查询工具
- 图谱分析工具
- 工作空间管理工具
- 三国演义领域技能
"""

from .graph_tools import (
    query_entities,
    query_relations,
    analyze_graph,
    search_graph,
    get_entity_details,
)
from .workspace_tools import (
    list_workspaces,
    get_workspace_info,
    create_workspace_summary,
)

# P4-fix: 注册三国领域技能
try:
    from . import sanguo_skills  # noqa: F401
except Exception as _e:
    import logging
    logging.getLogger(__name__).warning(f"三国技能包加载失败: {_e}")

__all__ = [
    'query_entities',
    'query_relations',
    'analyze_graph',
    'search_graph',
    'get_entity_details',
    'list_workspaces',
    'get_workspace_info',
    'create_workspace_summary',
]
