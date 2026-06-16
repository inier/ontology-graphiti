import asyncio
import logging
from typing import Any, Dict, List, Optional

from .parser import QueryParser
from .protocols import (
    QueryResult, QuerySource,
    SchemaSource, EntitySource, TopoSource,
    TemporalSource as TemporalSourceProtocol,
    UnstructuredSource as UnstructuredSourceProtocol,
)
from .sources import (
    SchemaSourceImpl, EntitySourceImpl, TopoSourceImpl,
    TemporalSource, UnstructuredSourceImpl,
)

logger = logging.getLogger(__name__)


class QueryService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        schema_source: Optional[SchemaSource] = None,
        entity_source: Optional[EntitySource] = None,
        topo_source: Optional[TopoSource] = None,
        temporal_source: Optional[TemporalSource] = None,
    ):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._parser = QueryParser()
        self._schema_source = schema_source or SchemaSourceImpl()
        self._entity_source = entity_source or EntitySourceImpl()
        self._topo_source = topo_source or TopoSourceImpl()
        self._temporal_source = temporal_source or TemporalSource()
        self._agent_safe_mode = False
        self._registered_tool_sources: Dict[str, Any] = {}
        self._initialized = True

    def enable_agent_safe_mode(self, enabled: bool = True):
        self._agent_safe_mode = enabled

    def register_tool_source(self, source_name: str, source_handler: Any):
        self._registered_tool_sources[source_name] = source_handler

    def execute(self, workspace_id: str, query: str, limit: int = 20, agent_safe: bool = False) -> QueryResult:
        parsed = self._parser.parse(query, limit)
        if agent_safe or self._agent_safe_mode:
            blocked = self._check_agent_safe_block(parsed)
            if blocked:
                return blocked
        try:
            rows = self._dispatch_source(parsed, workspace_id)
            return self._build_result(parsed, rows)
        except Exception as e:
            logger.error(f"QueryService execute error: {e}")
            return self._build_error_result(parsed, str(e))

    async def execute_async(self, workspace_id: str, query: str, limit: int = 20, agent_safe: bool = False) -> QueryResult:
        """Async version of execute() - runs in thread pool to avoid blocking event loop.

        Use this in async contexts (FastAPI routes, async services) where execute()
        may perform I/O (Neo4j queries, SQLite access) that would block the event loop.
        """
        return await asyncio.to_thread(self.execute, workspace_id, query, limit, agent_safe)

    def _check_agent_safe_block(self, parsed) -> Optional[QueryResult]:
        if parsed.source in (QuerySource.SCHEMA, QuerySource.ENTITY):
            return None
        return QueryResult(
            source=parsed.source,
            rows=[],
            total=0,
            explain={"source": parsed.source.value, "agent_safe": True, "message": "Write operations blocked in agent safe mode"},
        )

    def _dispatch_source(self, parsed, workspace_id: str) -> List[Dict[str, Any]]:
        dispatch_map = {
            QuerySource.SCHEMA: lambda: self._execute_schema(parsed.filters),
            QuerySource.ENTITY: lambda: self._execute_entity(parsed.filters, parsed.limit, workspace_id),
            QuerySource.TOPO: lambda: self._execute_topo(parsed.action, parsed.action_params, workspace_id),
            QuerySource.TEMPORAL: lambda: self._execute_temporal(parsed.action, parsed.action_params, workspace_id),
            QuerySource.UNSTRUCTURED: lambda: self._execute_unstructured(parsed.filters, parsed.limit, workspace_id),
        }
        handler = dispatch_map.get(parsed.source)
        return handler() if handler else []

    def _build_result(self, parsed, rows: List[Dict[str, Any]]) -> QueryResult:
        return QueryResult(
            source=parsed.source,
            rows=rows[:parsed.limit],
            total=len(rows),
            explain={"source": parsed.source.value, "filters": parsed.filters, "action": parsed.action},
        )

    def _build_error_result(self, parsed, err: str) -> QueryResult:
        return QueryResult(
            source=parsed.source,
            rows=[],
            total=0,
            explain={"error": err, "source": parsed.source.value},
        )

    def explain(self, workspace_id: str, query: str) -> Dict[str, Any]:
        parsed = self._parser.parse(query)
        return {
            "source": parsed.source.value,
            "filters": parsed.filters,
            "action": parsed.action,
            "action_params": parsed.action_params,
            "limit": parsed.limit,
            "workspace_id": workspace_id,
        }

    def validate(self, query: str) -> Dict[str, Any]:
        try:
            parsed = self._parser.parse(query)
            errors = []
            if not parsed.source:
                errors.append("Unknown query source")
            return {
                "valid": len(errors) == 0,
                "source": parsed.source.value if parsed.source else None,
                "filters": parsed.filters,
                "action": parsed.action,
                "errors": errors,
            }
        except Exception as e:
            return {
                "valid": False,
                "source": None,
                "filters": {},
                "action": None,
                "errors": [str(e)],
            }

    def list_sources(self) -> List[Dict[str, Any]]:
        sources = [
            {"name": "schema", "prefix": ".schema", "description": "Query ontology type definitions", "read_only": True},
            {"name": "entity", "prefix": ".entity", "description": "Query runtime entities", "read_only": True},
            {"name": "topo", "prefix": ".topo", "description": "Query topology relations and graph traversal", "read_only": False},
            {"name": "temporal", "prefix": ".temporal", "description": "Query temporal data (bitemporal)", "read_only": True},
            {"name": "unstructured", "prefix": ".unstructured", "description": "Query unstructured data (documents/vectors via semantic retriever)", "read_only": True},
        ]
        for name in self._registered_tool_sources:
            sources.append({"name": name, "prefix": f".{name}", "description": f"Tool source: {name}", "read_only": True})
        return sources

    def _execute_schema(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        kind = filters.pop("kind", "object_types")
        if kind == "link_definitions":
            return self._schema_source.query_link_definitions(filters)
        elif kind == "action_types":
            return self._schema_source.query_action_types(filters)
        else:
            return self._schema_source.query_object_types(filters)

    def _execute_entity(self, filters: Dict[str, Any], limit: int, workspace_id: str) -> List[Dict[str, Any]]:
        search_query = filters.pop("search", None)
        if search_query:
            return self._entity_source.search_entities(search_query, top_k=limit, workspace_id=workspace_id)
        entity_id = filters.pop("id", None)
        if entity_id:
            entity = self._entity_source.get_entity(entity_id, workspace_id=workspace_id)
            return [entity] if entity else []
        return self._entity_source.query_entities(filters, workspace_id=workspace_id)

    def _execute_topo(self, action: Optional[str], params: Dict[str, Any], workspace_id: str) -> List[Dict[str, Any]]:
        if action == "neighbors":
            entity_id = params.get("id", "")
            direction = params.get("direction", "both")
            depth = params.get("depth", 1)
            return self._topo_source.get_neighbors(entity_id, direction=direction, depth=depth, workspace_id=workspace_id)
        elif action == "path":
            from_id = params.get("from", "")
            to_id = params.get("to", "")
            max_depth = params.get("max_depth", 5)
            subgraph = self._topo_source.traverse(from_id, max_depth=max_depth, workspace_id=workspace_id)
            nodes = {n["id"] for n in subgraph.get("nodes", [])}
            if to_id in nodes:
                return [subgraph]
            return []
        elif action == "relations":
            entity_id = params.get("id", "")
            relation_type = params.get("type")
            return self._topo_source.get_relations(entity_id, relation_type=relation_type, workspace_id=workspace_id)
        entity_id = params.get("id", "")
        if entity_id:
            return self._topo_source.get_neighbors(entity_id, workspace_id=workspace_id)
        return []

    def _execute_temporal(self, action: Optional[str], params: Dict[str, Any], workspace_id: str) -> List[Dict[str, Any]]:
        if action == "history":
            entity_id = params.get("id", "")
            return self._temporal_source.query_history(entity_id)
        elif action == "at":
            valid_time = params.get("valid_time", "")
            return self._temporal_source.query_at_time(valid_time)
        elif action == "range":
            start_time = params.get("start_time", "")
            end_time = params.get("end_time", "")
            entity_type = params.get("type")
            return self._temporal_source.query_range(start_time, end_time, entity_type=entity_type)
        return self._temporal_source.query(params)


_query_service_instance = None

def get_query_service():
    global _query_service_instance
    if _query_service_instance is None:
        _query_service_instance = QueryService()
    return _query_service_instance

