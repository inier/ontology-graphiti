"""USL Writeback Request/Response Pydantic Schemas（I4T8 契约）。

对应 API 契约（I4T8 + usl_writeback/services 对齐）：
  POST /writeback/candidates/{candidate_id}   — 手动触发写回 → WritebackTriggerResponse
  GET  /writeback/status/{candidate_id}       — 查询写回状态 → WritebackStatusResponse

规则（对齐 AGENTS.md §附录 B）：
  - 可变容器 Field(default_factory=list/dict)（规则 5）
  - 响应字段扁平对齐 services 返回值（trigger_manual_writeback / get_writeback_status）
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ======================================================================
# I4T8 - POST /writeback/candidates/{id}（手动触发）
# ======================================================================

class WritebackTriggerRequest(BaseModel):
    """手动触发写回请求体（全部字段可选：缺省用 user_manual 作为执行主体）。"""

    executed_by: Optional[str] = Field(
        default=None,
        description="执行写回的用户标识，默认 user_manual。注入 Depends(get_current_user) 后会覆盖此字段。",
    )


class WritebackTriggerResponse(BaseModel):
    """手动触发写回响应（严格镜像 WritebackService.trigger_manual_writeback 返回值）。"""

    status: str = Field(..., description="服务层 status：ok / error")
    trigger: Optional[str] = Field(default=None, description="触发来源，固定 'manual' 成功时")
    candidate_id: Optional[str] = Field(default=None, description="被写回的 candidate_id")
    usl_term_id: Optional[str] = Field(default=None, description="成功写入 USL 后的术语 ID")
    written_back: Optional[bool] = Field(default=None, description="是否本次真正写入（幂等场景为 False）")
    idempotent: Optional[bool] = Field(default=None, description="是否幂等（已存在则 True）")
    degraded: Optional[bool] = Field(default=None, description="是否降级（USL 表缺失时伪成功）")
    degraded_reason: Optional[str] = Field(default=None, description="降级原因")
    executed_by: Optional[str] = Field(default=None, description="实际执行主体")
    written_at: Optional[str] = Field(default=None, description="实际写入时间（ISO）；幂等/降级时可能为 None")
    message: Optional[str] = Field(default=None, description="status=error 时的可读错误原因")
    code: Optional[str] = Field(default=None, description="可选错误码，例如 CANDIDATE_NOT_FOUND_404")


# ======================================================================
# I4T8 - GET /writeback/status/{id}（查询写回状态）
# ======================================================================

class WritebackStatusResponse(BaseModel):
    """写回状态查询响应（严格镜像 WritebackService.get_writeback_status 返回值）。"""

    status: str = Field(..., description="服务层 status：ok / error")
    candidate_id: str = Field(default="", description="被查询的 candidate_id")
    candidate_status: str = Field(default="", description="ol_candidates.status 列原始值")
    phase: str = Field(
        default="unknown",
        description="阶段分类：in_pipeline / approved_pending / written_back / rejected / degraded_missing_tables / unknown",
    )
    phase_ok: bool = Field(default=False, description="该 phase 是否属于正常语义")
    usl_term_id: Optional[str] = Field(default=None, description="成功写回后 USL term_id")
    written_at: Optional[str] = Field(default=None, description="写回时间 ISO")
    executed_by: Optional[str] = Field(default=None, description="写回执行主体")
    reject_reason: Optional[str] = Field(default=None, description="rejected 状态时的原因")
    degraded: Optional[bool] = Field(default=None, description="是否降级模式返回")
    degraded_reason: Optional[str] = Field(default=None, description="降级原因")
    message: Optional[str] = Field(default=None, description="status=error 时的错误描述")
    code: Optional[str] = Field(default=None, description="可选错误码，例如 CANDIDATE_NOT_FOUND_404")
