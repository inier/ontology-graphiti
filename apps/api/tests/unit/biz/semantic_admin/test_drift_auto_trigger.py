import asyncio
import pytest
from odap.biz.semantic_admin.drift_scan.services import DriftService
from odap.biz.semantic_admin.drift_scan.storage import SQLiteDriftStorage


@pytest.fixture
def store(tmp_path):
    return SQLiteDriftStorage(db_path=str(tmp_path / "drift.db"))


def _seed_terms(store, monkeypatch):
    # 注入一对 fork 术语 + 一条 indicator 快照变更
    terms = [
        {"id": "t1", "canonical": "势力", "domain_id": "d1", "semantic_type": "对象类型",
         "synonyms": ["阵营"], "near_synonyms": [], "aliases": [], "stoplist_flag": False},
        {"id": "t2", "canonical": "军团", "domain_id": "d1", "semantic_type": "对象类型",
         "synonyms": ["阵营"], "near_synonyms": [], "aliases": [], "stoplist_flag": False},
    ]
    monkeypatch.setattr(DriftService, "_load_terms", lambda self, scope: terms)
    monkeypatch.setattr(DriftService, "_load_version_pairs", lambda self, oid: [])
    store.append_indicator_snapshot({"indicator_id": "i1", "ontology_id": "o1",
        "definition_json": {"formula": "a/b"}, "change_op": "create",
        "captured_at": "2026-01-01T00:00:00"})
    store.append_indicator_snapshot({"indicator_id": "i1", "ontology_id": "o1",
        "definition_json": {"formula": "a/c"}, "change_op": "update",
        "captured_at": "2026-02-01T00:00:00"})


def test_run_scan_produces_expected_findings_exactly(store, monkeypatch):
    _seed_terms(store, monkeypatch)
    svc = DriftService(storage=store)
    r = svc.run_scan(scope={"domain_id": "d1"}, trigger="manual", ontology_id="o1")
    assert r["status"] == "ok"
    rep = store.get_report(r["report_id"])
    assert rep["status"] == "ok"
    # 恰好 1 fork + 1 indicator 演进，不多不少
    assert rep["counts_json"]["forks"] == 1
    assert rep["counts_json"]["evolutions"] == 1
    assert rep["source_errors_json"] == {}


def test_run_scan_records_source_error_on_partial_failure(store, monkeypatch):
    _seed_terms(store, monkeypatch)
    def boom(self, oid):
        raise RuntimeError("version store down")
    monkeypatch.setattr(DriftService, "_load_version_pairs", boom)
    svc = DriftService(storage=store)
    r = svc.run_scan(scope={}, trigger="manual", ontology_id="o1")
    rep = store.get_report(r["report_id"])
    assert rep["status"] == "ok"                       # ≥1 源成功
    assert "version_snapshot" in rep["source_errors_json"]


def test_on_ontology_committed_schedules_scan(store, monkeypatch):
    _seed_terms(store, monkeypatch)
    svc = DriftService(storage=store)
    monkeypatch.setattr(DriftService, "_instance_for_hook", lambda oid: svc, raising=False)
    svc.on_ontology_committed("o1")
    # 让 create_task 有机会跑完
    loop = asyncio.new_event_loop()
    loop.run_until_complete(asyncio.sleep(0.05))
    loop.close()
    import time
    time.sleep(0.1)
    items, total = store.list_reports(trigger="commit")
    assert total >= 1


# --- Fix round 1: coverage for the REAL `_load_version_pairs` body (Rule 14.6) ---
# The 3 tests above monkeypatch `_load_version_pairs` away, so its real body
# (filter is_stable -> sort created_at ASC -> pair adjacent -> parse snapshots ->
# raise RuntimeError on error) was never asserted. These tests drive the REAL
# body by stubbing ONLY its collaborator OntologyService.list_schema_versions.
# OntologyService is imported function-locally (mirrors drift_service's own
# circular-import-avoidance pattern and isolates import risk from the tests above).


