"""Candidate 2 级审批 helper（从 candidate_service 抽出，保证 < 250 LOC）。

Tier 划分 §4.2：
  HIGH      total_score >= 0.85                加速通道
  MEDIUM    0.70 <= total_score < 0.85         加速通道
  LOW       0.50 <= total_score < 0.70         必须 2 级 admin 审批
  VERY_LOW  total_score <  0.50                直接 reject
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..storage.sqlite_candidate_storage import (
    ADMIN_APPROVED,
    ADMIN_PENDING,
    AUDITOR_APPROVED,
    DRAFT,
    PENDING_REVIEW,
    QUALITY_GATED,
    REJECTED as CAND_REJECTED,
    STOPLISTED as CAND_STOPLISTED,
)


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


# level1 审批的合法入口状态（spec §5 状态机）。只收规范大写枚举：storage 出参已
# 统一归一为大写，再额外容忍一套小写等于让两套词汇继续并存，而且 409 的报错信息
# 会列出一堆永远不可能出现的值，把真正的状态机淹掉。
ALLOWED_LEVEL1_APPROVE_STATUS = frozenset({
    DRAFT, QUALITY_GATED, PENDING_REVIEW, AUDITOR_APPROVED, ADMIN_PENDING,
})


def check_level2_status(current_status: str) -> Optional[str]:
    """返回 None 表示 ok，否则错误 message。"""
    if current_status != ADMIN_PENDING:
        return (
            f"当前候选状态为 '{current_status}'，"
            f"只有 '{ADMIN_PENDING}' 可以进行 level2 审批"
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


def _writeback_failed(svc: Any, candidate_id: str, *, actor: str, action: str,
                      task_id: Optional[str], wb: Any) -> Dict[str, Any]:
    """写回失败 → 记审计 + 显式 error（规则 14：不许无视被调方返回的错误状态）。

    候选停在 APPROVED，这是可恢复的中间态：get_writeback_status 会如实报
    phase=approved_pending，运维可用 trigger_manual_writeback 重试。审批决策本身
    已经落库，所以既不能把整件事报成成功，也不该回滚决策。
    """
    svc.storage.append_audit_log(
        action=action, actor=actor or "system", candidate_id=candidate_id,
        approval_task_id=task_id, payload={"writeback": wb},
    )
    detail = wb.get("message") if isinstance(wb, dict) else str(wb)
    return {
        "status": "error",
        "code": "WRITEBACK_FAILED_502",
        "message": f"审批已记录，但写回 USL 失败（候选停在 APPROVED，可手动重试）: {detail}",
        "writeback": wb,
    }


def _writeback_ok(wb: Any) -> bool:
    return isinstance(wb, dict) and wb.get("status") == "ok"


def run_level2_approve(svc: Any, candidate_id: str, *, reviewer: str,
                       comment: Optional[str], tier: str) -> Dict[str, Any]:
    task2 = svc.storage.create_approval_task(
        candidate_id=candidate_id, level=2, assignee=reviewer,
    )
    svc.storage.update_approval_task(
        task2["id"], status="approved", reviewer=reviewer, comment=comment,
    )
    if not svc.storage.update_candidate_status(candidate_id, ADMIN_APPROVED):
        return {"status": "error", "message": "更新候选状态失败"}
    svc.storage.append_audit_log(
        action="candidate_level2_approved",
        actor=reviewer or "system", candidate_id=candidate_id,
        approval_task_id=task2.get("id"),
        payload=build_payload(level=2, tier=tier, reviewer=reviewer, comment=comment),
    )
    # 写回必须在状态落库之后。write_approved 自己会把候选推进到 WRITTEN_BACK 并
    # merge provenance.writeback_usl_term_id；原先顺序相反，紧随其后的
    # update_candidate_status 又把状态盖回 APPROVED，于是幂等判据
    # (status == WRITTEN_BACK) 永不命中 —— 重复审批不断新建 USL 术语，
    # get_writeback_status 也永远报 approved_pending。
    wb = svc.writeback.write_approved(candidate_id, executed_by=reviewer or "system")
    if not _writeback_ok(wb):
        return _writeback_failed(
            svc, candidate_id, actor=reviewer,
            action="candidate_level2_writeback_failed",
            task_id=task2.get("id"), wb=wb,
        )
    return _ok_candidate_dict(svc, candidate_id, tier=tier, writeback=wb)


def run_fastpath_approve(svc: Any, candidate_id: str, *, reviewer: str,
                         comment: Optional[str], tier: str, task1: Dict[str, Any]
                         ) -> Dict[str, Any]:
    if not svc.storage.update_candidate_status(candidate_id, ADMIN_APPROVED):
        return {"status": "error", "message": "更新候选状态失败"}
    svc.storage.append_audit_log(
        action="candidate_approved",
        actor=reviewer or "system", candidate_id=candidate_id,
        approval_task_id=task1.get("id"),
        payload=build_payload(
            level=1, tier=tier, reviewer=reviewer, comment=comment,
            extra={"fastpath": True},
        ),
    )
    wb = svc.writeback.write_approved(candidate_id, executed_by=reviewer or "system")
    if not _writeback_ok(wb):
        return _writeback_failed(
            svc, candidate_id, actor=reviewer,
            action="candidate_fastpath_writeback_failed",
            task_id=task1.get("id"), wb=wb,
        )
    # 不再用 status="approved" 覆盖出参。写回成功后 storage 里的真实状态是
    # WRITTEN_BACK，硬报 approved 等于对调用方撒谎：前端据此判断「是否还需写回」，
    # 写回状态查询也会和审批返回值互相矛盾。
    return _ok_candidate_dict(svc, candidate_id, tier=tier, fastpath=True, writeback=wb)


def run_low_admin_pending(svc: Any, candidate_id: str, *, reviewer: str,
                          comment: Optional[str], tier: str, task1: Dict[str, Any]
                          ) -> Dict[str, Any]:
    if not svc.storage.update_candidate_status(candidate_id, ADMIN_PENDING):
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
        svc, candidate_id, tier=tier, level2_required=True,
    )


# ======================================================================
# 驳回分支
# ======================================================================

def _reject_writeback_failed(svc: Any, candidate_id: str, *, reviewer: str,
                             comment: Optional[str], level: int,
                             add_to_stoplist: bool, wb: Any) -> Dict[str, Any]:
    """写回失败 → 记审计 + 显式 error，且不写任何审批流水。

    顺序很关键：write_rejected 是驳回的落库动作，必须在记审批流水之前完成。
    否则失败时审批任务已写成 rejected、候选状态却还是原值，留下一条谁也对不上
    的中间态。曾经这里不看 wb，照样把候选标成 STOPLISTED 并报「驳回成功」，
    而 USL 里根本没有对应停用词（规则 14「无视被调方返回的错误状态」）。
    """
    svc.storage.append_audit_log(
        action="candidate_reject_writeback_failed",
        actor=reviewer or "system", candidate_id=candidate_id,
        payload={"level": level, "comment": comment or "",
                 "add_to_stoplist": bool(add_to_stoplist), "writeback": wb},
    )
    detail = wb.get("message") if isinstance(wb, dict) else str(wb)
    return {
        "status": "error",
        "code": "REJECT_WRITEBACK_FAILED_502",
        "message": f"驳回写回 USL 失败，候选状态未变更: {detail}",
        "writeback": wb,
    }


def _pin_reject_status(svc: Any, candidate_id: str, *, cand: Dict[str, Any],
                       reviewer: str, comment: Optional[str],
                       add_to_stoplist: bool) -> None:
    """把候选状态钉成本次驳回决定的终态。

    update_approval_task 是个旧 shim，它会顺手把候选状态改成 AUDITOR_REJECTED，
    而 approver_role 缺失时还硬猜 "schema_auditor"（规则 14 禁止的猜测性默认）。
    驳回的权威结果由 add_to_stoplist 决定，不能让 shim 的猜测盖掉它。
    """
    if not add_to_stoplist:
        svc.storage.update_candidate_status(candidate_id, CAND_REJECTED)
        return
    merged = dict(cand.get("provenance") or {})
    merged["stoplist_added"] = True
    merged["stoplist_by"] = reviewer or "system"
    merged["stoplist_reason"] = comment or ""
    svc.storage.update_candidate_status(
        candidate_id, CAND_STOPLISTED, stoplist_flag=True, provenance=merged,
    )


def _audit_reject(svc: Any, candidate_id: str, *, task_id: Optional[str],
                  reviewer: str, comment: Optional[str], level: int,
                  add_to_stoplist: bool, wb: Any) -> None:
    svc.storage.append_audit_log(
        action="candidate_rejected",
        actor=reviewer or "system", candidate_id=candidate_id,
        approval_task_id=task_id,
        payload={"level": level, "comment": comment or "",
                 "add_to_stoplist": bool(add_to_stoplist), "writeback": wb},
    )
    if not add_to_stoplist:
        return
    # stoplist 相关审计：保证 list_audit_logs 过滤 stoplist 命中
    svc.storage.append_audit_log(
        action="candidate_stoplist_added",
        actor=reviewer or "system", candidate_id=candidate_id,
        approval_task_id=task_id,
        payload={"level": level, "comment": comment or "",
                 "reason": comment or "rejected_by_auditor"},
    )


def run_reject(svc: Any, candidate_id: str, *, reviewer: str, comment: Optional[str],
               level: int, add_to_stoplist: bool) -> Dict[str, Any]:
    cand = svc.storage.get_candidate(candidate_id)
    if not cand:
        return {"status": "error", "message": f"候选 {candidate_id} 不存在"}
    wb = svc.writeback.write_rejected(
        candidate_id,
        reason_code=comment or "rejected_by_auditor",
        add_to_stoplist=bool(add_to_stoplist),
        executed_by=reviewer or "system",
    )
    if not _writeback_ok(wb):
        return _reject_writeback_failed(
            svc, candidate_id, reviewer=reviewer, comment=comment, level=level,
            add_to_stoplist=add_to_stoplist, wb=wb,
        )
    task = svc.storage.create_approval_task(
        candidate_id=candidate_id, level=level, assignee=reviewer,
    )
    svc.storage.update_approval_task(
        task["id"], status="rejected", reviewer=reviewer, comment=comment,
    )
    _pin_reject_status(svc, candidate_id, cand=cand, reviewer=reviewer,
                       comment=comment, add_to_stoplist=add_to_stoplist)
    _audit_reject(svc, candidate_id, task_id=task.get("id"), reviewer=reviewer,
                  comment=comment, level=level, add_to_stoplist=add_to_stoplist, wb=wb)
    # 出参不再把 status 反向翻成旧小写枚举：storage 已统一规范大写，再覆盖成
    # "rejected"/"stoplisted" 会让同一个候选在列表接口和驳回接口里报两套词汇。
    updated = svc.get_candidate(candidate_id)
    if isinstance(updated, dict) and "id" in updated:
        updated["writeback"] = wb
    return updated
