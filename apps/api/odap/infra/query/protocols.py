from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel


class QuerySource(str, Enum):
    SCHEMA = "schema"
    ENTITY = "entity"
    TOPO = "topo"
    TEMPORAL = "temporal"
    UNSTRUCTURED = "unstructured"


class QueryResult(BaseModel):
    source: QuerySource
    rows: List[Dict[str, Any]]
    total: int
    explain: Optional[Dict[str, Any]] = None


@runtime_checkable
class SchemaSource(Protocol):
    def query_object_types(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]: ...
    def query_link_definitions(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]: ...
    def query_action_types(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]: ...


@runtime_checkable
class EntitySource(Protocol):
    def query_entities(self, filters: Dict[str, Any], workspace_id: Optional[str] = None) -> List[Dict[str, Any]]: ...
    def get_entity(self, entity_id: str, workspace_id: Optional[str] = None) -> Optional[Dict[str, Any]]: ...
    def search_entities(self, query: str, top_k: int = 10, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]: ...


@runtime_checkable
class TopoSource(Protocol):
    def get_neighbors(self, entity_id: str, direction: str = "both", depth: int = 1, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]: ...
    def get_relations(self, entity_id: str, relation_type: Optional[str] = None, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]: ...
    def traverse(self, start_id: str, max_depth: int = 3, workspace_id: Optional[str] = None) -> Dict[str, Any]: ...


@runtime_checkable
class TemporalSource(Protocol):
    def query(self, params: Dict[str, Any]) -> List[Dict[str, Any]]: ...
    def query_at_time(self, timestamp: str) -> List[Dict[str, Any]]: ...
    def query_history(self, entity_id: str) -> List[Dict[str, Any]]: ...
    def query_range(self, start_time: str, end_time: str, entity_type: str = None) -> List[Dict[str, Any]]: ...


@runtime_checkable
class UnstructuredSource(Protocol):
    """非结构化数据源（文档/向量）协议。"""

    def search(
        self,
        query: str,
        workspace_id: Optional[str] = None,
        ontology_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]: ...
