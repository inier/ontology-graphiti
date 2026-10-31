"""Wiki API 请求模型（Pydantic v2）。

刻意的「宽松校验」：`owner` / `title` / `content` 都声明为可选，由 service 抛
`ApiError(400, WIKI_XXX_REQUIRED)`。原因 —— 若用 `Field(...)` 必填，FastAPI 会返回
422 且错误体是框架默认结构，**不满足** AC-02 要求的 `400 WIKI_OWNER_REQUIRED`。
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from odap.biz.knowledge.models.common import Citation


class WikiEntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    content: Optional[str] = None
    owner: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    concept_refs: List[str] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    workspace_id: str = ""


class WikiEntryUpdate(BaseModel):
    """部分更新；`version` 为乐观锁期望值（AC-08）。"""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    content: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    concept_refs: Optional[List[str]] = None
    citations: Optional[List[Citation]] = None
    change_note: Optional[str] = None
    version: Optional[str] = Field(
        default=None, description="乐观锁：提交期望的当前版本，不一致返回 409"
    )


class DocsImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: str = Field(..., min_length=1)


class DocsExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str = Field(..., min_length=1)
    target_path: str = Field(..., min_length=1)
    approval_id: Optional[str] = Field(
        default=None,
        description="审批 id（AC-17：缺失或未通过一律 403 WIKI_EXPORT_FORBIDDEN）",
    )


__all__ = ["WikiEntryCreate", "WikiEntryUpdate", "DocsImportRequest", "DocsExportRequest"]
