"""Candidate Store Pydantic Request/Response Schemas（B2 / B4 / FR-018 / FR-019 契约）。

API 路由路径（统一 /api/semantic-admin/candidates 前缀）：
  FR-018:
    GET  /candidates?level=&status=&domain_id=&page=&page_size=  → 过滤 + 分页列表
    GET  /candidates/{id}                                         → 详情（含 quality_report + approval_records）
    PATCH /candidates/{id}                                       → 修改（HITL 审核台 modify）
    DELETE /candidates/{id}                                      → 软删（status → REJECTED），非 L1 返回 403
  FR-019:
    POST /candidates/batch-delete                               → ≤50 条批量软删
    POST /candidates/export                                      → ≤10000 条 JSON 导出
  B7 契约:
    POST /candidates/{id}/promote-to-usl                        → 手动触发写回 USL（仅 admin）

规则（对齐 AGENTS.md）：
  - 容器字段 Field(default_factory=list/dict)（规则 5）
  - Enum (str, Enum) 双继承（规则 4）
  - Response 字段扁平对齐 services 返回值
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ======================================================================
# Enum（(str, Enum) 双继承）
# ======================================================================

class CandidateLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"
    L6 = "L6"
    ALL = "ALL"


class CandidateDeleteResult(str, Enum):
    SOFT_DELETED = "soft_deleted"
    SKIPPED_NOT_FOUND = "skipped_not_found"
    FAILED = "failed"


# ======================================================================
# 通用 Query Param 模型
# ======================================================================

class CandidateListQuery(BaseModel):
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    domain_id: Optional[str] = None
    pipeline_run_id: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = None
    candidate_type: Optional[str] = None
    canonical_q: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=500)


class CandidateExportQuery(BaseModel):
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    domain_id: Optional[str] = None
    pipeline_run_id: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = None
    candidate_type: Optional[str] = None
    canonical_q: Optional[str] = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10000, ge=1, le=10000)


# ======================================================================
# FR-018: GET /candidates（List Response）
# ======================================================================

class CandidateRow(BaseModel):
    id: str = ""
    canonical: str = ""
    semantic_type: str = ""
    candidate_type: str = ""
    level: str = ""
    status: str = ""
    confidence: float = 0.0
    domain_id: Optional[str] = None
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    pipeline_run_id: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    definition: str = ""
    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class CandidateListResponse(BaseModel):
    items: List[CandidateRow] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


# ======================================================================
# FR-018: GET /candidates/{id}（Detail + report + approvals）
# ======================================================================

class CandidateDetailResponse(BaseModel):
    id: str = ""
    canonical: str = ""
    semantic_type: str = ""
    candidate_type: str = ""
    level: str = ""
    status: str = ""
    confidence: float = 0.0
    domain_id: Optional[str] = None
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    pipeline_run_id: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    near_synonyms: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    definition: str = ""
    hint_parents: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    quality_report: Optional[Dict[str, Any]] = None
    approval_records: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


# ======================================================================
# FR-018: PATCH /candidates/{id}（Modify Request / Response）
# ======================================================================

class CandidateModifyRequest(BaseModel):
    canonical: Optional[str] = None
    synonyms: Optional[List[str]] = None
    near_synonyms: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    definition: Optional[str] = None
    semantic_type: Optional[str] = None
    domain_id: Optional[str] = None
    confidence: Optional[float] = None
    editor_note: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


# ======================================================================
# FR-018: DELETE /candidates/{id}（Soft Delete Response）
# ======================================================================

class CandidateDeleteResponse(BaseModel):
    id: str = ""
    status: str = "ok"
    deleted: bool = False
    result: CandidateDeleteResult = CandidateDeleteResult.SOFT_DELETED


# ======================================================================
# FR-019: POST /candidates/batch-delete（Request + Response）
# ======================================================================

class BatchDeleteRequest(BaseModel):
    candidate_ids: List[str] = Field(default_factory=list, min_length=1, max_length=50)


class BatchDeleteResponse(BaseModel):
    deleted: int = 0
    skipped: int = 0
    failed: int = 0
    total_submitted: int = 0
    ids_deleted: List[str] = Field(default_factory=list)
    ids_skipped: List[str] = Field(default_factory=list)
    ids_failed: List[str] = Field(default_factory=list)


# ======================================================================
# FR-019: POST /candidates/export（Response）
# ======================================================================

class ExportResponse(BaseModel):
    count: int = 0
    total: int = 0
    items: List[Dict[str, Any]] = Field(default_factory=list)


# ======================================================================
# B7: POST /candidates/{id}/promote-to-usl（Request + Response）
# ======================================================================

class PromoteToUSLRequest(BaseModel):
    admin_id: str = "system"
    force_overwrite: bool = False
    parent_term_id: Optional[str] = None


class PromoteToUSLResponse(BaseModel):
    usl_term_id: Optional[str] = None
    created_new: bool = False
    overwrote_existing: bool = False
    term: Dict[str, Any] = Field(default_factory=dict)
    graphiti: Dict[str, Any] = Field(default_factory=dict)
    graphiti_ontology_id: Optional[str] = None
    graphiti_type_id: Optional[str] = None
