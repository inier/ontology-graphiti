"""
Branch API Pydantic Schemas (T358)

Request/Response 模型，对齐 AGENTS.md 规则 4-5。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------- Branch ----------

class CreateBranchRequest(BaseModel):
    name: str
    ontology_id: str
    base_version_id: str
    description: str = ""
    created_by: str = "system"
    head_version_id: Optional[str] = None


class BranchResponse(BaseModel):
    id: str
    name: str
    ontology_id: str
    base_version_id: str
    head_version_id: str
    status: str
    description: str
    created_by: str
    created_at: str
    updated_at: str
    merged_at: Optional[str] = None
    merge_target_branch_id: Optional[str] = None


# ---------- MergeRequest ----------

class CreateMergeRequestRequest(BaseModel):
    source_branch_id: str
    target_branch_id: str
    title: str
    description: str = ""
    base_snapshot: Dict[str, Any] = Field(default_factory=dict)
    ours_snapshot: Dict[str, Any] = Field(default_factory=dict)
    theirs_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_by: str = "system"


class MergeRequestResponse(BaseModel):
    id: str
    source_branch_id: str
    target_branch_id: str
    title: str
    description: str
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    status: str
    base_snapshot: Dict[str, Any] = Field(default_factory=dict)
    ours_snapshot: Dict[str, Any] = Field(default_factory=dict)
    theirs_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_by: str
    created_at: str
    updated_at: str
    merged_at: Optional[str] = None


# ---------- Conflict ----------

class ConflictResponse(BaseModel):
    id: str
    merge_request_id: str
    path: str
    base_value: Any = None
    ours_value: Any = None
    theirs_value: Any = None
    resolution: str
    resolved_value: Any = None
    resolved_by: str = ""
    resolved_at: Optional[str] = None


class ConflictResolutionRequest(BaseModel):
    conflict_id: str
    resolution: str
    resolved_value: Any = None
    resolved_by: str = "system"


class ExecuteMergeResponse(BaseModel):
    merge_request_id: str
    status: str
    merged: Dict[str, Any] = Field(default_factory=dict)
    auto_resolved_count: int = 0
    remaining_conflicts: List[Dict[str, Any]] = Field(default_factory=list)
