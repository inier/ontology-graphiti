"""知识域共享模型（Wiki 与文档治理共用）。

SPEC-v2 §6 约束在本模块落为类型不变量：
- `status` 状态机：draft → review → published → superseded|archived（§5.3）。
- `citations[].kind` 固定五类：doc / tbox_node / metric / graph_edge / opa_decision
  （与 openapi-v2 `Citation` 一致，供 AC-06 引用图与 AC-37 证据可解析复用）。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DocStatus(str, Enum):
    """纳管文档/条目状态机（AC-07 归档不物理删除）。"""

    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class CitationKind(str, Enum):
    """引用种类（openapi-v2 `Citation.kind`）。"""

    DOC = "doc"
    TBOX_NODE = "tbox_node"
    METRIC = "metric"
    GRAPH_EDGE = "graph_edge"
    OPA_DECISION = "opa_decision"


class Citation(BaseModel):
    """一条引用（文档引用图的边，也是溯源证据的最小单元）。"""

    model_config = ConfigDict(extra="ignore")

    kind: CitationKind
    ref: str = Field(..., min_length=1)
    asof: Optional[datetime] = None


class GovernedFields(BaseModel):
    """Wiki 条目与纳管文档的同构字段（ARCHITECTURE-v2 §5.2）。"""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    status: DocStatus
    owner: Optional[str] = None
    version: str
    source_ref: Optional[str] = None
    superseded_by: Optional[str] = None
    supersedes: list[str] = Field(default_factory=list)
    content_hash: str
    last_verified: Optional[str] = None


__all__ = ["DocStatus", "CitationKind", "Citation", "GovernedFields"]
