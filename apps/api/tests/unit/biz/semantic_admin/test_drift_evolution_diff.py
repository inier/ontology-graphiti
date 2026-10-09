from odap.biz.semantic_admin.drift_scan.services.scanners import (
    diff_version_snapshots, diff_indicator_snapshots, diff_term_history,
)
from odap.biz.semantic_admin.drift_scan.models import EvolutionSource


def test_version_diff_field_change():
    a = {"entities": [{"entity_id": "e1", "name": "势力", "name_en": "force"}],
         "relations": [], "rules": [], "constraints": []}
    b = {"entities": [{"entity_id": "e1", "name": "势力", "name_en": "faction"}],
         "relations": [], "rules": [], "constraints": []}
    fs = diff_version_snapshots(a, b, version_a="v1", version_b="v2")
    assert len(fs) == 1
    assert fs[0]["field"] == "name_en"
    assert fs[0]["old_value_json"] == "force"
    assert fs[0]["new_value_json"] == "faction"
    assert fs[0]["version_ref_json"] == {"version_a": "v1", "version_b": "v2"}
    assert fs[0]["source"] == EvolutionSource.VERSION_SNAPSHOT.value


def test_version_diff_added_removed_entity():
    a = {"entities": [{"entity_id": "e1", "name": "势力"}], "relations": [], "rules": [], "constraints": []}
    b = {"entities": [{"entity_id": "e2", "name": "人物"}], "relations": [], "rules": [], "constraints": []}
    fs = diff_version_snapshots(a, b, version_a="v1", version_b="v2")
    fields = {f["field"] for f in fs}
    assert "__removed__" in fields and "__added__" in fields


def test_version_diff_no_change_is_empty():
    a = {"entities": [{"entity_id": "e1", "name": "势力"}], "relations": [], "rules": [], "constraints": []}
    assert diff_version_snapshots(a, a, version_a="v1", version_b="v2") == []


def test_indicator_diff_across_snapshots():
    rows = [
        {"indicator_id": "i1", "captured_at": "2026-01-01T00:00:00",
         "definition_json": {"formula": "a/b"}, "change_op": "create"},
        {"indicator_id": "i1", "captured_at": "2026-02-01T00:00:00",
         "definition_json": {"formula": "a/c"}, "change_op": "update"},
    ]
    fs = diff_indicator_snapshots(rows)
    assert len(fs) == 1
    assert fs[0]["field"] == "formula"
    assert fs[0]["old_value_json"] == "a/b" and fs[0]["new_value_json"] == "a/c"
    assert fs[0]["source"] == EvolutionSource.INDICATOR_CALIBER.value
    assert fs[0]["version_ref_json"] == {"prev_at": "2026-01-01T00:00:00",
                                         "cur_at": "2026-02-01T00:00:00"}


def test_indicator_single_snapshot_no_diff():
    rows = [{"indicator_id": "i1", "captured_at": "2026-01-01T00:00:00",
             "definition_json": {"formula": "a"}, "change_op": "create"}]
    assert diff_indicator_snapshots(rows) == []


def test_term_history_diff():
    rows = [
        {"term_id": "t1", "at": "2026-01-01T00:00:00", "op": "create",
         "before_json": None, "after_json": {"canonical": "势力", "synonyms": []}},
        {"term_id": "t1", "at": "2026-02-01T00:00:00", "op": "update",
         "before_json": {"canonical": "势力", "synonyms": []},
         "after_json": {"canonical": "势力", "synonyms": ["阵营"]}},
    ]
    fs = diff_term_history(rows)
    assert len(fs) == 1
    assert fs[0]["field"] == "synonyms"
    assert fs[0]["source"] == EvolutionSource.USL_TERM.value
