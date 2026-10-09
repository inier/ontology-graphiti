"""USL WritebackService — 对外服务层（CandidateService.approve/reject 会调用）。

路由：不改，只由 services 层调用。

规则（AGENTS.md §3 + §C）：
  - 所有方法返回 Dict[str, Any]
  - 错误格式：{"status": "error", "message": "..."}
  - 不在 services 抛 HTTPException
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from ...candidate_store.storage.sqlite_candidate_storage import (
    ADMIN_PENDING,
    ADMIN_REJECTED,
    APPROVED,
    AUDITOR_APPROVED,
    AUDITOR_MODIFIED,
    AUDITOR_REJECTED,
    CAND_L1_DONE,
    CAND_L2_DONE,
    DRAFT,
    PENDING_REVIEW,
    QUALITY_GATED,
    REJECTED,
    REVIEWER_REJECTED,
    STOPLISTED,
    WRITTEN_BACK,
)

if TYPE_CHECKING:  # pragma: no cover
    from ...usl_manager.storage.sqlite_usl_storage import SQLiteUslStorage
    from ...candidate_store.storage.sqlite_candidate_storage import SQLiteCandidateStorage

logger = logging.getLogger(__name__)


# I4T8 phase 契约值。这是**对外契约字符串**，刻意保持小写，不要和
# candidate.status 的规范大写枚举混为一谈：前者是写回阶段，后者是审批状态机。
_PHASE_WRITTEN_BACK = "written_back"
_PHASE_APPROVED_PENDING = "approved_pending"
_PHASE_REJECTED = "rejected"
_PHASE_IN_PIPELINE = "in_pipeline"
_PHASE_UNKNOWN = "unknown"

# 已终批、等待写回。AUDITOR_APPROVED 不在内：HIGH/VERY_HIGH 档还需 L2 admin 终审，
# 此时它仍在审批流水线里（原先这里落到 unknown，会把正常在审候选报成异常）。
_PENDING_WRITEBACK = frozenset({APPROVED})

_REJECTED_LIKE = frozenset({
    REJECTED, AUDITOR_REJECTED, REVIEWER_REJECTED, ADMIN_REJECTED, STOPLISTED,
})

_IN_APPROVAL = frozenset({
    DRAFT, CAND_L1_DONE, CAND_L2_DONE, QUALITY_GATED, PENDING_REVIEW,
    AUDITOR_MODIFIED, AUDITOR_APPROVED, ADMIN_PENDING,
})


def _classify_phase(cand_status: str, provenance: Dict[str, Any]) -> Tuple[str, bool]:
    """candidate.status（规范大写枚举）→ I4T8 phase 契约值。

    状态机外的值显式返回 ("unknown", False)，不猜一个 phase 兜底（规则 14 禁止
    猜测性反推）——让调用方从 phase_ok=False 看见状态漂移，而不是看见假绿灯。
    """
    if cand_status == WRITTEN_BACK and provenance.get("writeback_usl_term_id"):
        return _PHASE_WRITTEN_BACK, True
    if cand_status in _PENDING_WRITEBACK:
        return _PHASE_APPROVED_PENDING, True
    if cand_status in _REJECTED_LIKE:
        return _PHASE_REJECTED, True
    if cand_status in _IN_APPROVAL:
        return _PHASE_IN_PIPELINE, True
    return _PHASE_UNKNOWN, False


def _is_missing_table_error(exc: Exception) -> bool:
    """判断是不是「表不存在」的 SQLite 错误（测试环境常缺 USL 表）。"""
    msg = str(exc).lower()
    return "no such table" in msg


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

    def _notify_gap_resolved(self, candidate_id: str, outcome: str,
                             *, term_id: str | None = None) -> None:
        """侧道回调 gap_pool，推进缺口状态机。惰性导入规避环；异常绝不影响 writeback。"""
        try:
            from odap.biz.semantic_admin.gap_pool.services.gap_service import GapService
            GapService().on_candidate_resolved(candidate_id, outcome, term_id=term_id)
        except Exception as e:
            logger.warning("gap 回调失败(candidate=%s, outcome=%s): %s",
                           candidate_id, outcome, e)
        if outcome == "adopted":
            self._maybe_auto_replay(candidate_id)

    def _maybe_auto_replay(self, candidate_id: str) -> None:
        """writeback 成功后侧道自动回放（ADR-088 D8）。

        开关 GAP_REGRESSION_AUTO_REPLAY（默认 off）：回放成本未实测前不默认开。
        绝不传播 writeback 主路径：无事件循环/无回归集 → 显式 warning 或 no-op；
        回放任务内部异常只 logger.warning。
        """
        import os
        if os.environ.get("GAP_REGRESSION_AUTO_REPLAY", "").lower() not in (
                "1", "true", "on", "yes"):
            return
        try:
            import asyncio
            from odap.biz.semantic_admin.gap_pool.services.gap_service import GapService
            from odap.biz.semantic_admin.gap_pool.regression.service import (
                RegressionService,
            )
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # writeback 可能在同步上下文被调（如审批脚本）：无循环无法
                # create_task，显式 warning（规则 14：不静默吞）
                logger.warning(
                    "GAP_REGRESSION_AUTO_REPLAY=on 但当前无事件循环，"
                    "跳过自动回放(candidate=%s)", candidate_id)
                return
            reg_svc = RegressionService()
            gap_svc = GapService()

            async def _replay() -> None:
                try:
                    gap = gap_svc.storage.get_by_candidate_id(candidate_id)
                    if not gap:
                        return
                    await reg_svc.auto_replay_for_scope(gap["scope_key"])
                except Exception as e:
                    logger.warning("自动回放失败(candidate=%s): %s",
                                   candidate_id, e)

            loop.create_task(_replay())
        except Exception as e:
            logger.warning("自动回放侧道异常(candidate=%s): %s", candidate_id, e)

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
                if result.get("status") == "ok":
                    self._notify_gap_resolved(
                        candidate_id, "adopted",
                        term_id=result.get("usl_term_id"),
                    )
                return result
            # 兜底
            return {"status": "ok", **result}
        except Exception as e:
            # 规则14：缺表等基础设施故障禁止伪成功降级，必须显式 error 让上层感知，
            # 由审批链路（_approval_helper._writeback_ok）判失败并保留 candidate 状态。
            code = (
                "WRITEBACK_FAILED_MISSING_TABLES"
                if _is_missing_table_error(e)
                else "WRITEBACK_FAILED"
            )
            return {"status": "error", "code": code, "message": f"write_approved 失败: {e}"}

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
                if result.get("status") == "ok":
                    self._notify_gap_resolved(candidate_id, "rejected")
                return result
            return {"status": "ok", **result}
        except Exception as e:
            # 规则14：缺表等基础设施故障禁止伪成功降级，必须显式 error 让上层感知。
            code = (
                "WRITEBACK_FAILED_MISSING_TABLES"
                if _is_missing_table_error(e)
                else "WRITEBACK_FAILED"
            )
            return {"status": "error", "code": code, "message": f"write_rejected 失败: {e}"}

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

            phase, ok = _classify_phase(cand_status, provenance)

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
            if phase == _PHASE_REJECTED and provenance.get("reject_reason"):
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
