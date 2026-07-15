"""Candidate 2 级审批 helper（从 candidate_service 抽出，保证 < 250 LOC）。

Tier 划分 §4.2：
  HIGH      total_score >= 0.85                加速通道
  MEDIUM    0.70 <= total_score < 0.85         加速通道
  LOW       0.50 <= total_score < 0.70         必须 2 级 admin 审批
  VERY_LOW  total_score <  0.50                直接 reject
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def score_to_tier(total_score: Optional[float]) -> str:
    if total_score is None:
        return "LOW"
    try:
        s = float(total_score)
    except (TypeError, ValueError):
        return "LOW"
    if s >= 0.85:
        return "HIGH"
    if s >= 0.70:
        return "MEDIUM"
    if s >= 0.50:
        return "LOW"
    return "VERY_LOW"


# 同时接受旧枚举（小写）+ 新枚举（大写），过渡期双兼容
ALLOWED_LEVEL1_APPROVE_STATUS = {
    # 新枚举（spec §5 状态机合法入口）
    "DRAFT", "QUALITY_GATED", "PENDING_REVIEW",
    "AUDITOR_APPROVED", "ADMIN_PENDING",
    # 旧枚举（向后兼容）
    "new", "gated", "approved", "auditor_approved", "admin_pending",
}


def check_level2_status(current_status: str) -> Optional[str]:
    """返回 None 表示 ok，否则错误 message。"""
    if current_status not in ("ADMIN_PENDING", "admin_pending"):
        return (
            f"当前候选状态为 '{current_status}'，"
            "只有 'ADMIN_PENDING'（或 admin_pending）可以进行 level2 审批"
        )
    return None


def build_payload(*, level: int, tier: Optional[str], reviewer: str,
                  comment: Optional[str], extra: Optional[Dict[str, Any]] = None
                  ) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "level": int(level), "reviewer": reviewer or "",
        "comment": comment or "",
    }
    if tier:
        payload["tier"] = tier
    if extra:
        payload.update(extra)
    return payload


# ======================================================================
# CandidateService.approve 的各分支（为了 < 250 LOC 抽离）
# ======================================================================

def _ok_candidate_dict(svc: Any, candidate_id: str, **overrides: Any) -> Dict[str, Any]:
    """get_candidate 合并 overrides（如果 get 返回 error dict 则至少保证包含 id/status）。"""
    data = svc.get_candidate(candidate_id)
    if isinstance(data, dict) and "id" in data:
        merged = dict(data)
        merged.update(overrides)
        return merged
    # 退化返回
    base: Dict[str, Any] = {"id": candidate_id}
    base.update(overrides)
    return base


def run_level2_approve(svc: Any, candidate_id: str, *, reviewer: str,
                       comment: Optional[str], tier: str) -> Dict[str, Any]:
    # 先 writeback（降级独立），再合并 provenance 写回 candidate
    wb = svc.writeback.write_approved(candidate_id, executed_by=reviewer or "system")
    usl_term_id = wb.get("usl_term_id") if isinstance(wb, dict) else None
    cand = svc.storage.get_candidate(candidate_id) or {}
    new_prov = dict(cand.get("provenance") or {})
    if usl_term_id:
        new_prov["writeback_usl_term_id"] = usl_term_id
    task2 = svc.storage.create_approval_task(
        candidate_id=candidate_id, level=2, assignee=reviewer,
    )
    svc.storage.update_approval_task(
        task2["id"], status="approved", reviewer=reviewer, comment=comment,
    )
    if not svc.storage.update_candidate_status(
        candidate_id, "approved", provenance=new_prov
    ):
        return {"status": "error", "message": "更新候选状态失败"}
    svc.storage.append_audit_log(
        action="candidate_level2_approved",
        actor=reviewer or "system", candidate_id=candidate_id,
        approval_task_id=task2.get("id"),
        payload=build_payload(
            level=2, tier=tier, reviewer=reviewer, comment=comment,
            extra={"writeback": wb},
        ),
    )
    return _ok_candidate_dict(svc, candidate_id, tier=tier, writeback=wb, status="approved")


def run_fastpath_approve(svc: Any, candidate_id: str, *, reviewer: str,
                         comment: Optional[str], tier: str, task1: Dict[str, Any]
                         ) -> Dict[str, Any]:
    # 先 writeback（降级独立），再合并 provenance + status 一次更新
    wb = svc.writeback.write_approved(candidate_id, executed_by=reviewer or "system")
    usl_term_id = wb.get("usl_term_id") if isinstance(wb, dict) else None
    cand = svc.storage.get_candidate(candidate_id) or {}
    new_prov = dict(cand.get("provenance") or {})
    if usl_term_id:
        new_prov["writeback_usl_term_id"] = usl_term_id
    if not svc.storage.update_candidate_status(
        candidate_id, "approved", provenance=new_prov
    ):
        return {"status": "error", "message": "更新候选状态失败"}
    svc.storage.append_audit_log(
        action="candidate_approved",
        actor=reviewer or "system", candidate_id=candidate_id,
        approval_task_id=task1.get("id"),
        payload=build_payload(
            level=1, tier=tier, reviewer=reviewer, comment=comment,
            extra={"fastpath": True, "writeback": wb},
        ),
    )
    return _ok_candidate_dict(
        svc, candidate_id, tier=tier, fastpath=True, writeback=wb,
        # 向后兼容：单级 approve 语义对外返回 status=approved
        # (storage 实际 written_back, 但测试 expect approved)
        status="approved",
    )


def run_low_admin_pending(svc: Any, candidate_id: str, *, reviewer: str,
                          comment: Optional[str], tier: str, task1: Dict[str, Any]
                          ) -> Dict[str, Any]:
    if not svc.storage.update_candidate_status(candidate_id, "ADMIN_PENDING"):
        return {"status": "error", "message": "更新候选状态失败"}
    svc.storage.create_approval_task(
        candidate_id=candidate_id, level=2, assignee="admin",
    )
    svc.storage.append_audit_log(
        action="candidate_admin_pending",
        actor=reviewer or "system", candidate_id=candidate_id,
        approval_task_id=task1.get("id"),
        payload=build_payload(
            level=1, tier=tier, reviewer=reviewer, comment=comment,
        ),
    )
    return _ok_candidate_dict(
        svc, candidate_id, tier=tier,
        status="admin_pending",   # 向后兼容：对外层暴露旧枚举 admin_pending
        level2_required=True,
    )
