"""Quality Gate + Dashboard Pydantic Request/Response Schemas。

对应 API 契约 C1 / C2 / C3：
  C1 GET  /quality-gate/reports/{cand_id} → get_report
  C2 POST /quality-gate/reports           → evaluate_batch
  C3 GET  /quality-gate/dashboard         → get_dashboard

规则：
  - 可变容器字段 Field(default_factory=list/dict)（AGENTS.md 规则 5）
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

class QualityDimension(str, Enum):
    RANGE_7D = "range_7d"
    RANGE_30D = "range_30d"
    ALL_TIME = "all_time"


class OverallLabel(str, Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


# ======================================================================
# C1 GET  /quality-gate/reports/{cand_id}
# ======================================================================

class SubMetricRow(BaseModel):
    submetric: str = ""
    score: float = 0.0
    reason: str = ""
    rule_name: str = ""
    threshold: Any = None


class SubMetricsGroup(BaseModel):
    gate1: List[SubMetricRow] = Field(default_factory=list)
    gate2: List[SubMetricRow] = Field(default_factory=list)
    gate3: List[SubMetricRow] = Field(default_factory=list)


class QualityReportResponse(BaseModel):
    report_id: str = ""
    candidate_id: str = ""
    run_id: Optional[str] = None
    generated_at: str = ""
    gate1_score: float = 0.0
    gate2_score: float = 0.0
    gate3_score: float = 0.0
    total_score: float = 0.0
    tier: str = ""
    submetrics: SubMetricsGroup = Field(default_factory=SubMetricsGroup)
    overall: str = "FAIL"          # PASS / REVIEW / FAIL
    recommend_auto_skip: bool = False


# ======================================================================
# C2 POST /quality-gate/reports
# ======================================================================

class BatchEvaluateRequest(BaseModel):
    candidate_ids: List[str] = Field(default_factory=list)
    sync: bool = True
    actor_id: str = "system"


class BatchEvaluateSyncResponse(BaseModel):
    generated: int = 0
    reports: List[QualityReportResponse] = Field(default_factory=list)


class BatchEvaluateAsyncResponse(BaseModel):
    async_task_id: str = ""
    estimated_seconds: int = 0
    count: int = 0


# ======================================================================
# C3 GET  /quality-gate/dashboard
# ======================================================================

class StatusBreakdown(BaseModel):
    DRAFT: int = 0
    QUALITY_REVIEW: int = 0
    REVIEW: int = 0
    PENDING_L1: int = 0
    PENDING_L2: int = 0
    APPROVED: int = 0
    REJECTED: int = 0
    OTHER: int = 0


class TierBreakdown(BaseModel):
    S: int = 0
    A: int = 0
    B: int = 0
    C: int = 0
    D: int = 0
    UNRATED: int = 0


class GateBreakdown(BaseModel):
    PASS: int = 0
    REVIEW: int = 0
    FAIL: int = 0


class AvgGateScores(BaseModel):
    gate1_avg: float = 0.0
    gate2_avg: float = 0.0
    gate3_avg: float = 0.0
    total_avg: float = 0.0


class ApprovalTimes(BaseModel):
    l1_avg_secs: int = 0
    l2_avg_secs: int = 0
    total_avg_secs: int = 0
    l1_samples: int = 0
    l2_samples: int = 0
    total_samples: int = 0


class DashboardResponse(BaseModel):
    range: str = "all_time"
    total_candidates: int = 0
    by_status: StatusBreakdown = Field(default_factory=StatusBreakdown)
    by_tier: TierBreakdown = Field(default_factory=TierBreakdown)
    by_quality_gate: GateBreakdown = Field(default_factory=GateBreakdown)
    avg_gate_scores: AvgGateScores = Field(default_factory=AvgGateScores)
    approval_times: ApprovalTimes = Field(default_factory=ApprovalTimes)
    generated_at: Optional[str] = None
    # ---- view=terms_trend 视图 ----
    days: Optional[int] = None
    workspace_id: Optional[str] = None
    domain_id: Optional[str] = None
    daily_points: List[Dict[str, Any]] = Field(default_factory=list)
    accumulative_new: List[Dict[str, Any]] = Field(default_factory=list)
    # ---- view=approvals_breakdown 视图 ----
    by_role: Dict[str, int] = Field(default_factory=dict)
    by_decision: Dict[str, int] = Field(default_factory=dict)
    by_outcome: Dict[str, int] = Field(default_factory=dict)
    avg_l1_seconds: int = 0
    avg_l2_seconds: int = 0


# ======================================================================
# 共用：错误响应（HTTPException 映射时用）
# ======================================================================

class ErrorResponse(BaseModel):
    code: str = "UNKNOWN_ERROR"
    message: str = ""
    missing_ids: Optional[List[str]] = None


__all__ = [
    "QualityDimension", "OverallLabel",
    "SubMetricRow", "SubMetricsGroup", "QualityReportResponse",
    "BatchEvaluateRequest", "BatchEvaluateSyncResponse", "BatchEvaluateAsyncResponse",
    "DashboardResponse",
    "StatusBreakdown", "TierBreakdown", "GateBreakdown",
    "AvgGateScores", "ApprovalTimes",
    "ErrorResponse",
]
