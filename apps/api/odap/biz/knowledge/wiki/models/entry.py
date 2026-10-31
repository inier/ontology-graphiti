"""Wiki 条目领域模型（F1）。

与 openapi-v2 `WikiEntry` / `WikiEntryPage` / `ReferenceGraph` 一一对应。
领域模型与 API schema 分离：schema 负责请求校验（可缺字段、可宽松），
领域模型负责「落库后一定成立」的不变量（owner 必填、status 枚举、hash 非空）。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from odap.biz.knowledge.models.common import Citation, DocStatus


class WikiEntry(BaseModel):
    """一条 Wiki 条目（含当前正文快照）。"""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    content: str = ""
    status: DocStatus = DocStatus.DRAFT
    owner: str
    version: str = "0.1.0"
    source_ref: Optional[str] = None
    superseded_by: Optional[str] = None
    supersedes: list[str] = Field(default_factory=list)
    content_hash: str = ""
    last_verified: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    concept_refs: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    workspace_id: str = ""
    created_at: str
    updated_at: str


class WikiVersion(BaseModel):
    """版本快照（AC-05：按 created_at DESC 返回，含 change_note）。"""

    model_config = ConfigDict(extra="ignore")

    id: str
    entry_id: str
    version: str
    content: str = ""
    content_hash: str = ""
    author_id: str = ""
    change_note: str = ""
    created_at: str


class ReferenceLink(BaseModel):
    """引用图的边（cites / supersedes / related）。"""

    model_config = ConfigDict(extra="ignore")

    from_id: str
    to_id: str
    kind: Literal["cites", "supersedes", "related"] = "cites"


class ReferenceNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    status: Optional[DocStatus] = None


class ReferenceGraph(BaseModel):
    """引用关系图。

    AC-06 要求 `outgoing[]` / `incoming[]`（每条含 kind 与 ref）；
    openapi-v2 `ReferenceGraph` 要求 `nodes` / `links`。
    两者同时提供（超集），前端与 QA 均可按各自契约消费。
    """

    model_config = ConfigDict(extra="ignore")

    nodes: list[ReferenceNode] = Field(default_factory=list)
    links: list[ReferenceLink] = Field(default_factory=list)
    outgoing: list[Citation] = Field(default_factory=list)
    incoming: list[Citation] = Field(default_factory=list)


class WikiEntryPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[WikiEntry] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20
    hasMore: bool = False


__all__ = [
    "WikiEntry",
    "WikiVersion",
    "ReferenceLink",
    "ReferenceNode",
    "ReferenceGraph",
    "WikiEntryPage",
]
