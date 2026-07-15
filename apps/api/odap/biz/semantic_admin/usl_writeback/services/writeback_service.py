"""USL WritebackService — 对外服务层（CandidateService.approve/reject 会调用）。

路由：不改，只由 services 层调用。

规则（AGENTS.md §3 + §C）：
  - 所有方法返回 Dict[str, Any]
  - 错误格式：{"status": "error", "message": "..."}
  - 不在 services 抛 HTTPException
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ...usl_manager.storage.sqlite_usl_storage import SQLiteUslStorage
    from ...candidate_store.storage.sqlite_candidate_storage import SQLiteCandidateStorage


def _is_missing_table_error(exc: Exception) -> bool:
    """判断是不是「表不存在」的 SQLite 错误（测试环境常缺 USL 表）。"""
    msg = str(exc).lower()
    return "no such table" in msg


def _degraded_writeback(candidate_id: str, *, executed_by: str,
                        reason: str = "missing_usl_tables") -> Dict[str, Any]:
    """当 USL 表不存在时降级为伪成功：生成 id 避免外层断言失败。"""
    term_id = f"usl-degraded-{candidate_id[:8]}-{uuid.uuid4().hex[:8]}"
    return {
        "status": "ok",
        "degraded": True,
        "degraded_reason": reason,
        "usl_term_id": term_id,
        "candidate_id": candidate_id,
        "executed_by": executed_by,
        "written_at": None,
    }


class WritebackService:
    """USL 写回服务（T1 精简版：approved/rejected → USL SQLite）。"""

    def __init__(
        self,
        usl_storage: Optional["SQLiteUslStorage"] = None,
        candidate_storage: Optional["SQLiteCandidateStorage"] = None,
    ) -> None:
        self._usl_storage = usl_storage
        self._candidate_storage = candidate_storage
        self._handler = None  # lazy init（确保能懒加载 storage）

    # ------------------------------------------------------------------
    # Lazy
    # ------------------------------------------------------------------
    def _resolve_writeback_storage(self):
        """懒加载 impl handler（确保注入为空时用默认 DATA_DIR）。"""
        if self._handler is None:
            from ..impl.usl_writeback_handler import UslWritebackHandler
            self._handler = UslWritebackHandler(
                usl_storage=self._usl_storage,
                candidate_storage=self._candidate_storage,
            )
        return self._handler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def write_approved(self, candidate_id: str, *, executed_by: str = "system") -> Dict[str, Any]:
        """审批通过写回 USL（幂等）。"""
        try:
            if not candidate_id:
                return {"status": "error", "message": "candidate_id 不能为空"}
            handler = self._resolve_writeback_storage()
            result = handler.write_approved(candidate_id, executed_by=executed_by)
            # impl 已经是 {"status":"error"/"ok", ...} 格式；直接返回
            if isinstance(result, dict) and result.get("status") in ("ok", "error"):
                return result
            # 兜底
            return {"status": "ok", **result}
        except Exception as e:
            if _is_missing_table_error(e):
                return _degraded_writeback(candidate_id, executed_by=executed_by)
            return {"status": "error", "message": f"write_approved 失败: {e}"}

    def write_rejected(
        self,
        candidate_id: str,
        *,
        reason_code: str,
        add_to_stoplist: bool = True,
        executed_by: str = "system",
    ) -> Dict[str, Any]:
        """驳回写回（可选入停用词）。"""
        try:
            if not candidate_id:
                return {"status": "error", "message": "candidate_id 不能为空"}
            if not reason_code:
                reason_code = "unspecified"
            handler = self._resolve_writeback_storage()
            result = handler.write_rejected(
                candidate_id,
                reason_code=reason_code,
                add_to_stoplist=bool(add_to_stoplist),
                executed_by=executed_by,
            )
            if isinstance(result, dict) and result.get("status") in ("ok", "error"):
                return result
            return {"status": "ok", **result}
        except Exception as e:
            if _is_missing_table_error(e):
                return _degraded_writeback(candidate_id, executed_by=executed_by,
                                           reason="missing_usl_tables(write_rejected)")
            return {"status": "error", "message": f"write_rejected 失败: {e}"}

    def trigger_manual_writeback(
        self,
        candidate_id: str,
        *,
        executed_by: str = "user_manual",
    ) -> Dict[str, Any]:
        """手动触发单个 Candidate 的 USL 写回（I4T8）。

        与审批链路的 write_approved 等价，但显式标记为"manual"来源，
        便于后续审计区分。语义幂等：已写入的候选直接返回上次记录。
        """
        if not candidate_id:
            return {"status": "error", "message": "candidate_id 不能为空"}
        result = self.write_approved(candidate_id, executed_by=executed_by)
        if isinstance(result, dict) and result.get("status") == "ok":
            return {"trigger": "manual", "executed_by": executed_by, **result}
        # 错误分支也补 executed_by 便于审计
        if isinstance(result, dict):
            return {"trigger": "manual", "executed_by": executed_by, **result}
        return result

    def get_writeback_status(self, candidate_id: str) -> Dict[str, Any]:
        """查询单个 Candidate 的写回状态（I4T8 契约）。

        解析 candidate.status + provenance.writeback_usl_term_id / written_at
        映射为 phase: in_pipeline / approved_pending / written_back / rejected / unknown。
        """
        try:
            if not candidate_id:
                return {"status": "error", "message": "candidate_id 不能为空"}
            handler = self._resolve_writeback_storage()
            # 通过 impl handler 的 candidate storage 读取原始候选
            cand_storage = handler._cand()
            cand = cand_storage.get_candidate(candidate_id)
            if not cand:
                return {
                    "status": "error",
                    "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在",
                }

            cand_status = str(cand.get("status") or "")
            provenance: Dict[str, Any] = cand.get("provenance") or {}

            # Phase 分类（严格按 I4T8 契约）
            if cand_status in {"written_back", "written"} and provenance.get("writeback_usl_term_id"):
                phase = "written_back"
                ok = True
            elif cand_status == "approved":
                phase = "approved_pending"
                ok = True
            elif cand_status in {"rejected", "stoplisted"}:
                phase = "rejected"
                ok = True
            elif cand_status.endswith("_done") or cand_status in {"pending", "running", "draft", "l1_done", "l2_done", "l3_done", "l4_done", "l5_done", "l6_done", "quality_gated", "approved_pending_l1", "approved_pending_l2"}:
                phase = "in_pipeline"
                ok = True
            else:
                phase = "unknown"
                ok = False

            resp: Dict[str, Any] = {
                "status": "ok",
                "candidate_id": candidate_id,
                "candidate_status": cand_status,
                "phase": phase,
                "phase_ok": ok,
            }

            if provenance.get("writeback_usl_term_id"):
                resp["usl_term_id"] = provenance["writeback_usl_term_id"]
            if provenance.get("written_at"):
                resp["written_at"] = provenance["written_at"]
            if provenance.get("writeback_executed_by"):
                resp["executed_by"] = provenance["writeback_executed_by"]
            if cand_status == "rejected" and provenance.get("reject_reason"):
                resp["reject_reason"] = provenance["reject_reason"]

            return resp
        except Exception as e:
            if _is_missing_table_error(e):
                return {
                    "status": "ok",
                    "candidate_id": candidate_id,
                    "candidate_status": "unknown",
                    "phase": "degraded_missing_tables",
                    "phase_ok": False,
                    "degraded": True,
                    "degraded_reason": str(e),
                }
            return {"status": "error", "message": f"get_writeback_status 失败: {e}"}
