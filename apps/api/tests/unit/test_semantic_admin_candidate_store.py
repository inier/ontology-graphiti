"""Semantic Admin Iter 2 — Candidate Store 存储层单元测试（AGENTS.md §C）。

- SQLite 用 tmp_path 真实 DB，严禁 MagicMock 模拟存储层
- 覆盖：
  1. 5 张表（pipeline_runs / ol_candidates / quality_reports / approval_tasks / audit_logs）CRUD
  2. 列表分页：get/delete 不存在分别返回 None / False
  3. JSON 字段：synonyms/near_synonyms/aliases/examples/provenance/risk_tags/suggestions roundtrip
  4. UNIQUE(candidate_id,level) on approval_tasks 幂等
  5. delete_candidate → 4 张子表（quality_reports/approval_tasks/audit_logs WHERE candidate_id）级联
  6. bulk_insert_candidates 事务：列表顺序一致
  7. update_pipeline_run_status：RUNNING → SUCCEEDED / FAILED；error_message 仅 FAILED 有效
  8. list_candidates 4 维过滤：pipeline_run_id / status / semantic_type / min_confidence
  9. list_approval_tasks：status + level + candidate_id 三维过滤
 10. list_audit_logs：run_id + candidate_id + action 三维过滤
 11. list_pipeline_runs：workspace_id + status 双过滤 + 分页
 12. save_quality_report 对同一 candidate 二次覆盖 upsert（UNIQUE(candidate_id)）
 13. get_candidate → synonyms JSON 反序列化后是 list，不是字符串
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

from odap.biz.semantic_admin.candidate_store.storage import (
    SQLiteCandidateStorage,
)


ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def storage(tmp_path: Path) -> SQLiteCandidateStorage:
    db = tmp_path / "candidates.db"
    return SQLiteCandidateStorage(db_path=str(db))


# =====================================================================
# Helpers / 工厂
# =====================================================================


def _run(ws: str = "ws-1", **kw: Any) -> Dict[str, Any]:
    d: Dict[str, Any] = dict(
        workspace_id=ws,
        ontology_id="ont-1",
        source_type="natural_language",
        source_ref="src-ref",
        triggered_by="tester",
        total_input_chars=100,
    )
    d.update(kw)
    return d


def _candidate(run_id: str, canon: str, **kw: Any) -> Dict[str, Any]:
    d: Dict[str, Any] = dict(
        id=str(uuid.uuid4()),
        pipeline_run_id=run_id,
        domain_id=None,
        canonical=canon,
        semantic_type="对象类型",
        synonyms=["角色"],
        near_synonyms=["武将"],
        aliases=["英雄"],
        stoplist_flag=False,
        confidence=0.75,
        definition=f"定义: {canon}",
        examples=["示例1", "示例2"],
        source_text=None,
        provenance={"step": "L3"},
        status="DRAFT",  # 新枚举：new → DRAFT
        created_at=_iso_now(),
        updated_at=_iso_now(),
    )
    d.update(kw)
    return d


# =====================================================================
# 1. pipeline_runs CRUD
# =====================================================================


class TestPipelineRuns:
    def test_create_and_get(self, storage: SQLiteCandidateStorage):
        payload = _run(ws="ws-a", triggered_by="alice")
        got = storage.create_pipeline_run(**payload)
        assert got["workspace_id"] == "ws-a"
        assert got["status"] == "DRAFT"  # 新枚举：pending → DRAFT
        assert ISO_RE.match(got["created_at"])

        r = storage.get_pipeline_run(got["id"])
        assert r is not None
        assert r["triggered_by"] == "alice"
        assert r["total_input_chars"] == 100
        assert r["total_output_candidates"] in (None, 0)

    def test_get_nonexistent(self, storage: SQLiteCandidateStorage):
        assert storage.get_pipeline_run("not-exist") is None

    def test_update_status_running_to_succeeded(self, storage: SQLiteCandidateStorage):
        r = storage.create_pipeline_run(**_run())
        ok = storage.update_pipeline_run_status(r["id"], status="RUNNING", progress=30)
        assert ok is True
        assert storage.get_pipeline_run(r["id"])["progress"] == 30
        assert storage.get_pipeline_run(r["id"])["status"] == "RUNNING"

        ok = storage.update_pipeline_run_status(
            r["id"], status="COMPLETED", progress=100, total_output_candidates=42
        )
        assert ok is True
        got = storage.get_pipeline_run(r["id"])
        assert got["status"] == "COMPLETED"
        assert got["total_output_candidates"] == 42
        assert got["finished_at"] is not None and ISO_RE.match(got["finished_at"])

    def test_update_status_failed_stores_error(self, storage: SQLiteCandidateStorage):
        r = storage.create_pipeline_run(**_run())
        storage.update_pipeline_run_status(
            r["id"], status="FAILED", error_message="OOM killed"
        )
        got = storage.get_pipeline_run(r["id"])
        assert got["status"] == "FAILED"
        assert got["error_message"] == "OOM killed"
        assert got["finished_at"] is not None

    def test_update_nonexistent_returns_false(self, storage: SQLiteCandidateStorage):
        assert storage.update_pipeline_run_status("no-such", status="COMPLETED") is False

    def test_list_runs_filter_workspace_and_status(self, storage: SQLiteCandidateStorage):
        a = storage.create_pipeline_run(**_run(ws="ws-1", status="COMPLETED"))
        b = storage.create_pipeline_run(**_run(ws="ws-1", status="FAILED"))
        c = storage.create_pipeline_run(**_run(ws="ws-2", status="COMPLETED"))
        pg = storage.list_pipeline_runs(workspace_id="ws-1")
        assert pg["total"] == 2
        ids = {x["id"] for x in pg["items"]}
        assert ids == {a["id"], b["id"]}

        pg = storage.list_pipeline_runs(status="COMPLETED")
        assert pg["total"] == 2
        ids = {x["id"] for x in pg["items"]}
        assert ids == {a["id"], c["id"]}

        pg = storage.list_pipeline_runs(workspace_id="ws-1", status="FAILED")
        assert pg["total"] == 1
        assert pg["items"][0]["id"] == b["id"]

    def test_list_runs_pagination(self, storage: SQLiteCandidateStorage):
        for i in range(7):
            storage.create_pipeline_run(**_run(ws="ws-7"))
        pg = storage.list_pipeline_runs(workspace_id="ws-7", page=2, page_size=3)
        assert pg["total"] == 7
        assert len(pg["items"]) == 3
        pg = storage.list_pipeline_runs(workspace_id="ws-7", page=3, page_size=3)
        assert len(pg["items"]) == 1
        pg = storage.list_pipeline_runs(workspace_id="ws-7", page=4, page_size=3)
        assert pg["total"] == 7
        assert len(pg["items"]) == 0


# =====================================================================
# 2. ol_candidates CRUD + 过滤器 + 级联
# =====================================================================


class TestCandidates:
    def test_bulk_insert_and_roundtrip_json(self, storage: SQLiteCandidateStorage):
        r = storage.create_pipeline_run(**_run())
        c1 = _candidate(r["id"], "人物", synonyms=["角色", "人"], examples=["e1", "e2", "e3"],
                        provenance={"a": "b"})
        c2 = _candidate(r["id"], "势力", semantic_type="关系类型", confidence=0.3, status="QUALITY_GATED",
                        near_synonyms=["盟友", "联盟"])
        out = storage.bulk_insert_candidates([c1, c2])
        assert len(out) == 2
        g1 = storage.get_candidate(out[0]["id"])
        assert g1 is not None
        assert g1["canonical"] == "人物"
        assert isinstance(g1["synonyms"], list) and g1["synonyms"] == ["角色", "人"]
        assert isinstance(g1["near_synonyms"], list) and g1["near_synonyms"] == ["武将"]
        assert isinstance(g1["examples"], list) and len(g1["examples"]) == 3
        assert isinstance(g1["provenance"], dict) and g1["provenance"]["a"] == "b"
        assert g1["status"] == "new"  # DRAFT(存储层) → new(legacy)
        assert g1["stoplist_flag"] is False
        assert 0.749 < g1["confidence"] < 0.751

        g2 = storage.get_candidate(out[1]["id"])
        assert g2["semantic_type"] == "关系类型"
        assert g2["status"] == "gated"  # QUALITY_GATED → gated(legacy)
        assert g2["confidence"] == pytest.approx(0.3, 1e-3)
        assert g2["near_synonyms"] == ["盟友", "联盟"]

    def test_get_candidate_nonexistent(self, storage: SQLiteCandidateStorage):
        assert storage.get_candidate("no") is None

    def test_update_candidate_status(self, storage: SQLiteCandidateStorage):
        r = storage.create_pipeline_run(**_run())
        c, = storage.bulk_insert_candidates([_candidate(r["id"], "A")])
        assert storage.update_candidate_status(c["id"], "APPROVED") is True
        got = storage.get_candidate(c["id"])
        assert got["status"] == "approved"  # APPROVED → approved(legacy)
        assert got["updated_at"] >= c["updated_at"]
        assert storage.update_candidate_status("nope", "APPROVED") is False

    def test_list_candidates_four_filters(self, storage: SQLiteCandidateStorage):
        r1 = storage.create_pipeline_run(**_run(ws="w1"))
        r2 = storage.create_pipeline_run(**_run(ws="w2"))
        storage.bulk_insert_candidates([
            _candidate(r1["id"], "A", semantic_type="对象类型", status="QUALITY_GATED", confidence=0.8),
            _candidate(r1["id"], "B", semantic_type="关系类型", status="APPROVED", confidence=0.5),
            _candidate(r2["id"], "C", semantic_type="过程类型", status="QUALITY_GATED", confidence=0.2),
            _candidate(r2["id"], "D", semantic_type="对象类型", status="DRAFT", confidence=0.9),
        ])
        _, total = storage.list_candidates(pipeline_run_id=r1["id"])["items"], storage.list_candidates(pipeline_run_id=r1["id"])["total"]
        assert total == 2
        pg = storage.list_candidates(status="QUALITY_GATED")
        assert pg["total"] == 2 and {x["canonical"] for x in pg["items"]} == {"A", "C"}
        _, total = storage.list_candidates(semantic_type="对象类型")["items"], storage.list_candidates(semantic_type="对象类型")["total"]
        assert total == 2
        pg = storage.list_candidates(min_confidence=0.85)
        assert pg["total"] == 1
        assert pg["items"][0]["canonical"] == "D"
        pg = storage.list_candidates(
            pipeline_run_id=r2["id"], status="QUALITY_GATED", semantic_type="过程类型"
        )
        assert pg["total"] == 1
        assert pg["items"][0]["canonical"] == "C"

    def test_list_candidates_pagination(self, storage: SQLiteCandidateStorage):
        r = storage.create_pipeline_run(**_run())
        rows = [_candidate(r["id"], f"T{i}", confidence=0.5) for i in range(11)]
        storage.bulk_insert_candidates(rows)
        pg = storage.list_candidates(pipeline_run_id=r["id"], page=2, page_size=5)
        assert pg["total"] == 11
        assert len(pg["items"]) == 5
        pg = storage.list_candidates(pipeline_run_id=r["id"], page=3, page_size=5)
        assert len(pg["items"]) == 1

    def test_delete_cascade(self, storage: SQLiteCandidateStorage):
        r = storage.create_pipeline_run(**_run())
        c, = storage.bulk_insert_candidates([_candidate(r["id"], "A")])
        cid = c["id"]
        storage.save_quality_report({"candidate_id": cid, "overall_score": 0.8, "grade": "A"})
        storage.create_approval_task(candidate_id=cid, level=1)
        storage.append_audit_log(action="candidate_made", actor="u", candidate_id=cid)
        assert storage.get_quality_report_by_candidate(cid) is not None
        at = storage.list_approval_tasks(candidate_id=cid)
        assert at["total"] == 1
        al = storage.list_audit_logs(candidate_id=cid)
        assert al["total"] == 1
        assert storage.delete_candidate(cid) is True
        assert storage.get_candidate(cid) is None
        assert storage.get_quality_report_by_candidate(cid) is None
        assert storage.list_approval_tasks(candidate_id=cid)["total"] == 0
        assert storage.list_audit_logs(candidate_id=cid)["total"] == 0
        assert storage.delete_candidate(cid) is False


# =====================================================================
# 3. quality_reports (UNIQUE candidate_id → UPSERT)
# =====================================================================


class TestQualityReports:
    def test_save_and_get_and_upsert(self, storage: SQLiteCandidateStorage):
        r = storage.create_pipeline_run(**_run())
        c, = storage.bulk_insert_candidates([_candidate(r["id"], "A")])
        storage.save_quality_report({
            "candidate_id": c["id"], "overall_score": 0.5, "novelty_score": 0.3,
            "completeness_score": 0.1, "orthogonality_score": 0.9, "consistency_score": 0.2,
            "grade": "C", "risk_tags": ["缺定义"], "suggestions": ["补充definition"],
        })
        qr = storage.get_quality_report_by_candidate(c["id"])
        assert qr is not None
        assert qr["grade"] == "C"
        assert qr["risk_tags"] == ["缺定义"]
        assert qr["overall_score"] == pytest.approx(0.5)
        storage.save_quality_report({
            "candidate_id": c["id"], "overall_score": 0.95, "novelty_score": 0.9,
            "completeness_score": 0.9, "orthogonality_score": 1.0, "consistency_score": 0.9,
            "grade": "A", "risk_tags": [], "suggestions": [],
        })
        qr = storage.get_quality_report_by_candidate(c["id"])
        assert qr["grade"] == "A"
        assert qr["overall_score"] == pytest.approx(0.95)
        assert qr["risk_tags"] == []


# =====================================================================
# 4. approval_tasks (UNIQUE candidate_id+level)
# =====================================================================


class TestApprovalTasks:
    def test_create_unique_upsert_and_list_filters(self, storage: SQLiteCandidateStorage):
        r = storage.create_pipeline_run(**_run())
        c1, c2 = storage.bulk_insert_candidates([
            _candidate(r["id"], "A"), _candidate(r["id"], "B"),
        ])
        t1 = storage.create_approval_task(candidate_id=c1["id"], level=1)
        assert t1["status"] == "pending"
        t1_dup = storage.create_approval_task(candidate_id=c1["id"], level=1)
        assert t1_dup["id"] == t1["id"]

        storage.create_approval_task(candidate_id=c1["id"], level=2)
        storage.create_approval_task(candidate_id=c2["id"], level=1)
        storage.update_approval_task(t1["id"], status="approved", reviewer="alice", comment="ok")
        got = storage.get_approval_task(t1["id"])
        assert got["status"] == "approved"
        assert got["reviewer"] == "alice"
        assert got["comment"] == "ok"
        assert got["approved_at"] is not None and ISO_RE.match(got["approved_at"])

        at = storage.list_approval_tasks(candidate_id=c1["id"])
        assert at["total"] == 2
        at = storage.list_approval_tasks(status="approved")
        assert at["total"] == 1
        at = storage.list_approval_tasks(level=2)
        assert at["total"] == 1
        at = storage.list_approval_tasks(status="pending", level=1)
        assert at["total"] == 1


# =====================================================================
# 5. audit_logs 三维过滤
# =====================================================================


class TestAuditLogs:
    def test_append_and_list(self, storage: SQLiteCandidateStorage):
        r1 = storage.create_pipeline_run(**_run(ws="w1"))
        r2 = storage.create_pipeline_run(**_run(ws="w2"))
        c, = storage.bulk_insert_candidates([_candidate(r1["id"], "X")])
        storage.append_audit_log(action="pipeline_started", actor="u1", pipeline_run_id=r1["id"], payload={"x": 1})
        storage.append_audit_log(action="candidate_approved", actor="u2", candidate_id=c["id"], payload={})
        storage.append_audit_log(action="pipeline_started", actor="u1", pipeline_run_id=r2["id"], payload={})
        storage.append_audit_log(action="candidate_deleted", actor="u3", payload={})
        al = storage.list_audit_logs(pipeline_run_id=r1["id"])
        assert al["total"] == 2
        al = storage.list_audit_logs(candidate_id=c["id"])
        assert al["total"] == 1
        al = storage.list_audit_logs(action="pipeline_started")
        assert al["total"] == 2
        al = storage.list_audit_logs(pipeline_run_id=r2["id"], action="pipeline_started")
        assert al["total"] == 1
