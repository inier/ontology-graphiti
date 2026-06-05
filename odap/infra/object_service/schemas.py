from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ObjectQueryOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class ObjectQueryFilter(BaseModel):
    field: str
    operator: ObjectQueryOperator = ObjectQueryOperator.EQ
    value: Any = None


class ObjectQuerySort(BaseModel):
    field: str
    ascending: bool = True


class ObjectQuery(BaseModel):
    object_type: Optional[str] = None
    filters: List[ObjectQueryFilter] = Field(default_factory=list)
    sorts: List[ObjectQuerySort] = Field(default_factory=list)
    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)
    include_links: bool = False
    include_actions: bool = False
    link_depth: int = Field(1, ge=0, le=3)


class LinkTraversal(BaseModel):
    link_name: str
    direction: str = "outgoing"
    target_type: Optional[str] = None
    depth: int = 1


class ObjectQueryResult(BaseModel):
    object_id: str
    object_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    links: List[Dict[str, Any]] = Field(default_factory=list)
    available_actions: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = ""
    score: Optional[float] = None


class ObjectQueryResponse(BaseModel):
    results: List[ObjectQueryResult]
    total: int
    limit: int
    offset: int


class SemanticQuery(BaseModel):
    query_text: str
    object_type: Optional[str] = None
    top_k: int = 10
    include_links: bool = True
    link_depth: int = 1


class SemanticQueryResponse(BaseModel):
    results: List[ObjectQueryResult]
    total: int