def test_load_version_pairs_filters_sorts_and_pairs(store, monkeypatch):
    from odap.biz.core.ontology.ontology_api.services.ontology_service import (
        OntologyService,
    )
    v2 = {"version_id": "v2", "is_stable": True,
          "created_at": "2026-02-01T00:00:00",
          "schema_snapshot": {"object_types": [
              {"type_id": "t1", "name": "A", "name_en": "x"}]}}
    v3 = {"version_id": "v3", "is_stable": False,
          "created_at": "2026-03-01T00:00:00",
          "schema_snapshot": {"object_types": [
              {"type_id": "t1", "name": "A", "name_en": "unstable"}]}}
    v1 = {"version_id": "v1", "is_stable": True,
          "created_at": "2026-01-01T00:00:00",
          # JSON STRING snapshot -> _load_version_pairs must json.loads it
          "schema_snapshot": '{"object_types":[{"type_id":"t1","name":"A"}]}'}
    # deliberately OUT OF ORDER (DESC-ish) + MIXED stability
    monkeypatch.setattr(
        OntologyService, "list_schema_versions",
        lambda self, oid: {"versions": [v2, v3, v1], "count": 3})
    pairs = DriftService(storage=store)._load_version_pairs("o1")
    # exactly one adjacent pair from the two STABLE versions
    assert len(pairs) == 1
    snap_a, snap_b, ver_a, ver_b = pairs[0]
    # sorted ASCENDING by created_at -> v1 (Jan) before v2 (Feb)
    assert ver_a == "v1"
    assert ver_b == "v2"
    # v1 snapshot was a JSON string -> parsed to dict
    assert snap_a == {"object_types": [{"type_id": "t1", "name": "A"}]}
    # v2 snapshot already a dict -> passed through unchanged
    assert snap_b == {"object_types": [
        {"type_id": "t1", "name": "A", "name_en": "x"}]}
    # the NON-stable v3 is excluded entirely (appears nowhere)
    assert all("v3" not in (p[2], p[3]) for p in pairs)


def test_load_version_pairs_raises_on_error(store, monkeypatch):
    from odap.biz.core.ontology.ontology_api.services.ontology_service import (
        OntologyService,
    )
    monkeypatch.setattr(
        OntologyService, "list_schema_versions",
        lambda self, oid: {"status": "error", "message": "boom"})
    # explicit failure -> RuntimeError (run_scan records it as a source_error,
    # it does NOT silently return [])
    with pytest.raises(RuntimeError):
        DriftService(storage=store)._load_version_pairs("o1")


def test_run_scan_version_source_end_to_end(store, monkeypatch):
    from odap.biz.core.ontology.ontology_api.services.ontology_service import (
        OntologyService,
    )
    v1 = {"version_id": "v1", "is_stable": True,
          "created_at": "2026-01-01T00:00:00",
          "schema_snapshot": {"object_types": [
              {"type_id": "t1", "name": "A", "name_en": "force"}]}}
    v2 = {"version_id": "v2", "is_stable": True,
          "created_at": "2026-02-01T00:00:00",
          "schema_snapshot": {"object_types": [
              {"type_id": "t1", "name": "A", "name_en": "faction"}]}}
    monkeypatch.setattr(
        OntologyService, "list_schema_versions",
        lambda self, oid: {"versions": [v1, v2], "count": 2})
    # fork source contributes nothing; we are testing the VERSION source.
    # _load_terms is a separate collaborator.
    monkeypatch.setattr(DriftService, "_load_terms", lambda self, scope: [])
    svc = DriftService(storage=store)
    r = svc.run_scan(scope={}, trigger="manual", ontology_id="o1")
    assert r["status"] == "ok"
    rep = store.get_report(r["report_id"])
    assert rep["counts_json"]["evolutions"] >= 1
    assert "version_snapshot" not in rep["source_errors_json"]
    findings = store.list_findings(r["report_id"])
    assert any(f["source"] == "version_snapshot" and f["field"] == "name_en"
               for f in findings)
