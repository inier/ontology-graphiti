"""Approval Workflow Pydantic Request/Response Schemas（D1~D5 + 新任务接口）。

对应 API 契约（D1~D5 保留）：
  D1 GET    /approvals/pending                       → get_pending_items
  D2 POST   /approvals/submit                        → submit_approval
  D3 POST   /approvals/{cand_id}/review/level-1      → review_level_1
  D4 POST   /approvals/{cand_id}/review/level-2      → review_level_2
  D5 GET    /approvals                               → list_approvals (approval logs)

新增任务接口 schemas：
  list_tasks           → ApprovalTaskRow / ApprovalListResponse
  action_audit         → AuditRequest / TaskResponse
  action_modify        → ModifyRequest / TaskResponse
  action_reject        → RejectRequest / TaskResponse
  action_final_approve → FinalApproveRequest / TaskResponse

规则（对齐 AGENTS.md §附录 B）：
  - 可变容器 Field(default_factory=list/dict)（规则 5）
  - Enum (str, Enum) 双继承（规则 4）
  - Response 扁平对齐 services 返回值
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ======================================================================
# Enum（(str, Enum) 双继承）
# ======================================================================

class ReviewDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ApprovalLevelEnum(str, Enum):
    SUBMIT = "SUBMIT"
    L1 = "L1"
    L2 = "L2"


class TaskType(str, Enum):
    TERM_APPROVAL = "term_approval"
    RELATION_APPROVAL = "relation_approval"
    PATTERN_APPROVAL = "pattern_approval"


class AssignedRole(str, Enum):
    SCHEMA_AUDITOR = "schema_auditor"
    ADMIN = "admin"
    OWNER = "owner"
    COMPLETED = "completed"
    CLOSED = "closed"


# ======================================================================
# D1 GET /approvals/pending（保留）
# ======================================================================

class PendingItemResponse(BaseModel):
    candidate_id: str = ""
    term: str = ""
    synonyms: List[str] = Field(default_factory=list)
    term_type: str = ""
    status: str = ""
    quality_tier: str = ""
    run_id: str = ""
    workspace_id: str = ""
    scenario_id: str = ""
    submitted_by: str = ""
    submitted_at: str = ""
    current_level: str = ""       # L1 / L2


class PendingListResponse(BaseModel):
    items: List[PendingItemResponse] = Field(default_factory=list)
    count: int = 0


# ======================================================================
# D2 POST /approvals/submit（保留）
# ======================================================================

class SubmitApprovalRequest(BaseModel):
    candidate_id: str
    submitter_id: str
    comment: str = ""


class SubmitApprovalResponse(BaseModel):
    candidate_id: str = ""
    new_status: str = ""
    skipped_level_1: bool = False
    submitted_by: str = ""


# ======================================================================
# D3 / D4 Review（保留）
# ======================================================================

class ReviewRequest(BaseModel):
    reviewer_id: str
    decision: str = "APPROVE"   # APPROVE / REJECT
    comment: str = ""
    # 仅 L2 支持 overwrite 参数：若 USL 已存在同 term，是否 overwrite
    overwrite: bool = False


class ReviewResponse(BaseModel):
    candidate_id: str = ""
    level: str = ""              # L1 / L2
    decision: str = ""           # APPROVE / REJECT
    new_status: str = ""         # PENDING_L2 / REJECTED / APPROVED
    reviewer: str = ""
    promote_to_usl: Optional[Dict[str, Any]] = None


# ======================================================================
# D5 审批历史日志（保留 + 重命名）
#   原 ApprovalListResponse → 改名为 ApprovalLogListResponse
#   新增 ApprovalListResponse = 任务分页列表（见下方）
# ======================================================================

class ApprovalLogRow(BaseModel):
    log_id: str = ""
    candidate_id: str = ""
    level: str = ""              # SUBMIT / L1 / L2 / AUDIT / MODIFY / REJECT / FINAL_APPROVE
    reviewer: str = ""
    decision: str = ""           # SUBMIT / APPROVE / REJECT / MODIFY / AUDIT
    comment: str = ""
    decided_at: str = ""
    changed_fields: Dict[str, Any] = Field(default_factory=dict)


class ApprovalLogListResponse(BaseModel):
    """原 ApprovalListResponse（日志列表）——重命名以区分任务列表。"""
    items: List[ApprovalLogRow] = Field(default_factory=list)
    count: int = 0


# ======================================================================
# 新增：任务列表
# ======================================================================

class ApprovalTaskRow(BaseModel):
    """虚拟审批任务行（从 candidate 状态机聚合）。"""
    task_id: str = ""                  # "appr-task-<candidate_id>"
    task_type: str = ""                # term_approval / relation_approval / pattern_approval
    title: str = ""                    # 术语/关系显示名
    priority: int = 0                  # 1(最高) ~ 5(最低)
    status: str = ""                   # 新大写枚举
    assigned_role: str = ""            # schema_auditor / admin / owner / completed / closed
    assignee_user_id: str = ""         # 指派人（submitter 或 candidate.created_by）
    candidate_id: str = ""
    domain_id: str = ""
    created_at: str = ""
    due_at: str = ""


class ApprovalListResponse(BaseModel):
    """任务分页列表（新增，取代原 ApprovalListResponse 的语义）。"""
    items: List[ApprovalTaskRow] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


# ======================================================================
# 新增：动作请求
# ======================================================================

class AuditRequest(BaseModel):
    """POST /tasks/{task_id}/audit（schema_auditor L1 决策）。"""
    comment: str = ""
    decisions: Dict[str, Any] = Field(default_factory=dict)


class ModifyRequest(BaseModel):
    """POST /tasks/{task_id}/modify（修改候选字段）。"""
    candidate_patch: Dict[str, Any] = Field(default_factory=dict)
    editor_comment: str = ""


class RejectRequest(BaseModel):
    """POST /tasks/{task_id}/reject（直接驳回）。"""
    reason: str = ""
    close_task: bool = True


class FinalApproveRequest(BaseModel):
    """POST /tasks/{task_id}/final-approve（admin 终审 + promote_to_usl）。"""
    comment: str = ""
    auto_promote: bool = True
    writeback_now: bool = True


# ======================================================================
# 新增：动作响应（统一）
# ======================================================================

class TaskResponse(BaseModel):
    """任务动作统一响应（action_audit / action_modify /
       action_reject / action_final_approve）。"""
    task_id: str = ""
    candidate_id: str = ""
    new_status: str = ""
    message: str = ""
    # action_final_approve 场景：promote_to_usl 结果
    promote_to_usl: Optional[Dict[str, Any]] = None
    # action_modify 场景：被修改的字段名列表
    updated_fields: List[str] = Field(default_factory=list)
    # action_reject 场景：是否关闭任务
    close_task: Optional[bool] = None
    # action_audit 场景：若状态改变则给出新 task_id（目前格式同 task_id）
    new_task_id_if_changed: Optional[str] = None


# ======================================================================
# 新增：runs 路由需要的 Request（ol_pipeline routes 会从 ol_pipeline/schemas
# 再引用；此处为 ol_pipeline/schemas 提供缺省的补充定义也方便）
# ======================================================================

class CandidatePatchRequest(BaseModel):
    """PATCH /candidates/{candidate_id} 请求体（B5 契约）。

    允许的字段与 action_modify 的 candidate_patch 对应。
    """
    term: Optional[str] = None
    canonical_label: Optional[str] = None
    term_type: Optional[str] = None
    synonyms: Optional[List[str]] = None
    domain_id: Optional[str] = None
    definition: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None


class AdvanceStepRequest(BaseModel):
    """POST /runs/{run_id}/advance 请求体（B3 契约）。"""
    to_layer: str = ""                     # L1 / L2 / L3 / L4 / L5 / L6
    params: Dict[str, Any] = Field(default_factory=dict)


class ExecuteAllRequest(BaseModel):
    """POST /runs/{run_id}/execute-all 请求体（B3 契约）。"""
    params: Dict[str, Any] = Field(default_factory=dict)
    actor_id: str = ""


__all__ = [
    # Enum
    "ReviewDecision", "ApprovalLevelEnum",
    "TaskType", "AssignedRole",
    # D1 原保留
    "PendingItemResponse", "PendingListResponse",
    # D2 原保留
    "SubmitApprovalRequest", "SubmitApprovalResponse",
    # D3/D4 原保留
    "ReviewRequest", "ReviewResponse",
    # D5 原保留（重命名）
    "ApprovalLogRow", "ApprovalLogListResponse",
    # 新任务
    "ApprovalTaskRow", "ApprovalListResponse",
    # 新动作请求
    "AuditRequest", "ModifyRequest", "RejectRequest", "FinalApproveRequest",
    # 新动作响应
    "TaskResponse",
    # ol_pipeline 补充
    "CandidatePatchRequest", "AdvanceStepRequest", "ExecuteAllRequest",
]
