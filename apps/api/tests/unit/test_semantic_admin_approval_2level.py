"""Semantic Admin T1 - 2级审批 单元测试（AGENTS.md §C 严格规则，≤250 LOC）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

from odap.biz.semantic_admin.candidate_store.services._approval_helper import (
    score_to_tier,
)
from odap.biz.semantic_admin.candidate_store.services.candidate_service import (
    CandidateService,
)
from odap.biz.semantic_admin.candidate_store.storage.sqlite_candidate_storage import (
    SQLiteCandidateStorage,
)
from odap.biz.semantic_admin.usl_manager.storage.sqlite_usl_storage import (
    SQLiteUslStorage,
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
def svc(cs: SQLiteCandidateStorage, us: SQLiteUslStorage) -> CandidateService:
    wb = WritebackService(usl_storage=us, candidate_storage=cs)
    return CandidateService(storage=cs, writeback_service=wb)


def _c(storage: SQLiteCandidateStorage, *, canon: str = "T",
       score: float = 0.8, grade: str = "B",
       status: str = "gated") -> Dict[str, Any]:
    run = storage.create_pipeline_run(workspace_id="ws-1")
    c = storage.bulk_insert_candidates([{
        "id": str(uuid.uuid4()), "pipeline_run_id": run["id"],
        "canonical": canon, "semantic_type": "对象类型",
        "synonyms": ["A", "B"], "definition": "d",
        "confidence": score, "status": status, "provenance": {},
    }])[0]
    storage.save_quality_report({
        "candidate_id": c["id"], "overall_score": float(score), "grade": grade,
    })
    return c


# 1. Tier 边界值 -----------------------------------------------------------
class TestTierClassification:
    def test_high(self):
        assert score_to_tier(0.85) == "HIGH"
        assert score_to_tier(1.0) == "HIGH"

    def test_medium(self):
        assert score_to_tier(0.7) == "MEDIUM"
        assert score_to_tier(0.849) == "MEDIUM"

    def test_low(self):
        assert score_to_tier(0.5) == "LOW"
        assert score_to_tier(0.699) == "LOW"

    def test_very_low(self):
        assert score_to_tier(0.49) == "VERY_LOW"
        assert score_to_tier(0.3) == "VERY_LOW"

    def test_none_invalid_defaults_low(self):
        assert score_to_tier(None) == "LOW"
        assert score_to_tier("x") == "LOW"


# 2. L1 快速通道 HIGH/MEDIUM → 直接 writeback ------------------------------
class TestLevel1ApprovalFastpath:
    def test_high_fastpath(self, svc: CandidateService, cs: SQLiteCandidateStorage):
        c = _c(cs, canon="H", score=0.9, grade="A")
        r = svc.approve(c["id"], reviewer="a1", level=1)
        # 写回成功后 storage 里的真实状态就是 WRITTEN_BACK。曾经这里硬报
        # "approved"（override 出参），前端据此判断「是否还需写回」就被骗了。
        assert r.get("status") == "WRITTEN_BACK"
        assert r.get("fastpath") is True
        wb = r.get("writeback") or {}
        assert wb.get("status") == "ok" and wb.get("usl_term_id")
        upd = cs.get_candidate(c["id"]) or {}
        prov = upd.get("provenance") or {}
        assert prov.get("writeback_usl_term_id") == wb["usl_term_id"]


# 3. L1 LOW → admin_pending + L2 pending task ------------------------------
class TestLevel1ApprovalLowToAdminPending:
    def test_low_to_admin_pending(self, svc: CandidateService, cs: SQLiteCandidateStorage):
        c = _c(cs, canon="L", score=0.55, grade="C")
        svc.approve(c["id"], reviewer="a1", level=1)
        upd = cs.get_candidate(c["id"])
        assert upd is not None and upd["status"] == "ADMIN_PENDING"
        tasks = svc.list_approval_tasks(candidate_id=c["id"]).get("items", [])
        lv = {int(t["level"]): t["status"] for t in tasks}
        assert lv.get(1) == "approved"
        assert lv.get(2) == "pending"


# 4. L2 admin_pending → approved/written_back ------------------------------
class TestLevel2ApprovalFromAdminPending:
    def test_l2_finalizes(self, svc: CandidateService, cs: SQLiteCandidateStorage):
        c = _c(cs, canon="L2", score=0.55, grade="C")
        svc.approve(c["id"], reviewer="a1", level=1)
        r = svc.approve(c["id"], reviewer="admin1", level=2)
        assert r.get("status") == "WRITTEN_BACK"
        assert (r.get("writeback") or {}).get("usl_term_id")
        tasks = svc.list_approval_tasks(candidate_id=c["id"]).get("items", [])
        assert len(tasks) >= 2 and all(t["status"] == "approved" for t in tasks)
        prov = (cs.get_candidate(c["id"]) or {}).get("provenance") or {}
        assert "writeback_usl_term_id" in prov


# 5. VERY_LOW → auto reject ------------------------------------------------
class TestVeryLowAutoReject:
    def test_vl_auto_reject(self, svc: CandidateService, cs: SQLiteCandidateStorage):
        c = _c(cs, canon="VL", score=0.3, grade="D")
        svc.approve(c["id"], reviewer="a1", level=1)
        upd = cs.get_candidate(c["id"])
        assert upd is not None
        assert upd["status"] in ("REJECTED", "STOPLISTED")
        tasks = svc.list_approval_tasks(candidate_id=c["id"]).get("items", [])
        rej = [t for t in tasks if t["status"] == "rejected"]
        assert len(rej) >= 1


# 6. Reject + add_to_stoplist → stoplisted ----------------------------------
class TestRejectAddToStoplist:
    def test_reject_stoplist(self, svc: CandidateService, cs: SQLiteCandidateStorage):
        c = _c(cs, canon="S", score=0.6, grade="C")
        svc.reject(c["id"], reviewer="a1", level=1,
                   comment="bad", add_to_stoplist=True)
        upd = cs.get_candidate(c["id"])
        assert upd is not None
        assert upd["status"] == "STOPLISTED"
        assert upd["stoplist_flag"] is True
        logs = svc.list_audit_logs(candidate_id=c["id"]).get("items", [])
        stop_acts = [l["action"] for l in logs if "stoplist" in (l.get("action") or "").lower()]
        assert len(stop_acts) >= 1
        prov = upd.get("provenance") or {}
        assert prov.get("stoplist_added") is True


# 7. 写回失败必须显式失败（规则 14：不许无视被调方返回的错误状态）--------------
class TestWritebackFailureIsExplicit:
    """审批链拿到 wb={"status":"error"} 时绝不能报成功。

    曾经 run_fastpath_approve / run_level2_approve 只看 wb["usl_term_id"]，
    写回失败也照样把候选置成 approved 并返回成功 —— USL 里根本没有术语，
    界面却弹「审批通过」，反馈闭环据此认为语义已入库。
    """

    @staticmethod
    def _break_writeback(us: SQLiteUslStorage):
        from unittest.mock import patch
        return patch.object(us, "save_term",
                            side_effect=RuntimeError("Storage failure"))

    def test_fastpath_failure_returns_error(self, svc: CandidateService,
                                            cs: SQLiteCandidateStorage,
                                            us: SQLiteUslStorage):
        c = _c(cs, canon="WBF", score=0.9, grade="A")
        with self._break_writeback(us):
            r = svc.approve(c["id"], reviewer="a1", level=1)

        assert r.get("status") == "error"
        assert r.get("code") == "WRITEBACK_FAILED_502"
        # 审批决策已落库，候选停在 APPROVED：get_writeback_status 会如实报
        # phase=approved_pending，可用 trigger_manual_writeback 重试
        upd = cs.get_candidate(c["id"]) or {}
        assert upd["status"] == "APPROVED"
        assert not (upd.get("provenance") or {}).get("writeback_usl_term_id")
        acts = [x["action"] for x in
                svc.list_audit_logs(candidate_id=c["id"]).get("items", [])]
        assert "candidate_fastpath_writeback_failed" in acts

    def test_level2_failure_returns_error(self, svc: CandidateService,
                                          cs: SQLiteCandidateStorage,
                                          us: SQLiteUslStorage):
        c = _c(cs, canon="WBL2", score=0.55, grade="C")
        assert svc.approve(c["id"], reviewer="a1", level=1).get("status") == "ADMIN_PENDING"
        with self._break_writeback(us):
            r = svc.approve(c["id"], reviewer="admin1", level=2)

        assert r.get("status") == "error"
        assert r.get("code") == "WRITEBACK_FAILED_502"
        assert (cs.get_candidate(c["id"]) or {})["status"] == "APPROVED"
        acts = [x["action"] for x in
                svc.list_audit_logs(candidate_id=c["id"]).get("items", [])]
        assert "candidate_level2_writeback_failed" in acts

    def test_reject_stoplist_failure_leaves_candidate_untouched(
        self, svc: CandidateService, cs: SQLiteCandidateStorage, us: SQLiteUslStorage
    ):
        """驳回写回失败时不得留下「任务已驳回、候选状态没变」的对不上中间态。"""
        c = _c(cs, canon="WBR", score=0.6, grade="C")
        with self._break_writeback(us):
            r = svc.reject(c["id"], reviewer="a1", level=1,
                           comment="bad", add_to_stoplist=True)

        assert r.get("status") == "error"
        assert r.get("code") == "REJECT_WRITEBACK_FAILED_502"
        assert (cs.get_candidate(c["id"]) or {})["status"] == "QUALITY_GATED"
        assert svc.list_approval_tasks(candidate_id=c["id"]).get("items", []) == []
        acts = [x["action"] for x in
                svc.list_audit_logs(candidate_id=c["id"]).get("items", [])]
        assert "candidate_reject_writeback_failed" in acts
