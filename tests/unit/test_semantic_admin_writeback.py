"""Semantic Admin T1 - USL Writeback 单元测试（AGENTS.md §C，≤250 LOC）。"""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest

from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
    SQLiteCandidateStorage,
)
from odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage import (
    SQLiteUslStorage,
)
from odap.biz.semantic_admin.usl_writeback.impl.usl_writeback_handler import (
    UslWritebackHandler,
)
from odap.biz.semantic_admin.usl_writeback.services.writeback_service import (
    WritebackService,
)


@pytest.fixture
def cs(tmp_path: Path) -> SQLiteCandidateStorage:
    return SQLiteCandidateStorage(db_path=str(tmp_path / "c.db"))


@pytest.fixture
def us(tmp_path: Path) -> SQLiteUslStorage:
    return SQLiteUslStorage(db_path=str(tmp_path / "u.db"))


@pytest.fixture
def h(cs: SQLiteCandidateStorage, us: SQLiteUslStorage) -> UslWritebackHandler:
    return UslWritebackHandler(usl_storage=us, candidate_storage=cs)


@pytest.fixture
def wb(cs: SQLiteCandidateStorage, us: SQLiteUslStorage) -> WritebackService:
    return WritebackService(usl_storage=us, candidate_storage=cs)


def _mc(cs: SQLiteCandidateStorage, *, canon: str = "T",
       syn=None, did: Any = None, status: str = "approved",
       stype: str = "对象类型") -> Dict[str, Any]:
    run = cs.create_pipeline_run(workspace_id="ws-1")
    return cs.bulk_insert_candidates([{
        "id": str(uuid.uuid4()), "pipeline_run_id": run["id"],
        "canonical": canon, "semantic_type": stype,
        "synonyms": list(syn or []), "domain_id": did,
        "definition": "d", "confidence": 0.8,
        "status": status, "provenance": {},
    }])[0]


