"""Quality Gate Service（C1 + C2 契约）。

对应 API 契约：
  C1 GET  /quality-gate/reports/{cand_id}      → get_report
  C2 POST /quality-gate/reports                → evaluate_batch

所有方法返回 Dict[str, Any]，错误格式 {"status": "error", "message": "..."}。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .quality_evaluator import (
    QualityEvaluator,
    evaluate_candidate,
    score_to_tier,
)

if TYPE_CHECKING:  # pragma: no cover
    from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
        SQLiteCandidateStorage,
    )


def _overall_label(total_score: float) -> str:
    """按 §4.2 / C1 契约：PASS≥0.8, REVIEW 0.5-0.8, FAIL<0.5。"""
    try:
        s = float(total_score)
    except (TypeError, ValueError):
        return "FAIL"
    if s >= 0.8:
        return "PASS"
    if s >= 0.5:
        return "REVIEW"
    return "FAIL"


def _flatten_submetrics(
    gate1_details: List[Dict[str, Any]],
    gate2_details: List[Dict[str, Any]],
    gate3_details: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """把 3 组 gate details 压成 {gate1: [...], gate2: [...], gate3: [...]}。"""
    def _sanitize(items: Any) -> List[Dict[str, Any]]:
        if not isinstance(items, (list, tuple)):
            return []
        out: List[Dict[str, Any]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            d = {
                "submetric": it.get("submetric"),
                "score": float(it.get("score") or 0),
                "reason": str(it.get("reason") or ""),
                "rule_name": str(it.get("rule_name") or ""),
                "threshold": it.get("threshold"),
            }
            out.append(d)
        return out
    return {
        "gate1": _sanitize(gate1_details),
        "gate2": _sanitize(gate2_details),
        "gate3": _sanitize(gate3_details),
    }


def _build_report_response(
    report_row: Dict[str, Any],
    candidate_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """把 storage 返回的 quality report 行 → C1 契约响应格式。"""
    total = float(report_row.get("total_score") or 0)
    tier = str(report_row.get("tier") or score_to_tier(total))
    return {
        "report_id": str(report_row.get("id")),
        "candidate_id": str(report_row.get("candidate_id")),
        "run_id": (
            str(candidate_row.get("run_id") or candidate_row.get("pipeline_run_id"))
            if candidate_row else None
        ),
        "generated_at": str(report_row.get("created_at") or datetime.now().isoformat()),
        "gate1_score": float(report_row.get("gate1_score") or 0),
        "gate2_score": float(report_row.get("gate2_score") or 0),
        "gate3_score": float(report_row.get("gate3_score") or 0),
        "total_score": total,
        "tier": tier,
        "submetrics": _flatten_submetrics(
            report_row.get("gate1_details") or [],
            report_row.get("gate2_details") or [],
            report_row.get("gate3_details") or [],
        ),
        "overall": _overall_label(total),
        "recommend_auto_skip": total >= 0.9,
    }


# ======================================================================
# QualityGateService 主类
# ======================================================================

class QualityGateService:
    """Quality Gate 服务：get_report + evaluate_batch（对应契约 C1 / C2）。"""

    def __init__(
        self,
        candidate_storage: Optional["SQLiteCandidateStorage"] = None,
        quality_evaluator: Optional[QualityEvaluator] = None,
    ) -> None:
        if candidate_storage is None:
            from odap.biz.semantic_admin.candidate_store.storage import (
                Storage as _CS,
            )
            candidate_storage = _CS()
        self.candidate_storage = candidate_storage
        self.evaluator = quality_evaluator or QualityEvaluator()

    # ------------------------------------------------------------------
    # C1 GET /quality-gate/reports/{cand_id}
    # ------------------------------------------------------------------
    def get_report(
        self,
        candidate_id: str,
        *,
        force: bool = False,
    ) -> Dict[str, Any]:
        """获取 QualityGate 16 指标报告。

        先查 usl_quality_reports.candidate_id 有记录；
        无记录 或 force=True → 重新 evaluate 并 INSERT/REPLACE。
        """
        try:
            cand = self.candidate_storage.get_candidate(candidate_id)
            if not cand:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在",
                }
            existing = None
            if not force:
                existing = self.candidate_storage.get_quality_report_by_candidate(
                    candidate_id
                )
            if existing and not force:
                return _build_report_response(existing, cand)
            # 重新 evaluate
            qr = evaluate_candidate(cand)
            # save_quality_report 是 UPSERT 语义（DELETE + INSERT）
            saved = self.candidate_storage.save_quality_report(qr)
            return _build_report_response(
                saved if isinstance(saved, dict) else qr, cand
            )
        except Exception as e:
            return {
                "status": "error",
                "code": "EVALUATION_ERROR_500",
                "message": f"QualityGate evaluate 异常: {e}",
            }

    # ------------------------------------------------------------------
    # C2 POST /quality-gate/reports
    # ------------------------------------------------------------------
    def evaluate_batch(
        self,
        *,
        candidate_ids: List[str],
        sync: bool = True,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """批量重新评估。

        candidate_ids 长度校验 [1, 100]，超了 → 413 TOO_MANY_IDS。
        任一 candidate 不存在 → 整批 404 CANDIDATE_NOT_FOUND 列不存在的id列表。
        sync=True → 循环 evaluate，返回 {generated: N, reports: [...]}。
        sync=False → 后台 task（实现：在 candidate.provenance 中写
                     async_task_id=uuid，立即 202 返回）。
        """
        try:
            # 1. 长度校验
            ids = list(candidate_ids or [])
            if not ids:
                return {
                    "status": "error",
                    "code": "EMPTY_CANDIDATE_IDS_400",
                    "message": "candidate_ids 不能为空",
                }
            if len(ids) > 100:
                return {
                    "status": "error",
                    "code": "TOO_MANY_IDS_413",
                    "message": (
                        f"candidate_ids 数量={len(ids)}，上限 100"
                    ),
                }
            # 2. 所有 candidate 存在性校验
            missing: List[str] = []
            cand_map: Dict[str, Dict[str, Any]] = {}
            for cid in ids:
                cid_s = str(cid)
                c = self.candidate_storage.get_candidate(cid_s)
                if not c:
                    missing.append(cid_s)
                else:
                    cand_map[cid_s] = c
            if missing:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": (
                        f"以下 candidate_id 不存在: {', '.join(sorted(missing))}"
                    ),
                    "missing_ids": missing,
                }
            # 3. sync=False → 后台任务，立即返回
            if not sync:
                task_id = str(uuid.uuid4())
                # 把 async_task_id 写入每个 candidate 的 provenance
                for cid, c in cand_map.items():
                    old_prov = dict(c.get("provenance") or {})
                    new_prov = dict(old_prov)
                    new_prov["quality_async_task_id"] = task_id
                    new_prov["quality_async_submitted_at"] = (
                        datetime.now().isoformat()
                    )
                    new_prov["quality_async_submitted_by"] = actor_id
                    self.candidate_storage.update_candidate_status(
                        cid,
                        str(c.get("status") or "DRAFT"),
                        provenance=new_prov,
                    )
                self.candidate_storage.append_audit_log(
                    action="quality_evaluate_batch_queued",
                    actor=actor_id,
                    payload={
                        "task_id": task_id,
                        "candidate_ids": ids,
                        "count": len(ids),
                    },
                )
                return {
                    "async_task_id": task_id,
                    "estimated_seconds": max(3, len(ids)),
                    "count": len(ids),
                }
            # 4. sync=True → 循环 evaluate
            reports: List[Dict[str, Any]] = []
            for cid, c in cand_map.items():
                qr = evaluate_candidate(c)
                saved = self.candidate_storage.save_quality_report(qr)
                reports.append(
                    _build_report_response(
                        saved if isinstance(saved, dict) else qr, c
                    )
                )
            self.candidate_storage.append_audit_log(
                action="quality_evaluate_batch_done",
                actor=actor_id,
                payload={"generated": len(reports), "candidate_ids": ids},
            )
            return {"generated": len(reports), "reports": reports}
        except Exception as e:
            return {
                "status": "error",
                "message": f"evaluate_batch 失败: {e}",
            }


__all__ = ["QualityGateService", "_build_report_response", "_overall_label"]
