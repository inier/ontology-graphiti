import json
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class AggregationType(str, Enum):
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    DISTINCT = "distinct"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class QueryRequest(BaseModel):
    query: str
    workspace_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    limit: int = 100
    offset: int = 0


class QueryPlan(BaseModel):
    source_tables: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    aggregations: List[Dict[str, Any]] = Field(default_factory=list)
    sort_by: Optional[str] = None
    sort_order: SortOrder = SortOrder.ASC
    limit: int = 100
    offset: int = 0


class QueryResult(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    execution_time_ms: float = 0.0
    plan: Optional[QueryPlan] = None
    error: Optional[str] = None


class DataSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    name: str
    description: str = ""
    data: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entity_counts: Dict[str, int] = Field(default_factory=dict)
