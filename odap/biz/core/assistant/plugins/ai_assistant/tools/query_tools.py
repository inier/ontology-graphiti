"""Query tools — ontology-aware entity/relation/temporal queries.

Migrated from odap.biz.core.assistant.tools (original _execute_* functions).
Each tool is now an OpenHarness BaseTool subclass with Pydantic input validation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext

logger = logging.getLogger(__name__)


# ── Input Models ────────────────────────────────────────────────────────────────────

class EntityListInput(BaseModel):
    """Arguments for listing entities (object types) in the ontology."""

    workspace_id: str = Field(default="default", description="Workspace ID, defaults to 'default'")
    object_type: str | None = Field(default=None, description="Optional: filter by object type name")
    limit: int = Field(default=20, ge=1, le=200, description="Max number of results to return")


class EntitySearchInput(BaseModel):
    """Arguments for searching entities by keyword."""

    query: str = Field(description="Search keyword to match against entity names")
    workspace_id: str = Field(default="default", description="Workspace ID, defaults to 'default'")
    limit: int = Field(default=10, ge=1, le=200, description="Max number of results to return")


class RelationQueryInput(BaseModel):
    """Arguments for querying relations/edges between entities."""

    source_type: str | None = Field(default=None, description="Optional: filter by source type name")
    target_type: str | None = Field(default=None, description="Optional: filter by target type name")
    workspace_id: str = Field(default="default", description="Workspace ID, defaults to 'default'")
    limit: int = Field(default=20, ge=1, le=200, description="Max number of results to return")


class TemporalQueryInput(BaseModel):
    """Arguments for querying temporal/episodic data in a time range."""

    from_time: str | None = Field(default=None, description="Start time (ISO 8601 format), optional")
    to_time: str | None = Field(default=None, description="End time (ISO 8601 format), optional")
    workspace_id: str = Field(default="default", description="Workspace ID, defaults to 'default'")


# ── Tools ──────────────────────────────────────────────────────────────────────────

class EntityListTool(BaseTool):
    """List entities in the ontology, optionally filtered by type.

    Uses QueryService.execute() with '.entity list()' DSL command.
    Results are ontology-based — queries the knowledge graph via Graphiti/Neo4j.
    """

    name = "list_entities"
    description = (
        "列出知识图谱中的实体（对象类型）。"
        "可按类型筛选。参数: workspace_id(默认default), object_type(可选), limit(默认20,最大200)。"
        "基于本体进行查询——通过 QueryService 执行 '.entity list()' DSL 命令。"
    )
    input_model = EntityListInput

    def is_read_only(self, arguments: EntityListInput) -> bool:
        return True

    async def execute(self, arguments: EntityListInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.infra.query import get_query_service

            qs = get_query_service()
            if arguments.object_type:
                result = qs.execute(
                    arguments.workspace_id,
                    f".entity list({arguments.object_type}) limit({arguments.limit})",
                )
            else:
                result = qs.execute(
                    arguments.workspace_id,
                    f".entity list() limit({arguments.limit})",
                )
            rows = result.rows if hasattr(result, "rows") else []
            output = {
                "status": "success",
                "count": len(rows),
                "rows": rows[: arguments.limit],
            }
            return ToolResult(output=str(output), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("EntityListTool failed: %s", e)
            return ToolResult(output=f"查询失败: {e}", is_error=True)


class EntitySearchTool(BaseTool):
    """Search entities by name or keyword.

    Uses QueryService.execute() with '.entity search()' DSL command.
    """

    name = "search_entities"
    description = (
        "按关键词搜索知识图谱中的实体。"
        "参数: query(必填,搜索关键词), workspace_id(默认default), limit(默认10,最大200)。"
        "基于本体进行查询——通过 QueryService 执行 '.entity search()' DSL 命令。"
    )
    input_model = EntitySearchInput

    def is_read_only(self, arguments: EntitySearchInput) -> bool:
        return True

    async def execute(self, arguments: EntitySearchInput, context: ToolExecutionContext) -> ToolResult:
        if not arguments.query or not arguments.query.strip():
            return ToolResult(output="query 参数不能为空", is_error=True)
        try:
            from odap.infra.query import get_query_service

            qs = get_query_service()
            result = qs.execute(
                arguments.workspace_id,
                f'.entity search("{arguments.query}") limit({arguments.limit})',
            )
            rows = result.rows if hasattr(result, "rows") else []
            output = {
                "status": "success",
                "count": len(rows),
                "rows": rows[: arguments.limit],
            }
            return ToolResult(output=str(output), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("EntitySearchTool failed: %s", e)
            return ToolResult(output=f"搜索失败: {e}", is_error=True)


class RelationQueryTool(BaseTool):
    """Query relations/edges between entities in the ontology.

    Uses QueryService.execute() with '.topo' DSL commands.
    Supports filtering by source type and/or target type.
    """

    name = "query_relations"
    description = (
        "查询实体间的关系/边。"
        "可按源类型或目标类型筛选。"
        "参数: source_type(可选), target_type(可选), workspace_id(默认default), limit(默认20,最大200)。"
        "基于本体进行查询——通过 QueryService 执行 '.topo' DSL 命令。"
    )
    input_model = RelationQueryInput

    def is_read_only(self, arguments: RelationQueryInput) -> bool:
        return True

    async def execute(self, arguments: RelationQueryInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.infra.query import get_query_service

            qs = get_query_service()
            if arguments.source_type and arguments.target_type:
                cmd = f'.topo path(from({arguments.source_type}), to({arguments.target_type})) limit({arguments.limit})'
            elif arguments.source_type:
                cmd = f'.topo neighbors({arguments.source_type}) limit({arguments.limit})'
            else:
                cmd = f'.topo graph() limit({arguments.limit})'
            result = qs.execute(arguments.workspace_id, cmd)
            rows = result.rows if hasattr(result, "rows") else []
            output = {
                "status": "success",
                "count": len(rows),
                "rows": rows[: arguments.limit],
            }
            return ToolResult(output=str(output), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("RelationQueryTool failed: %s", e)
            return ToolResult(output=f"关系查询失败: {e}", is_error=True)


class TemporalQueryTool(BaseTool):
    """Query temporal/episodic data in a time range.

    Uses QueryService.execute() with '.temporal range()' DSL command.
    """

    name = "query_temporal"
    description = (
        "查询时序/事件数据。"
        "参数: from_time(可选,ISO格式), to_time(可选,ISO格式), workspace_id(默认default)。"
        "基于本体进行查询——通过 QueryService 执行 '.temporal range()' DSL 命令。"
    )
    input_model = TemporalQueryInput

    def is_read_only(self, arguments: TemporalQueryInput) -> bool:
        return True

    async def execute(self, arguments: TemporalQueryInput, context: ToolExecutionContext) -> ToolResult:
        try:
            from odap.infra.query import get_query_service

            qs = get_query_service()
            cmd_parts = ['.temporal range(']
            if arguments.from_time:
                cmd_parts.append(f'"{arguments.from_time}", ')
            if arguments.to_time:
                cmd_parts.append(f'"{arguments.to_time}"')
            cmd_parts.append(')')
            cmd = ''.join(cmd_parts)
            result = qs.execute(arguments.workspace_id, cmd)
            rows = result.rows if hasattr(result, "rows") else []
            output = {
                "status": "success",
                "count": len(rows),
                "rows": rows[:20],
            }
            return ToolResult(output=str(output), is_error=False, metadata=output)
        except Exception as e:
            logger.warning("TemporalQueryTool failed: %s", e)
            return ToolResult(output=f"时序查询失败: {e}", is_error=True)
