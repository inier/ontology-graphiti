import logging
from typing import Any, Dict, List, Optional

from odap.infra.query.protocols import QuerySource

logger = logging.getLogger(__name__)


class QuerySchemaTool:
    name = "query_schema"
    description = "Query ontology type definitions (object types, link definitions, action types)"
    source = QuerySource.SCHEMA

    def execute(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        from odap.infra.query.service import QueryService
        qs = QueryService()
        result = qs.execute(
            workspace_id=params.get("workspace_id", "default"),
            query=".schema",
            limit=params.get("limit", 20),
        )
        return result.rows


class QueryEntityTool:
    name = "query_entity"
    description = "Query runtime entities by filters or search"
    source = QuerySource.ENTITY

    def execute(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        from odap.infra.query.service import QueryService
        qs = QueryService()
        search = params.get("search", "")
        query = f".entity with(search='{search}')" if search else ".entity"
        result = qs.execute(
            workspace_id=params.get("workspace_id", "default"),
            query=query,
            limit=params.get("limit", 20),
        )
        return result.rows


class QueryTopoTool:
    name = "query_topo"
    description = "Query topology relations and graph traversal"
    source = QuerySource.TOPO

    def execute(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        from odap.infra.query.service import QueryService
        qs = QueryService()
        entity_id = params.get("entity_id", "")
        direction = params.get("direction", "both")
        depth = params.get("depth", 1)
        query = f".topo neighbors(id='{entity_id}', direction='{direction}', depth={depth})"
        result = qs.execute(
            workspace_id=params.get("workspace_id", "default"),
            query=query,
            limit=params.get("limit", 20),
        )
        return result.rows


class QueryTemporalTool:
    name = "query_temporal"
    description = "Query temporal data using Graphiti bitemporal features"
    source = QuerySource.TEMPORAL

    def execute(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        from odap.infra.query.service import QueryService
        qs = QueryService()
        entity_id = params.get("entity_id", "")
        valid_time = params.get("valid_time", "")
        if entity_id:
            query = f".temporal history(id='{entity_id}')"
        elif valid_time:
            query = f".temporal at(valid_time='{valid_time}')"
        else:
            query = ".temporal"
        result = qs.execute(
            workspace_id=params.get("workspace_id", "default"),
            query=query,
            limit=params.get("limit", 20),
        )
        return result.rows


QUERY_TOOLS = [QuerySchemaTool, QueryEntityTool, QueryTopoTool, QueryTemporalTool]


def register_query_tools(registry=None) -> int:
    count = 0
    for tool_cls in QUERY_TOOLS:
        tool = tool_cls()
        if registry is not None:
            try:
                registry.register_function(
                    name=tool.name,
                    description=tool.description,
                    func=tool.execute,
                    category="query",
                )
                count += 1
            except Exception as e:
                logger.debug("register_query_tools %s fallback: %s", tool.name, e)
        else:
            try:
                from odap.biz.platform.tool_registry import get_tool_registry
                reg = get_tool_registry()
                reg.register_function(
                    name=tool.name,
                    description=tool.description,
                    func=tool.execute,
                    category="query",
                )
                count += 1
            except Exception as e:
                logger.debug("register_query_tools %s fallback: %s", tool.name, e)
    return count
