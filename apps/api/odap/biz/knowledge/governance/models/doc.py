"""纳管文档领域模型（F2，openapi-v2 `GovernedDoc` / `GovernedDocPage`）。

与 wiki 条目同构的字段集（ARCHITECTURE-v2 §5.2），差异点：
- `owner` 可为空 —— 空即「待治理」（AC-12 MISSING_OWNER）。
- `role` 记录文档归属角色（pm/architect/designer/fe/be/qa/devops）。
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from odap.biz.knowledge.models.common import Citation, DocStatus


class DocRole(str, Enum):
    """文档责任人角色（SPEC-v2 §6 governed_documents.role）。"""

    PM = "pm"
    ARCHITECT = "architect"
    DESIGNER = "designer"
    FE = "fe"
    BE = "be"
    QA = "qa"
    DEVOPS = "devops"


class GovernedDoc(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    status: DocStatus = DocStatus.DRAFT
    owner: Optional[str] = None
    version: str = "0.1.0"
    source_ref: Optional[str] = None
    superseded_by: Optional[str] = None
    supersedes: list[str] = Field(default_factory=list)
    content_hash: str = ""
    content: str = ""
    last_verified: Optional[str] = None
    role: str = ""
    tags: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class GovernedDocPage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[GovernedDoc] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 20
    hasMore: bool = False


class GovernanceIssueCode(str, Enum):
    """机械校验问题码（openapi-v2 `DocGovernanceIssue.code`）。

    AC-11/12/13/14 分别对应 DANGLING_REF / MISSING_OWNER / STALE / DUPLICATE_HASH。
    `DANGLING_REF` 在 SPEC AC 文案里写作 `DANGLING_REF`，openapi 枚举写作
    `dangling_reference` —— 本模型用 SPEC 的大写码（QA 以 AC 为唯一依据），
    并在响应里同时给出 `code_api` 兼容 openapi 枚举。
    """

    DANGLING_REF = "DANGLING_REF"
    MISSING_OWNER = "MISSING_OWNER"
    ORPHAN_DOC = "ORPHAN_DOC"
    STALE = "STALE"
    DUPLICATE_HASH = "DUPLICATE_HASH"


_API_CODE_COMPAT = {
    GovernanceIssueCode.DANGLING_REF.value: "dangling_reference",
    GovernanceIssueCode.MISSING_OWNER.value: "missing_owner",
    GovernanceIssueCode.ORPHAN_DOC.value: "orphan_doc",
    GovernanceIssueCode.STALE.value: "stale_verified",
    GovernanceIssueCode.DUPLICATE_HASH.value: "duplicate_hash",
}


class GovernanceIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    code_api: str = ""
    severity: str = "error"
    doc_id: str = ""
    detail: str = ""

    def model_post_init(self, __context) -> None:  # noqa: D401 - pydantic hook
        if not self.code_api:
            self.code_api = _API_CODE_COMPAT.get(self.code, self.code.lower())


class GovernanceReport(BaseModel):
    """机械校验报告（AC-11~AC-14）：分类计数 + 问题清单 + pass 判定。"""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    checked: int = 0
    issues: list[GovernanceIssue] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    pass_: bool = Field(default=True, alias="pass")
    errors: int = 0
    warnings: int = 0


class DedupeCandidate(BaseModel):
    """去重合并候选（AC-14）。"""

    model_config = ConfigDict(extra="ignore")

    doc_ids: list[str]
    similarity: float
    reason: str = "same_hash"
    canonical_id: Optional[str] = None


__all__ = [
    "DocRole",
    "GovernedDoc",
    "GovernedDocPage",
    "GovernanceIssueCode",
    "GovernanceIssue",
    "GovernanceReport",
    "DedupeCandidate",
]
