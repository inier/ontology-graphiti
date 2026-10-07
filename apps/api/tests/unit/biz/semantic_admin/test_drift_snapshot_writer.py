import pytest
from odap.biz.semantic_admin.drift_scan.services import snapshot_writer
from odap.biz.semantic_admin.drift_scan.storage import SQLiteDriftStorage


@pytest.fixture
def store(tmp_path, monkeypatch):
    s = SQLiteDriftStorage(db_path=str(tmp_path / "drift.db"))
    monkeypatch.setattr(snapshot_writer, "_get_storage", lambda: s)
    return s


def test_record_indicator_snapshot(store):
    snapshot_writer.record_indicator_snapshot(
        indicator_id="ind1", ontology_id="o1",
        definition={"formula": "a/b"}, change_op="create")
    rows = store.list_indicator_snapshots("ind1")
    assert len(rows) == 1
    assert rows[0]["definition_json"]["formula"] == "a/b"


def test_record_term_history_update_before_after(store):
    snapshot_writer.record_term_history(
        term_id="t1", domain_id="d1", op="update",
        before={"canonical": "旧"}, after={"canonical": "新"})
    rows = store.list_term_history("t1")
    assert rows[0]["before_json"]["canonical"] == "旧"
    assert rows[0]["after_json"]["canonical"] == "新"


def test_hook_failure_swallowed_and_counted(store, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(snapshot_writer, "_get_storage", boom)
    before = snapshot_writer.get_hook_failures()
    snapshot_writer.record_indicator_snapshot(   # 不 raise
        indicator_id="x", ontology_id="o", definition={}, change_op="create")
    assert snapshot_writer.get_hook_failures() == before + 1
