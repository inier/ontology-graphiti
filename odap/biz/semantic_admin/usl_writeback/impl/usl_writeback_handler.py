"""USL Writeback Handler — T1 精简版（Approach A：仅 Candidate → USL SQLite）。

负责：
  1. write_approved：approved → save_term(USL) → candidate.written_back
  2. write_rejected：reject → 可选停用词入库 (stoplist_flag=1) → candidate.stoplisted
  3. 幂等：多次 write_approved 返回同一 usl_term_id

规则（AGENTS.md）：
  - 每次 sqlite3.connect() → 用完 conn.close()（无连接池）
  - 不抛 HTTPException，错误用 {"status":"error","message":...}
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime as _dt
from typing import Any, Dict, Optional, TYPE_CHECKING

from ._internal_utils import (
    CANDIDATE_DB_PATH,
    DEFAULT_DOMAIN_CODE,
    _append_candidate_audit,
    _resolve_or_create_domain_id,
    _update_candidate_row,
)

if TYPE_CHECKING:  # pragma: no cover
    from ...usl_manager.storage.sqlite_usl_storage import SQLiteUslStorage
    from ...candidate_store.storage.sqlite_candidate_storage import SQLiteCandidateStorage


# ======================================================================
# UslWritebackHandler
# ======================================================================

class UslWritebackHandler:
    """Writeback impl。只依赖两个 storage 实例。"""

    def __init__(
        self,
        usl_storage: Optional["SQLiteUslStorage"] = None,
        candidate_storage: Optional["SQLiteCandidateStorage"] = None,
    ) -> None:
        self._usl_storage = usl_storage
        self._candidate_storage = candidate_storage
        self._candidate_db_path: str = (
            candidate_storage.db_path  # type: ignore[attr-defined]
            if (candidate_storage is not None and hasattr(candidate_storage, "db_path"))
            else CANDIDATE_DB_PATH
        )

    # ------------------------------------------------------------------
    # storage lazy-getter
    # ------------------------------------------------------------------
    def _usl(self) -> "SQLiteUslStorage":
        if self._usl_storage is None:
            from ...usl_manager.storage import SQLiteUslStorage as _U
            self._usl_storage = _U()
        return self._usl_storage  # type: ignore[return-value]

    def _cand(self) -> "SQLiteCandidateStorage":
        if self._candidate_storage is None:
            from ...candidate_store.storage import SQLiteCandidateStorage as _C
            self._candidate_storage = _C(db_path=self._candidate_db_path)
        return self._candidate_storage  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # 1. write_approved（幂等）
    # ------------------------------------------------------------------
    def write_approved(self, candidate_id: str, *, executed_by: str = "system") -> Dict[str, Any]:
        cand = self._cand().get_candidate(candidate_id)
        if not cand:
            return {"status": "error", "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在"}

        # 幂等：已 written_back 直接返回写入过的 usl_term_id
        current_status = str(cand.get("status") or "")
        provenance: Dict[str, Any] = cand.get("provenance") or {}
        if (
            current_status in {"written_back", "written"}
            and isinstance(provenance, dict)
            and provenance.get("writeback_usl_term_id")
        ):
            return {
                "status": "ok",
                "usl_term_id": provenance["writeback_usl_term_id"],
                "written_back": False,
                "idempotent": True,
            }

        # 1) 构造 term_dict；domain_id 为空走默认域
        usl = self._usl()
        domain_id = cand.get("domain_id") or None
        if not domain_id:
            domain_id = _resolve_or_create_domain_id(usl, DEFAULT_DOMAIN_CODE)
        term_dict: Dict[str, Any] = {
            "id": str(_uuid.uuid4()),
            "domain_id": domain_id,
            "canonical": cand.get("canonical", ""),
            "semantic_type": cand.get("semantic_type") or "对象类型",
            "definition": cand.get("definition") or "",
            "synonyms": list(cand.get("synonyms") or []),
            "near_synonyms": list(cand.get("near_synonyms") or []),
            "aliases": list(cand.get("aliases") or []),
            "stoplist_flag": False,
        }
        saved = usl.save_term(term_dict)
        usl_term_id = str(saved["id"])

        # 2) UPDATE ol_candidates status + provenance
        written_at = _dt.now().isoformat()
        ok = _update_candidate_row(
            candidate_id,
            status="written_back",
            db_path=self._candidate_db_path,
            provenance_patch={
                "writeback_usl_term_id": usl_term_id,
                "written_at": written_at,
                "writeback_executed_by": executed_by,
            },
            stoplist_flag=0,
        )
        if not ok:  # pragma: no cover
            return {"status": "error", "message": "更新 candidate.status=written_back 失败"}

        # 3) audit_logs
        _append_candidate_audit(
            candidate_id,
            action="writeback_usl_success",
            actor=executed_by,
            payload={"usl_term_id": usl_term_id, "written_at": written_at},
            db_path=self._candidate_db_path,
        )
        return {"status": "ok", "usl_term_id": usl_term_id, "written_back": True}

    # ------------------------------------------------------------------
    # 2. write_rejected（可选加入停用词）
    # ------------------------------------------------------------------
    def write_rejected(
        self,
        candidate_id: str,
        *,
        reason_code: str,
        add_to_stoplist: bool = True,
        executed_by: str = "system",
    ) -> Dict[str, Any]:
        cand = self._cand().get_candidate(candidate_id)
        if not cand:
            return {"status": "error", "code": "CANDIDATE_NOT_FOUND_404",
                    "message": f"候选 {candidate_id} 不存在"}

        new_status = "stoplisted" if add_to_stoplist else "rejected"
        stop_int = 1 if add_to_stoplist else 0
        usl_term_id: Optional[str] = None

        if add_to_stoplist:
            usl = self._usl()
            domain_id = cand.get("domain_id") or None
            if not domain_id:
                domain_id = _resolve_or_create_domain_id(usl, DEFAULT_DOMAIN_CODE)
            stop_term: Dict[str, Any] = {
                "id": str(_uuid.uuid4()),
                "domain_id": domain_id,
                "canonical": cand.get("canonical", ""),
                "semantic_type": cand.get("semantic_type") or "对象类型",
                "definition": f"[停用词] {reason_code}",
                "synonyms": list(cand.get("synonyms") or []),
                "near_synonyms": list(cand.get("near_synonyms") or []),
                "aliases": list(cand.get("aliases") or []),
                "stoplist_flag": True,
            }
            saved = usl.save_term(stop_term)
            usl_term_id = str(saved["id"])

        # UPDATE candidate
        reject_at = _dt.now().isoformat()
        provenance_patch: Dict[str, Any] = {
            "reject_reason_code": reason_code,
            "rejected_at": reject_at,
            "rejected_by": executed_by,
            "stoplist_added": add_to_stoplist,
        }
        if usl_term_id:
            provenance_patch["stoplist_usl_term_id"] = usl_term_id
        ok = _update_candidate_row(
            candidate_id,
            status=new_status,
            db_path=self._candidate_db_path,
            provenance_patch=provenance_patch,
            stoplist_flag=stop_int,
        )
        if not ok:  # pragma: no cover
            return {"status": "error", "message": "更新 candidate 驳回状态失败"}

        _append_candidate_audit(
            candidate_id,
            action="writeback_reject_stoplist" if add_to_stoplist else "writeback_reject",
            actor=executed_by,
            payload={
                "reason_code": reason_code,
                "add_to_stoplist": add_to_stoplist,
                "usl_term_id": usl_term_id,
            },
            db_path=self._candidate_db_path,
        )
        return {
            "status": "ok",
            "candidate_status": new_status,
            "stoplist_usl_term_id": usl_term_id,
            "written_back": True,
        }
