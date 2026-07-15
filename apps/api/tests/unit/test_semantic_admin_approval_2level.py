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
        assert r.get("status") == "approved"
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
        assert upd is not None and upd["status"] == "admin_pending"
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
        assert r.get("status") == "approved"
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
        assert upd["status"] in ("rejected", "stoplisted")
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
        assert upd["status"] == "stoplisted"
        assert upd["stoplist_flag"] is True
        logs = svc.list_audit_logs(candidate_id=c["id"]).get("items", [])
        stop_acts = [l["action"] for l in logs if "stoplist" in (l.get("action") or "").lower()]
        assert len(stop_acts) >= 1
        prov = upd.get("provenance") or {}
        assert prov.get("stoplist_added") is True