def _cnt(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM usl_terms").fetchone()[0])
    finally:
        conn.close()


# 1. write_approved 幂等 ------------------------------------------------
class TestWriteApprovedIdempotent:
    def test_idempotent_count_unchanged(
        self, wb: WritebackService, cs: SQLiteCandidateStorage, us: SQLiteUslStorage
    ):
        c = _mc(cs, canon="U", syn=["a", "b"])
        b0 = _cnt(us.db_path)
        r1 = wb.write_approved(c["id"], executed_by="u1")
        assert r1["status"] == "ok"
        uid = r1["usl_term_id"]
        assert uid and len(uid) > 0
        assert _cnt(us.db_path) == b0 + 1
        upd = cs.get_candidate(c["id"]) or {}
        assert upd["status"] == "written_back"
        assert (upd.get("provenance") or {}).get("writeback_usl_term_id") == uid

        r2 = wb.write_approved(c["id"], executed_by="u2")
        assert r2["status"] == "ok"
        assert r2["idempotent"] is True
        assert r2["written_back"] is False
        assert r2["usl_term_id"] == uid
        assert _cnt(us.db_path) == b0 + 1


# 2. Conflict Merge: same canonical different ID --------------------------
class TestWriteApprovedConflictMerge:
    def test_merge_reuses_existing(
        self, h: UslWritebackHandler, cs: SQLiteCandidateStorage, us: SQLiteUslStorage
    ):
        dom = us.save_domain({"code": "GENERAL", "display_name": "通用"})
        ex = us.save_term({
            "id": str(uuid.uuid4()), "domain_id": dom["id"],
            "canonical": "MergeMe", "semantic_type": "对象类型",
            "synonyms": ["old"], "definition": "old",
        })
        str(ex["id"])
        c = _mc(cs, canon="MergeMe", syn=["new"])
        b0 = _cnt(us.db_path)
        r = h.write_approved(c["id"], executed_by="u1")
        assert r["status"] == "ok"
        # 不新增（ON CONFLICT UPDATE）
        assert _cnt(us.db_path) == b0
        # 返回的 id 应存在于 usl_terms
        term = us.get_term(r["usl_term_id"])
        assert term is not None
        assert term["canonical"] == "MergeMe"


# 3. write_rejected + add_to_stoplist -------------------------------------
class TestWriteRejectedStoplist:
    def test_stoplist_three_synonyms(
        self, wb: WritebackService, cs: SQLiteCandidateStorage, us: SQLiteUslStorage
    ):
        c = _mc(cs, canon="BW", syn=["A", "B", "C"], status="gated")
        b0 = _cnt(us.db_path)
        r = wb.write_rejected(c["id"], reason_code="bad",
                              add_to_stoplist=True, executed_by="a")
        assert r["status"] == "ok"
        assert r["candidate_status"] == "stoplisted"
        sid = r["stoplist_usl_term_id"]
        assert sid
        assert _cnt(us.db_path) == b0 + 1
        st = us.get_term(sid)
        assert st is not None
        assert st["canonical"] == "BW"
        assert st["stoplist_flag"] is True
        assert st["synonyms"] == ["A", "B", "C"]
        upd = cs.get_candidate(c["id"]) or {}
        assert upd["status"] == "stoplisted"
        assert upd["stoplist_flag"] is True


# 4. Domain Auto-Create ----------------------------------------------------
class TestWriteApprovedDomainAutoCreate:
    def test_null_domain_creates_general(
        self, h: UslWritebackHandler, cs: SQLiteCandidateStorage, us: SQLiteUslStorage
    ):
        assert us.get_domain_by_code("GENERAL") is None
        c = _mc(cs, canon="ND", did=None)
        r = h.write_approved(c["id"], executed_by="u1")
        assert r["status"] == "ok"
        dom = us.get_domain_by_code("GENERAL")
        assert dom is not None and dom["code"] == "GENERAL"
        term = us.get_term(r["usl_term_id"])
        assert term is not None
        assert term["domain_id"] == dom["id"]

    def test_missing_did_reuses_general(
        self, h: UslWritebackHandler, cs: SQLiteCandidateStorage, us: SQLiteUslStorage
    ):
        us.save_domain({"code": "GENERAL", "display_name": "通用"})
        c = _mc(cs, canon="MD", did="NOT-EXIST")
        r = h.write_approved(c["id"], executed_by="u1")
        assert r["status"] == "ok"
        term = us.get_term(r["usl_term_id"])
        assert term is not None
        doms, _ = us.list_domains(page_size=999)
        assert sum(1 for d in doms if d["code"] == "GENERAL") == 1


# 5. trigger_manual_writeback 手动写回 ------------------------------------------------
class TestWritebackManualTrigger:
    def test_manual_trigger_writes_then_idempotent(
        self, wb: WritebackService, cs: SQLiteCandidateStorage, us: SQLiteUslStorage
    ):
        c = _mc(cs, canon="ManualT", status="approved")
        r1 = wb.trigger_manual_writeback(c["id"], executed_by="alice")
        assert r1["status"] == "ok"
        assert r1["trigger"] == "manual"
        assert r1["executed_by"] == "alice"
        assert r1["written_back"] is True
        uid = r1["usl_term_id"]
        assert uid and _cnt(us.db_path) >= 1

        r2 = wb.trigger_manual_writeback(c["id"], executed_by="bob")
        assert r2["status"] == "ok"
        assert r2["idempotent"] is True
        assert r2["written_back"] is False
        assert r2["usl_term_id"] == uid

    def test_manual_trigger_empty_cid_errors(self, wb: WritebackService):
        r = wb.trigger_manual_writeback("")
        assert r["status"] == "error"
        assert "不能为空" in str(r.get("message", ""))

    def test_manual_trigger_not_found_then_error(
        self, wb: WritebackService, us: SQLiteUslStorage, cs: SQLiteCandidateStorage
    ):
        r = wb.trigger_manual_writeback("NO-SUCH-ID-XYZ-" + uuid.uuid4().hex[:8])
        # get_status returns CANDIDATE_NOT_FOUND_404, trigger_manual -> write_approved -> impl
        # returns status=error message, no need for exact code
        assert isinstance(r, dict)
        assert r.get("status") == "error" or (r.get("degraded") is True and r.get("status") == "ok")


# 6. get_writeback_status 写回状态查询 ------------------------------------------------
class TestWritebackGetStatus:
    def test_status_approved_pending(self, wb: WritebackService, cs: SQLiteCandidateStorage):
        c = _mc(cs, canon="StatA", status="approved")
        r = wb.get_writeback_status(c["id"])
        assert r["status"] == "ok"
        assert r["candidate_id"] == c["id"]
        assert r["candidate_status"] == "approved"
        assert r["phase"] == "approved_pending"
        assert r["phase_ok"] is True

    def test_status_written_back_with_usl_term(
        self, wb: WritebackService, cs: SQLiteCandidateStorage, us: SQLiteUslStorage
    ):
        c = _mc(cs, canon="StatW", status="approved")
        w = wb.write_approved(c["id"], executed_by="u1")
        assert w["status"] == "ok" and w["usl_term_id"]
        r = wb.get_writeback_status(c["id"])
        assert r["status"] == "ok"
        assert r["phase"] == "written_back"
        assert r["phase_ok"] is True
        assert r["usl_term_id"] == w["usl_term_id"]
        assert r.get("executed_by") == "u1"
        assert r.get("written_at") is not None

    def test_status_in_pipeline_l2(self, wb: WritebackService, cs: SQLiteCandidateStorage):
        c = _mc(cs, canon="StatP", status="l2_done")
        r = wb.get_writeback_status(c["id"])
        assert r["status"] == "ok"
        assert r["phase"] == "in_pipeline"
        assert r["phase_ok"] is True

    def test_status_rejected(self, wb: WritebackService, cs: SQLiteCandidateStorage):
        c = _mc(cs, canon="StatR", status="rejected")
        r = wb.get_writeback_status(c["id"])
        assert r["status"] == "ok"
        assert r["phase"] == "rejected"
        assert r["phase_ok"] is True

    def test_status_not_found_returns_404_code(self, wb: WritebackService):
        r = wb.get_writeback_status("MISSING-CAND-" + uuid.uuid4().hex[:8])
        assert r["status"] == "error"
        assert r.get("code") == "CANDIDATE_NOT_FOUND_404"

    def test_status_empty_cid_errors(self, wb: WritebackService):
        r = wb.get_writeback_status("")
        assert r["status"] == "error"
