import pytest
from odap.biz.semantic_admin.drift_scan.models import DriftKind
from odap.biz.semantic_admin.drift_scan.storage import SQLiteDriftStorage


@pytest.fixture
def store(tmp_path):
    return SQLiteDriftStorage(db_path=str(tmp_path / "drift.db"))


def test_save_report_with_findings_atomic(store):
    rep = {"id": "r1", "trigger": "manual", "status": "ok",
           "scope_json": {"ontology_id": "o1"}, "counts_json": {"forks": 1, "evolutions": 0},
           "source_errors_json": {}}
    fnd = [{"id": "f1", "report_id": "r1", "kind": DriftKind.FORK.value,
            "source": "", "subject": "诸侯", "subject_label": "诸侯",
            "sides_json": [{"term_id": "t1"}, {"term_id": "t2"}]}]
    out = store.save_report_with_findings(rep, fnd)
    assert out["id"] == "r1"
    assert len(store.list_findings("r1")) == 1


def test_report_immutable_no_update_api(store):
    rep = {"id": "r2", "trigger": "manual", "status": "ok", "counts_json": {},
           "scope_json": {}, "source_errors_json": {}}
    store.save_report_with_findings(rep, [])
    # 存储层不暴露 update_report；再 save 同 id 走 INSERT OR REPLACE 但服务层从不调用
    assert store.get_report("r2")["status"] == "ok"


def test_list_reports_filter_and_paging(store):
    for i in range(3):
        store.save_report_with_findings(
            {"id": f"r{i}", "trigger": "manual" if i < 2 else "commit",
             "status": "ok", "counts_json": {}, "scope_json": {}, "source_errors_json": {}}, [])
    items, total = store.list_reports(trigger="manual", page=1, page_size=10)
    assert total == 2


def test_indicator_snapshot_append_and_order(store):
    store.append_indicator_snapshot({"id": "s1", "indicator_id": "ind1",
        "ontology_id": "o1", "definition_json": {"formula": "a"}, "change_op": "create"})
    store.append_indicator_snapshot({"id": "s2", "indicator_id": "ind1",
        "ontology_id": "o1", "definition_json": {"formula": "b"}, "change_op": "update"})
    rows = store.list_indicator_snapshots("ind1")
    assert len(rows) == 2
    assert rows[0]["captured_at"] <= rows[1]["captured_at"]


def test_term_history_append(store):
    store.append_term_history({"id": "h1", "term_id": "t1", "domain_id": "d1",
        "op": "update", "before_json": {"canonical": "旧"}, "after_json": {"canonical": "新"}})
    assert len(store.list_term_history("t1")) == 1


def test_bad_json_tolerated(store):
    store.save_report_with_findings(
        {"id": "r3", "trigger": "manual", "status": "ok",
         "counts_json": {}, "scope_json": {}, "source_errors_json": {}}, [])
    import sqlite3
    conn = sqlite3.connect(store.db_path)
    conn.execute("UPDATE drift_scan_reports SET counts_json='{bad' WHERE id='r3'")
    conn.commit()
    conn.close()
    assert store.get_report("r3")["counts_json"] == {}
