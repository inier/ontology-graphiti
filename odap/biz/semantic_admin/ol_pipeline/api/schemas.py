"""OL Pipeline + Candidates Pydantic Request/Response Schemas（AGENTS.md §3 路由层 schemas.py）。

规则对齐 usl_manager.api.schemas：
  - 所有可变容器字段 Field(default_factory=list/dict)（AGENTS.md 规则 5）
  - Enum 字段 (str, Enum) 双继承（规则 4）
  - Request 以 CreateXxxRequest / UpdateXxxRequest 命名
  - Response 扁平 dict 对齐 services 返回值
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 共用 Enum（(str, Enum)双继承，保证 JSON 序列化）
# ---------------------------------------------------------------------------

class PipelineRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CandidateStatus(str, Enum):
    NEW = "new"
    GATED = "gated"
    APPROVED = "approved"
    REJECTED = "rejected"
    WRITTEN = "written"
    # ---- T1: 2 级审批 + Writeback 新增状态 ----
    AUDITOR_APPROVED = "auditor_approved"
    ADMIN_PENDING = "admin_pending"
    WRITTEN_BACK = "written_back"
    STOPLISTED = "stoplisted"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class QualityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


# ---------------------------------------------------------------------------
# Pipeline Runs
# ---------------------------------------------------------------------------

class CreatePipelineRunRequest(BaseModel):
    workspace_id: str
    ontology_id: Optional[str] = None
    text: Optional[str] = None
    extra_docs: Optional[List[str]] = Field(default_factory=list)
    source_type: str = "natural_language"
    source_ref: Optional[str] = None
    triggered_by: Optional[str] = None
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PipelineRunResponse(BaseModel):
    id: str
    workspace_id: str
    ontology_id: Optional[str] = None
    source_type: str = "natural_language"
    source_ref: Optional[str] = None
    status: str = "pending"
    triggered_by: Optional[str] = None
    progress: int = 0
    total_input_chars: int = 0
    total_output_candidates: int = 0
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: str
    stats: Optional[Dict[str, Any]] = None


class PipelineRunListResponse(BaseModel):
    items: List[PipelineRunResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

class CandidateResponse(BaseModel):
    id: str
    pipeline_run_id: str
    domain_id: Optional[str] = None
    canonical: str
    semantic_type: Optional[str] = None
    synonyms: List[str] = Field(default_factory=list)
    near_synonyms: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    definition: Optional[str] = None
    examples: List[str] = Field(default_factory=list)
    stoplist_flag: bool = False
    confidence: float = 0.0
    source_text: Optional[str] = None
    provenance: Dict[str, Any] = Field(default_factory=dict)
    status: str = "new"
    created_at: str
    updated_at: str
    quality_report: Optional[Dict[str, Any]] = None  # 附加：get_candidate 时合并进来


class CandidateListResponse(BaseModel):
    items: List[CandidateResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 100


class ApproveCandidateRequest(BaseModel):
    reviewer: str
    comment: Optional[str] = None
    level: int = 1


class RejectCandidateRequest(BaseModel):
    reviewer: str
    comment: Optional[str] = None
    level: int = 1


# ---------------------------------------------------------------------------
# Approval Tasks + Audit Logs（简化版，仅查询用）
# ---------------------------------------------------------------------------

class ApprovalTaskResponse(BaseModel):
    id: str
    candidate_id: str
    level: int = 1
    status: str = "pending"
    assignee: Optional[str] = None
    reviewer: Optional[str] = None
    comment: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: str
    updated_at: str


class ApprovalTaskListResponse(BaseModel):
    items: List[ApprovalTaskResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


class AuditLogResponse(BaseModel):
    id: str
    pipeline_run_id: Optional[str] = None
    candidate_id: Optional[str] = None
    approval_task_id: Optional[str] = None
    action: str
    actor: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 100


# ---------------------------------------------------------------------------
# 通用删除响应
# ---------------------------------------------------------------------------

class DeleteResponse(BaseModel):
    status: str = "ok"
    deleted: bool = False
    id: Optional[str] = None


# ---------------------------------------------------------------------------
# B3 契约：advance / execute-all
# ---------------------------------------------------------------------------

class AdvanceStepRequest(BaseModel):
    """POST /runs/{run_id}/advance 请求体（B3 契约）。"""
    to_layer: str = ""                      # L1 / L2 / L3 / L4 / L5 / L6
    params: Dict[str, Any] = Field(default_factory=dict)


class ExecuteAllRequest(BaseModel):
    """POST /runs/{run_id}/execute-all 请求体（B3 契约）。"""
    params: Dict[str, Any] = Field(default_factory=dict)
    actor_id: str = ""


# ---------------------------------------------------------------------------
# B5 契约：PATCH /candidates/{candidate_id}
# ---------------------------------------------------------------------------

class CandidatePatchRequest(BaseModel):
    """PATCH /candidates/{candidate_id} 请求体（B5 契约）。

    允许字段与 ApprovalWorkflow action_modify 保持一致。
    """
    term: Optional[str] = None
    canonical_label: Optional[str] = None
    term_type: Optional[str] = None
    synonyms: Optional[List[str]] = None
    domain_id: Optional[str] = None
    definition: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class CandidatePatchResponse(BaseModel):
    """PATCH /candidates/{candidate_id} 响应。"""
    candidate_id: str = ""
    updated_fields: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# B7 契约：POST /candidates/{candidate_id}/promote-to-usl
# ---------------------------------------------------------------------------

class PromoteToUslResponse(BaseModel):
    """POST /candidates/{id}/promote-to-usl 响应（B7 契约）。"""
    candidate_id: str = ""
    writeback_status: str = ""               # WRITTEN_BACK / TERM_EXISTS / FAILED ...
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    usl_term_id: Optional[str] = None
    created_new: bool = False
    overwrote_existing: bool = False


# ol_pipeline/schemas/__all__（可选，仅用于显式导出）
__all__ = [
    # Enum
    "PipelineRunStatus", "CandidateStatus", "ApprovalStatus", "QualityGrade",
    # Runs
    "CreatePipelineRunRequest", "PipelineRunResponse", "PipelineRunListResponse",
    # Candidates
    "CandidateResponse", "CandidateListResponse",
    "ApproveCandidateRequest", "RejectCandidateRequest",
    # Approval tasks + audit
    "ApprovalTaskResponse", "ApprovalTaskListResponse",
    "AuditLogResponse", "AuditLogListResponse",
    # Generic
    "DeleteResponse",
    # B3 契约
    "AdvanceStepRequest", "ExecuteAllRequest",
    # B5 / B7 契约
    "CandidatePatchRequest", "CandidatePatchResponse",
    "PromoteToUslResponse",
]
