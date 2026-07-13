"""Approval Service（D1~D5 契约 + 新任务/动作接口）。

对应 API 契约（D1~D5 保留）：
  D1 GET    /approvals/pending                       → get_pending_items
  D2 POST   /approvals/submit                        → submit_approval
  D3 POST   /approvals/{candidate_id}/review/level-1 → review_level_1
  D4 POST   /approvals/{candidate_id}/review/level-2 → review_level_2
  D5 GET    /approvals                                → list_approvals

新增任务接口（task_id = "appr-task-<candidate_id>" 虚拟聚合）：
  list_tasks          → 按角色/状态聚合审批任务
  action_audit        → L1 schema_auditor 审批决策
  action_modify       → 修改候选字段（任何可编辑状态）
  action_reject       → 直接驳回（PENDING_REVIEW / ADMIN_PENDING）
  action_final_approve → L2 admin 终审 + 可选 promote_to_usl

状态机（新大写枚举）：
  DRAFT / L1_DONE / L2_DONE / PENDING_REVIEW / AUDITOR_APPROVED /
  ADMIN_PENDING / APPROVED / REVIEWER_REJECTED / ADMIN_REJECTED /
  WRITTEN_BACK / STOPLISTED

所有方法返回 Dict[str, Any]，错误格式 {"status": "error", "code": XXX_4xx, "message": "..."}。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
        SQLiteCandidateStorage,
    )


class ApprovalLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"


APPROVAL_STATUS_FLOW = {
    # candidate.status → 允许的操作
    "PENDING_L1": ["L1_APPROVE", "L1_REJECT"],
    "PENDING_L2": ["L2_APPROVE", "L2_REJECT"],
    "APPROVED": [],  # 终态，禁止任何 review
    "REJECTED": [],  # 终态，禁止任何 review
}

# 新状态机大写枚举
_NEW_STATUS_SET = {
    "DRAFT", "L1_DONE", "L2_DONE", "PENDING_REVIEW", "AUDITOR_APPROVED",
    "ADMIN_PENDING", "APPROVED", "REVIEWER_REJECTED", "ADMIN_REJECTED",
    "WRITTEN_BACK", "STOPLISTED",
}

# task_type 优先级映射（默认优先级）
_TYPE_PRIORITY: Dict[str, int] = {
    "term_approval": 3,
    "relation_approval": 2,
    "pattern_approval": 1,
    "default": 2,
}


# ======================================================================
# 辅助函数
# ======================================================================

def _row_to_approval_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """把 storage 返回的 approval log 行 → 标准 dict。"""
    return {
        "log_id": str(row.get("id") or row.get("log_id") or ""),
        "candidate_id": str(row.get("candidate_id") or ""),
        "level": str(row.get("level") or ""),
        "reviewer": str(row.get("reviewer") or ""),
        "decision": str(row.get("decision") or ""),
        "comment": str(row.get("comment") or ""),
        "decided_at": str(row.get("created_at") or row.get("decided_at") or ""),
        "changed_fields": (
            dict(row.get("changed_fields")) if isinstance(row.get("changed_fields"), dict)
            else {}
        ),
    }


def _row_to_candidate_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    """把 candidate 行 → pending item / approval item 摘要。"""
    return {
        "candidate_id": str(row.get("id")),
        "term": str(row.get("term") or row.get("canonical") or ""),
        "synonyms": list(row.get("synonyms") or []),
        "term_type": str(row.get("term_type") or row.get("type") or row.get("semantic_type") or ""),
        "status": str(row.get("status") or "DRAFT"),
        "quality_tier": str(row.get("quality_tier") or ""),
        "run_id": str(row.get("run_id") or row.get("pipeline_run_id") or ""),
        "workspace_id": str(row.get("workspace_id") or ""),
        "scenario_id": str(row.get("scenario_id") or ""),
        "submitted_by": str(row.get("created_by") or row.get("created_by_id") or ""),
        "submitted_at": str(row.get("created_at") or ""),
    }


def _parse_candidate_id_from_task(task_id: str) -> str:
    """解析 task_id → candidate_id。

    格式：appr-task-<candidate_id>
    """
    if not task_id:
        return ""
    if task_id.startswith("appr-task-"):
        return task_id.split("appr-task-", 1)[-1]
    # fallback：直接当作 candidate_id
    return task_id


def _norm_status(raw: Any) -> str:
    """把各种状态（旧小写/新大写）归一化为新大写枚举或原样大写。"""
    if not raw:
        return "DRAFT"
    s = str(raw).strip().upper()
    if s in _NEW_STATUS_SET:
        return s
    # 旧小写 → 新大写兼容映射
    legacy_map = {
        "NEW": "DRAFT",
        "GATED": "PENDING_REVIEW",
        "PENDING": "PENDING_REVIEW",
        "APPROVED": "APPROVED",
        "REJECTED": "REVIEWER_REJECTED",
        "WRITTEN": "WRITTEN_BACK",
        "WRITTEN_BACK": "WRITTEN_BACK",
        "STOPLISTED": "STOPLISTED",
        "AUDITOR_APPROVED": "AUDITOR_APPROVED",
        "ADMIN_PENDING": "ADMIN_PENDING",
        "ADMIN_REJECTED": "ADMIN_REJECTED",
        "REVIEWER_REJECTED": "REVIEWER_REJECTED",
        "PENDING_L1": "PENDING_REVIEW",
        "PENDING_L2": "ADMIN_PENDING",
        "QUALITY_REVIEW": "PENDING_REVIEW",
        "REVIEW": "PENDING_REVIEW",
        "AUDITOR_MODIFIED": "PENDING_REVIEW",
        "QUALITY_GATED": "PENDING_REVIEW",
    }
    return legacy_map.get(s, s)


def _priority_from_candidate(cand: Dict[str, Any]) -> int:
    """从 candidate 字段推任务优先级。"""
    tier = str(cand.get("quality_tier") or "").upper()
    if tier in {"S", "VERY_HIGH"}:
        return 1
    if tier in {"A", "HIGH"}:
        return 2
    if tier in {"B", "MEDIUM"}:
        return 3
    if tier in {"C", "LOW"}:
        return 4
    return 5


def _task_type_from_candidate(cand: Dict[str, Any]) -> str:
    """从 candidate.semantic_type/term_type 推 task_type。"""
    st = str(cand.get("semantic_type") or cand.get("term_type") or "").lower()
    if any(k in st for k in ("relation", "link", "edge")):
        return "relation_approval"
    if any(k in st for k in ("pattern", "cardinal", "disjoint")):
        return "pattern_approval"
    return "term_approval"


def _due_at_from_created(created_at: Any, priority: int) -> str:
    """根据创建时间和优先级算 due_at。"""
    dt = None
    if isinstance(created_at, datetime):
        dt = created_at
    elif isinstance(created_at, str) and created_at:
        try:
            txt = created_at.strip()
            if txt.endswith("Z"):
                txt = txt[:-1] + "+00:00"
            dt = datetime.fromisoformat(txt)
        except Exception:
            dt = None
    if dt is None:
        dt = datetime.now()
    days_by_priority = {1: 1, 2: 3, 3: 5, 4: 7, 5: 14}
    delta_days = days_by_priority.get(priority, 7)
    return (dt + timedelta(days=delta_days)).isoformat()


def _assigned_role_from_status(status_norm: str) -> str:
    """根据归一化状态分配角色。"""
    if status_norm == "PENDING_REVIEW":
        return "schema_auditor"
    if status_norm in ("ADMIN_PENDING", "AUDITOR_APPROVED"):
        return "admin"
    if status_norm in ("APPROVED", "WRITTEN_BACK"):
        return "completed"
    if status_norm in ("REVIEWER_REJECTED", "ADMIN_REJECTED", "STOPLISTED"):
        return "closed"
    return "owner"


# ======================================================================
# ApprovalService 主类
# ======================================================================

class ApprovalService:
    """Approval Workflow 服务：D1~D5 + 5 个新任务/动作方法。"""

    def __init__(
        self,
        candidate_storage: Optional["SQLiteCandidateStorage"] = None,
    ) -> None:
        if candidate_storage is None:
            from odap.biz.semantic_admin.candidate_store.storage import (
                Storage as _CS,
            )
            candidate_storage = _CS()
        self.candidate_storage = candidate_storage

    # ------------------------------------------------------------------
    # D1 GET /approvals/pending
    # ------------------------------------------------------------------
    def get_pending_items(
        self,
        *,
        statuses: Optional[List[str]] = None,
        actor_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取待审列表（保留原有 D1 行为）。"""
        try:
            allowed_statuses = {"PENDING_L1", "PENDING_L2"}
            if statuses:
                cleaned = {str(s).upper() for s in statuses if s}
                invalid = cleaned - allowed_statuses
                if invalid:
                    return {
                        "status": "error",
                        "code": "INVALID_STATUS_FILTER_400",
                        "message": (
                            f"statuses 只允许 PENDING_L1/PENDING_L2，"
                            f"非法值: {sorted(invalid)}"
                        ),
                    }
                final_statuses = sorted(cleaned)
            else:
                final_statuses = sorted(allowed_statuses)

            page, per_page = 1, 1000
            filters: Dict[str, Any] = {}
            if workspace_id:
                filters["workspace_id"] = workspace_id
            list_result = self.candidate_storage.list_candidates(
                page=page,
                page_size=per_page,
                statuses=final_statuses,
                **filters,
            )
            cands = list_result.get("items") or [] if isinstance(list_result, dict) else list_result

            items: List[Dict[str, Any]] = []
            for c in cands:
                st = str(c.get("status") or "")
                current_level = "L1" if st == "PENDING_L1" else (
                    "L2" if st == "PENDING_L2" else ""
                )
                summary = _row_to_candidate_summary(c)
                summary["current_level"] = current_level
                items.append(summary)
            return {"items": items, "count": len(items)}
        except Exception as e:
            return {
                "status": "error",
                "message": f"get_pending_items 失败: {e}",
            }

    # ------------------------------------------------------------------
    # D2 POST /approvals/submit
    # ------------------------------------------------------------------
    def submit_approval(
        self,
        *,
        candidate_id: str,
        submitter_id: str,
        comment: str = "",
    ) -> Dict[str, Any]:
        """提交候选到审批流程（保留原有 D2 行为）。"""
        try:
            cand = self.candidate_storage.get_candidate(candidate_id)
            if not cand:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在",
                }
            current_status = str(cand.get("status") or "")
            submitable = {"DRAFT", "QUALITY_REVIEW", "REVIEW"}
            if current_status not in submitable:
                return {
                    "status": "error",
                    "code": "INVALID_STATUS_FOR_SUBMISSION_409",
                    "message": (
                        f"提交审批前 candidate.status 必须为 {sorted(submitable)}，"
                        f"当前={current_status!r}"
                    ),
                }
            tier = str(cand.get("quality_tier") or "")
            if tier in {"S", "A"}:
                next_status = "PENDING_L2"
                skipped_level_1 = True
            else:
                next_status = "PENDING_L1"
                skipped_level_1 = False
            new_prov = dict(cand.get("provenance") or {})
            new_prov["submitted_at"] = datetime.now().isoformat()
            new_prov["submitted_by"] = submitter_id
            new_prov["skipped_level_1"] = skipped_level_1
            self.candidate_storage.update_candidate_status(
                candidate_id,
                next_status,
                provenance=new_prov,
            )
            self.candidate_storage.save_approval_log({
                "candidate_id": candidate_id,
                "level": "SUBMIT",
                "reviewer": submitter_id,
                "decision": "SUBMIT",
                "comment": comment or "",
                "changed_fields": {
                    "status": {"from": current_status, "to": next_status},
                    "skipped_level_1": skipped_level_1,
                },
            })
            self.candidate_storage.append_audit_log(
                action="approval_submit",
                actor=submitter_id,
                payload={
                    "candidate_id": candidate_id,
                    "from_status": current_status,
                    "to_status": next_status,
                    "skipped_level_1": skipped_level_1,
                },
            )
            return {
                "candidate_id": candidate_id,
                "new_status": next_status,
                "skipped_level_1": skipped_level_1,
                "submitted_by": submitter_id,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"submit_approval 失败: {e}",
            }

    # ------------------------------------------------------------------
    # D3 POST /approvals/{candidate_id}/review/level-1
    # ------------------------------------------------------------------
    def review_level_1(
        self,
        *,
        candidate_id: str,
        decision: str,
        reviewer_id: str,
        comment: str = "",
    ) -> Dict[str, Any]:
        """L1 审批（保留原有 D3 行为）。"""
        try:
            dec = str(decision).upper()
            if dec not in {"APPROVE", "REJECT"}:
                return {
                    "status": "error",
                    "code": "INVALID_DECISION_400",
                    "message": "decision 必须为 APPROVE 或 REJECT",
                }
            cand = self.candidate_storage.get_candidate(candidate_id)
            if not cand:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在",
                }
            current_status = str(cand.get("status") or "")
            if current_status != "PENDING_L1":
                return {
                    "status": "error",
                    "code": "LEVEL_MISMATCH_409",
                    "message": (
                        f"L1 审批需要 candidate.status=PENDING_L1，"
                        f"当前={current_status!r}"
                    ),
                }
            next_status = "PENDING_L2" if dec == "APPROVE" else "REJECTED"
            self.candidate_storage.update_candidate_status(
                candidate_id,
                next_status,
                provenance=dict(cand.get("provenance") or {}),
            )
            self.candidate_storage.save_approval_log({
                "candidate_id": candidate_id,
                "level": "L1",
                "reviewer": reviewer_id,
                "decision": dec,
                "comment": comment or "",
                "changed_fields": {
                    "status": {"from": current_status, "to": next_status},
                },
            })
            self.candidate_storage.append_audit_log(
                action="approval_review_l1",
                actor=reviewer_id,
                payload={
                    "candidate_id": candidate_id,
                    "decision": dec,
                    "from_status": current_status,
                    "to_status": next_status,
                },
            )
            return {
                "candidate_id": candidate_id,
                "level": "L1",
                "decision": dec,
                "new_status": next_status,
                "reviewer": reviewer_id,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"review_level_1 失败: {e}",
            }

    # ------------------------------------------------------------------
    # D4 POST /approvals/{candidate_id}/review/level-2
    # ------------------------------------------------------------------
    def review_level_2(
        self,
        *,
        candidate_id: str,
        decision: str,
        reviewer_id: str,
        comment: str = "",
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """L2 审批（通过后自动 promote_to_usl，保留原有 D4 行为）。"""
        try:
            dec = str(decision).upper()
            if dec not in {"APPROVE", "REJECT"}:
                return {
                    "status": "error",
                    "code": "INVALID_DECISION_400",
                    "message": "decision 必须为 APPROVE 或 REJECT",
                }
            cand = self.candidate_storage.get_candidate(candidate_id)
            if not cand:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在",
                }
            current_status = str(cand.get("status") or "")
            if current_status != "PENDING_L2":
                return {
                    "status": "error",
                    "code": "LEVEL_MISMATCH_409",
                    "message": (
                        f"L2 审批需要 candidate.status=PENDING_L2，"
                        f"当前={current_status!r}"
                    ),
                }
            next_status = "APPROVED" if dec == "APPROVE" else "REJECTED"
            self.candidate_storage.update_candidate_status(
                candidate_id,
                next_status,
                provenance=dict(cand.get("provenance") or {}),
            )
            self.candidate_storage.save_approval_log({
                "candidate_id": candidate_id,
                "level": "L2",
                "reviewer": reviewer_id,
                "decision": dec,
                "comment": comment or "",
                "changed_fields": {
                    "status": {"from": current_status, "to": next_status},
                },
            })
            self.candidate_storage.append_audit_log(
                action="approval_review_l2",
                actor=reviewer_id,
                payload={
                    "candidate_id": candidate_id,
                    "decision": dec,
                    "from_status": current_status,
                    "to_status": next_status,
                },
            )
            promote_result: Optional[Dict[str, Any]] = None
            if dec == "APPROVE":
                from odap.biz.semantic_admin.candidate_store.services.candidate_service import (
                    CandidateService,
                )
                cs = CandidateService(candidate_storage=self.candidate_storage)
                promote_result = cs.promote_to_usl(
                    candidate_id=candidate_id,
                    overwrite=overwrite,
                    approver_id=reviewer_id,
                )
            return {
                "candidate_id": candidate_id,
                "level": "L2",
                "decision": dec,
                "new_status": next_status,
                "reviewer": reviewer_id,
                "promote_to_usl": promote_result,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"review_level_2 失败: {e}",
            }

    # ------------------------------------------------------------------
    # D5 GET /approvals
    # ------------------------------------------------------------------
    def list_approvals(
        self,
        *,
        candidate_id: Optional[str] = None,
        level: Optional[str] = None,
        decision: Optional[str] = None,
        reviewer_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """查询审批历史日志（保留原有 D5 行为）。"""
        try:
            if candidate_id:
                logs = self.candidate_storage.list_approvals_by_candidate(candidate_id)
                items = [_row_to_approval_row(r) for r in logs]
                if level:
                    items = [i for i in items if i["level"] == level]
                if decision:
                    items = [i for i in items if i["decision"] == decision]
                if reviewer_id:
                    items = [i for i in items if i["reviewer"] == reviewer_id]
                return {"items": items, "count": len(items)}
            page, per_page = 1, 1000
            list_result = self.candidate_storage.list_candidates(
                page=page, page_size=per_page
            )
            cands = list_result.get("items") or [] if isinstance(list_result, dict) else list_result
            all_items: List[Dict[str, Any]] = []
            for c in cands:
                cid = str(c.get("id"))
                try:
                    logs = self.candidate_storage.list_approvals_by_candidate(cid)
                    for r in logs:
                        all_items.append(_row_to_approval_row(r))
                except Exception:
                    continue
            if level:
                all_items = [i for i in all_items if i["level"] == level]
            if decision:
                all_items = [i for i in all_items if i["decision"] == decision]
            if reviewer_id:
                all_items = [i for i in all_items if i["reviewer"] == reviewer_id]
            return {"items": all_items, "count": len(all_items)}
        except Exception as e:
            return {
                "status": "error",
                "message": f"list_approvals 失败: {e}",
            }

    # ==================================================================
    # 新增方法 1：list_tasks —— 从 candidate 状态机聚合虚拟审批任务
    # ==================================================================

    def list_tasks(
        self,
        *,
        assigned_role: Optional[str] = None,
        status: Optional[List[str]] = None,
        assignee_user_id: Optional[str] = None,
        domain_id: Optional[str] = None,
        order_by: str = "created_at",
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """按角色/状态/指派人/领域聚合虚拟审批任务。

        task_id = "appr-task-<candidate_id>"

        assigned_role 过滤语义：
          - schema_auditor → 只看 status=PENDING_REVIEW
          - admin          → 只看 status=ADMIN_PENDING 或 AUDITOR_APPROVED
          - None           → 不过滤角色

        status 列表过滤（大写，支持新状态机）。
        order_by: "created_at" (默认) 或 "priority"。
        """
        try:
            # 1. assigned_role → 状态预过滤
            role_statuses: Optional[set] = None
            if assigned_role:
                role_lower = str(assigned_role).lower()
                if role_lower == "schema_auditor":
                    role_statuses = {"PENDING_REVIEW"}
                elif role_lower == "admin":
                    role_statuses = {"ADMIN_PENDING", "AUDITOR_APPROVED"}
                else:
                    return {
                        "status": "error",
                        "code": "INVALID_ASSIGNED_ROLE_400",
                        "message": (
                            "assigned_role 仅允许 schema_auditor / admin，"
                            f"当前={assigned_role!r}"
                        ),
                    }

            # 2. 显式 status 过滤（与 role_statuses 求交集）
            query_statuses: Optional[List[str]] = None
            if status:
                normalized_statuses = {_norm_status(s) for s in status if s}
                if role_statuses is not None:
                    normalized_statuses = normalized_statuses & role_statuses
                if normalized_statuses:
                    query_statuses = sorted(normalized_statuses)
            elif role_statuses is not None:
                query_statuses = sorted(role_statuses)

            # 3. 拉取 candidate（不分页先扫描最多 10000 条）
            scan_page, scan_per = 1, 500
            max_scan_pages = 20
            all_cands: List[Dict[str, Any]] = []

            for _p in range(1, max_scan_pages + 1):
                filters: Dict[str, Any] = {}
                if domain_id:
                    filters["domain_id"] = domain_id
                list_result = self.candidate_storage.list_candidates(
                    page=scan_page,
                    page_size=scan_per,
                    statuses=query_statuses,
                    **filters,
                )
                cands = (
                    list_result.get("items") or []
                    if isinstance(list_result, dict) else list_result
                )
                if not cands:
                    break
                all_cands.extend(cands)
                if len(cands) < scan_per:
                    break
                scan_page += 1

            # 4. 过滤 assignee_user_id（基于 provenance.created_by / submitted_by）
            if assignee_user_id:
                uid = str(assignee_user_id)
                filtered: List[Dict[str, Any]] = []
                for c in all_cands:
                    prov = c.get("provenance") or {}
                    submitted_by = str(
                        prov.get("submitted_by")
                        or c.get("created_by")
                        or c.get("created_by_id")
                        or ""
                    )
                    if submitted_by == uid:
                        filtered.append(c)
                all_cands = filtered

            # 5. 构造 tasks
            tasks: List[Dict[str, Any]] = []
            for c in all_cands:
                cid = str(c.get("id") or "")
                norm_st = _norm_status(c.get("status"))
                priority = _priority_from_candidate(c)
                task_type = _task_type_from_candidate(c)
                created_at = c.get("created_at")
                due_at = _due_at_from_created(created_at, priority)
                assignee = str(
                    (c.get("provenance") or {}).get("submitted_by")
                    or c.get("created_by")
                    or c.get("created_by_id")
                    or ""
                )
                title = (
                    str(c.get("canonical") or c.get("term") or "")
                    or f"Task-{cid[:8]}"
                )
                tasks.append({
                    "task_id": f"appr-task-{cid}",
                    "task_type": task_type,
                    "title": title,
                    "priority": priority,
                    "status": norm_st,
                    "assigned_role": _assigned_role_from_status(norm_st),
                    "assignee_user_id": assignee,
                    "candidate_id": cid,
                    "domain_id": str(c.get("domain_id") or ""),
                    "created_at": str(created_at or ""),
                    "due_at": due_at,
                })

            # 6. 排序
            if order_by == "priority":
                tasks.sort(key=lambda t: (t["priority"], t["created_at"]))
            else:
                # 默认 created_at 倒序（最新在前）
                tasks.sort(key=lambda t: t["created_at"], reverse=True)

            # 7. 分页
            total = len(tasks)
            p = max(1, int(page or 1))
            ps = max(1, min(500, int(page_size or 50)))
            start = (p - 1) * ps
            end = start + ps
            page_items = tasks[start:end]

            return {
                "items": page_items,
                "total": total,
                "page": p,
                "page_size": ps,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"list_tasks 失败: {e}",
            }

    # ==================================================================
    # 新增方法 2：action_audit —— schema_auditor L1 审批决策
    # ==================================================================

    def action_audit(
        self,
        *,
        task_id: str,
        approver_id: str,
        comment: str = "",
        decisions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """L1 审批决策（AUDIT 动作）。

        - task_id = "appr-task-<cand_id>"
        - candidate.status 必须是 PENDING_REVIEW（否则 409 STATUS_NOT_PENDING_REVIEW_409）
        - decisions 格式：{approve: bool, l1_fields_ok: bool, quality_ok: bool,
                           suggestions_ok: bool, ...} 可空
        - 状态流转：
            * HIGH/VERY_HIGH + approve=True → ADMIN_PENDING（需要 L2 admin）
            * approve=True（其他 tier）→ AUDITOR_APPROVED（单级通过）
            * approve=False → REVIEWER_REJECTED
        - 记 approval_log（action=AUDIT）+ audit_log
        """
        try:
            candidate_id = _parse_candidate_id_from_task(task_id)
            if not candidate_id:
                return {
                    "status": "error",
                    "code": "INVALID_TASK_ID_400",
                    "message": f"无法解析 task_id={task_id!r}",
                }
            cand = self.candidate_storage.get_candidate(candidate_id)
            if not cand:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在",
                }
            cur_status = _norm_status(cand.get("status"))
            if cur_status != "PENDING_REVIEW":
                return {
                    "status": "error",
                    "code": "STATUS_NOT_PENDING_REVIEW_409",
                    "message": (
                        f"action_audit 需要 candidate.status=PENDING_REVIEW，"
                        f"当前={cur_status!r}"
                    ),
                }

            dec = decisions or {}
            approve = bool(dec.get("approve", False))
            tier = str(cand.get("quality_tier") or "").upper()

            if approve:
                if tier in ("HIGH", "VERY_HIGH", "S", "A"):
                    new_status = "ADMIN_PENDING"
                else:
                    new_status = "AUDITOR_APPROVED"
            else:
                new_status = "REVIEWER_REJECTED"

            # 更新 candidate 状态
            old_prov = dict(cand.get("provenance") or {})
            new_prov = dict(old_prov)
            new_prov["l1_audited_at"] = datetime.now().isoformat()
            new_prov["l1_audited_by"] = str(approver_id)
            new_prov["l1_decisions"] = dict(dec)
            self.candidate_storage.update_candidate_status(
                candidate_id, new_status, provenance=new_prov,
            )

            # approval_log（action=AUDIT，用 level=L1_AUDIT 或 L1 兼容）
            changes_json = {
                "decisions": dict(dec),
                "status": {"from": cur_status, "to": new_status},
            }
            self.candidate_storage.save_approval_log({
                "candidate_id": candidate_id,
                "level": "AUDIT",
                "reviewer": str(approver_id),
                "decision": "APPROVE" if approve else "REJECT",
                "comment": str(comment or ""),
                "changed_fields": changes_json,
            })

            # 审计日志
            self.candidate_storage.append_audit_log(
                action="approval_action_audit",
                actor=str(approver_id),
                payload={
                    "candidate_id": candidate_id,
                    "task_id": task_id,
                    "approve": approve,
                    "from_status": cur_status,
                    "to_status": new_status,
                    "decisions": dict(dec),
                },
            )

            # 状态若变了，task_id 对应的虚拟任务也变了
            new_task_id = f"appr-task-{candidate_id}"
            new_task_id_if_changed = new_task_id if new_status != cur_status else ""

            return {
                "task_id": task_id,
                "candidate_id": candidate_id,
                "new_status": new_status,
                "new_task_id_if_changed": new_task_id_if_changed,
                "approver_id": str(approver_id),
                "approve": approve,
                "comment": str(comment or ""),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"action_audit 失败: {e}",
            }

    # ==================================================================
    # 新增方法 3：action_modify —— 修改候选字段
    # ==================================================================

    def action_modify(
        self,
        *,
        task_id: str,
        approver_id: str,
        candidate_patch: Dict[str, Any],
        editor_comment: str = "",
    ) -> Dict[str, Any]:
        """修改候选字段（任何可修改状态）。

        candidate_patch 允许 key = ["term", "canonical_label", "term_type",
                                       "synonyms", "domain_id", "definition",
                                       "custom_attributes"]
        - 调用 CandidateService.patch_candidate（即 modify_candidate 别名封装）
        - 记 approval_log action=MODIFY + changes_json = patch
        - 记 audit_log
        - candidate.status 维持原状态
        """
        try:
            candidate_id = _parse_candidate_id_from_task(task_id)
            if not candidate_id:
                return {
                    "status": "error",
                    "code": "INVALID_TASK_ID_400",
                    "message": f"无法解析 task_id={task_id!r}",
                }
            cand = self.candidate_storage.get_candidate(candidate_id)
            if not cand:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在",
                }
            cur_status_before = _norm_status(cand.get("status"))

            # 允许的 patch 字段
            ALLOWED_PATCH_KEYS = {
                "term", "canonical_label", "term_type",
                "synonyms", "domain_id", "definition", "custom_attributes",
            }
            if not isinstance(candidate_patch, dict):
                return {
                    "status": "error",
                    "code": "INVALID_PATCH_400",
                    "message": "candidate_patch 必须是 dict",
                }
            clean_patch: Dict[str, Any] = {}
            for k, v in candidate_patch.items():
                if k in ALLOWED_PATCH_KEYS:
                    clean_patch[k] = v

            # 映射到 CandidateService.modify_candidate 字段名
            # task 层字段名 → storage 层字段名
            field_map = {
                "term": "canonical",
                "canonical_label": "canonical",
                "term_type": "semantic_type",
            }
            storage_patch: Dict[str, Any] = {}
            updated_fields: List[str] = []
            for k, v in clean_patch.items():
                storage_key = field_map.get(k, k)
                storage_patch[storage_key] = v
                updated_fields.append(k)
            if editor_comment:
                storage_patch["editor_note"] = editor_comment

            # 调用 CandidateService.modify_candidate（等价于 patch_candidate）
            from odap.biz.semantic_admin.candidate_store.services.candidate_service import (
                CandidateService,
            )
            cs = CandidateService(candidate_storage=self.candidate_storage)
            modify_result = cs.modify_candidate(
                candidate_id,
                patch=storage_patch,
                editor_id=str(approver_id),
            )
            if isinstance(modify_result, dict) and modify_result.get("status") == "error":
                return modify_result

            # approval_log action=MODIFY（追加一条，modify_candidate 内部也会写
            # append_approval_record；这里再写 save_approval_log 保证兼容两种流水）
            self.candidate_storage.save_approval_log({
                "candidate_id": candidate_id,
                "level": "MODIFY",
                "reviewer": str(approver_id),
                "decision": "MODIFY",
                "comment": str(editor_comment or ""),
                "changed_fields": {
                    "patch": dict(clean_patch),
                    "editor_comment": str(editor_comment or ""),
                    "status_kept": cur_status_before,
                },
            })

            return {
                "task_id": task_id,
                "candidate_id": candidate_id,
                "updated_fields": sorted(set(updated_fields)),
                "editor_comment": str(editor_comment or ""),
                "status": cur_status_before,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"action_modify 失败: {e}",
            }

    # ==================================================================
    # 新增方法 4：action_reject —— 直接驳回
    # ==================================================================

    def action_reject(
        self,
        *,
        task_id: str,
        approver_id: str,
        reason: str = "",
        close_task: bool = True,
    ) -> Dict[str, Any]:
        """直接驳回（PENDING_REVIEW → REVIEWER_REJECTED；ADMIN_PENDING → ADMIN_REJECTED）。

        status 要求 PENDING_REVIEW 或 ADMIN_PENDING → 否则 409 STATUS_NOT_REJECTABLE_409
        记 approval_log action=REJECT + changes_json={"reason": ..., "close_task": ...}
        """
        try:
            candidate_id = _parse_candidate_id_from_task(task_id)
            if not candidate_id:
                return {
                    "status": "error",
                    "code": "INVALID_TASK_ID_400",
                    "message": f"无法解析 task_id={task_id!r}",
                }
            cand = self.candidate_storage.get_candidate(candidate_id)
            if not cand:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在",
                }
            cur_status = _norm_status(cand.get("status"))
            if cur_status not in ("PENDING_REVIEW", "ADMIN_PENDING", "AUDITOR_APPROVED"):
                return {
                    "status": "error",
                    "code": "STATUS_NOT_REJECTABLE_409",
                    "message": (
                        f"action_reject 需要 status ∈ "
                        f"{{PENDING_REVIEW, ADMIN_PENDING, AUDITOR_APPROVED}}，"
                        f"当前={cur_status!r}"
                    ),
                }

            if cur_status == "ADMIN_PENDING" or cur_status == "AUDITOR_APPROVED":
                new_status = "ADMIN_REJECTED"
            else:
                new_status = "REVIEWER_REJECTED"

            old_prov = dict(cand.get("provenance") or {})
            new_prov = dict(old_prov)
            new_prov["rejected_at"] = datetime.now().isoformat()
            new_prov["rejected_by"] = str(approver_id)
            new_prov["reject_reason"] = str(reason or "")
            new_prov["reject_close_task"] = bool(close_task)
            self.candidate_storage.update_candidate_status(
                candidate_id, new_status, provenance=new_prov,
            )

            changes_json = {
                "reason": str(reason or ""),
                "close_task": bool(close_task),
                "status": {"from": cur_status, "to": new_status},
            }
            self.candidate_storage.save_approval_log({
                "candidate_id": candidate_id,
                "level": "REJECT",
                "reviewer": str(approver_id),
                "decision": "REJECT",
                "comment": str(reason or ""),
                "changed_fields": changes_json,
            })
            self.candidate_storage.append_audit_log(
                action="approval_action_reject",
                actor=str(approver_id),
                payload={
                    "candidate_id": candidate_id,
                    "task_id": task_id,
                    "from_status": cur_status,
                    "to_status": new_status,
                    "reason": str(reason or ""),
                    "close_task": bool(close_task),
                },
            )
            return {
                "task_id": task_id,
                "candidate_id": candidate_id,
                "new_status": new_status,
                "close_task": bool(close_task),
                "approver_id": str(approver_id),
                "reason": str(reason or ""),
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"action_reject 失败: {e}",
            }

    # ==================================================================
    # 新增方法 5：action_final_approve —— L2 admin 终审 + promote_to_usl
    # ==================================================================

    def action_final_approve(
        self,
        *,
        task_id: str,
        approver_id: str,
        comment: str = "",
        auto_promote: bool = True,
        writeback_now: bool = True,
    ) -> Dict[str, Any]:
        """L2 admin 终审批准 + 可选 promote_to_usl。

        candidate.status 必须是 ADMIN_PENDING / AUDITOR_APPROVED
          → 否则 409 STATUS_NOT_ADMIN_PENDING_409
        更新 status → APPROVED
        记 approval_log action=FINAL_APPROVE
          + changes_json={"auto_promote": ..., "writeback_now": ...}
        若 auto_promote=True：调用 CandidateService.promote_to_usl()
          把 promote 结果加到响应 promote_to_usl_result
        """
        try:
            candidate_id = _parse_candidate_id_from_task(task_id)
            if not candidate_id:
                return {
                    "status": "error",
                    "code": "INVALID_TASK_ID_400",
                    "message": f"无法解析 task_id={task_id!r}",
                }
            cand = self.candidate_storage.get_candidate(candidate_id)
            if not cand:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在",
                }
            cur_status = _norm_status(cand.get("status"))
            if cur_status not in ("ADMIN_PENDING", "AUDITOR_APPROVED"):
                return {
                    "status": "error",
                    "code": "STATUS_NOT_ADMIN_PENDING_409",
                    "message": (
                        f"action_final_approve 需要 status ∈ "
                        f"{{ADMIN_PENDING, AUDITOR_APPROVED}}，"
                        f"当前={cur_status!r}"
                    ),
                }
            new_status = "APPROVED"
            old_prov = dict(cand.get("provenance") or {})
            new_prov = dict(old_prov)
            new_prov["final_approved_at"] = datetime.now().isoformat()
            new_prov["final_approved_by"] = str(approver_id)
            new_prov["auto_promote"] = bool(auto_promote)
            new_prov["writeback_now"] = bool(writeback_now)
            self.candidate_storage.update_candidate_status(
                candidate_id, new_status, provenance=new_prov,
            )

            changes_json = {
                "auto_promote": bool(auto_promote),
                "writeback_now": bool(writeback_now),
                "status": {"from": cur_status, "to": new_status},
            }
            self.candidate_storage.save_approval_log({
                "candidate_id": candidate_id,
                "level": "FINAL_APPROVE",
                "reviewer": str(approver_id),
                "decision": "APPROVE",
                "comment": str(comment or ""),
                "changed_fields": changes_json,
            })
            self.candidate_storage.append_audit_log(
                action="approval_final_approve",
                actor=str(approver_id),
                payload={
                    "candidate_id": candidate_id,
                    "task_id": task_id,
                    "from_status": cur_status,
                    "to_status": new_status,
                    "auto_promote": bool(auto_promote),
                    "writeback_now": bool(writeback_now),
                },
            )

            # auto_promote：调用 CandidateService.promote_to_usl
            promote_to_usl_result: Optional[Dict[str, Any]] = None
            if auto_promote:
                from odap.biz.semantic_admin.candidate_store.services.candidate_service import (
                    CandidateService,
                )
                cs = CandidateService(candidate_storage=self.candidate_storage)
                promote_to_usl_result = cs.promote_to_usl(
                    candidate_id=candidate_id,
                    approver_id=str(approver_id),
                    overwrite=False,
                    force_writeback=bool(writeback_now),
                )

            return {
                "task_id": task_id,
                "candidate_id": candidate_id,
                "new_status": "APPROVED",
                "approver_id": str(approver_id),
                "comment": str(comment or ""),
                "auto_promote": bool(auto_promote),
                "writeback_now": bool(writeback_now),
                "promote_to_usl_result": promote_to_usl_result,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"action_final_approve 失败: {e}",
            }


__all__ = ["ApprovalService", "ApprovalLevel"]
