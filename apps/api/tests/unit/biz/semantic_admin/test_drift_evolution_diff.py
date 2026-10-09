from odap.biz.semantic_admin.drift_scan.services.scanners import (
    diff_version_snapshots, diff_indicator_snapshots, diff_term_history,
)
from odap.biz.semantic_admin.drift_scan.models import EvolutionSource


_CATEGORIES = ("object_types", "link_types", "action_types", "process_types",
               "rule_types", "function_types", "indicator_types")


def _snap(**overrides):
    """构造真实 schema_snapshot 结构（_build_schema_snapshot 的 7 大类型分类）。"""
    base = {c: [] for c in _CATEGORIES}
    base.update(overrides)
    return base


def test_version_diff_field_change():
    a = _snap(object_types=[{"type_id": "o1", "name": "势力", "name_en": "force"}])
    b = _snap(object_types=[{"type_id": "o1", "name": "势力", "name_en": "faction"}])
    fs = diff_version_snapshots(a, b, version_a="v1", version_b="v2")
    assert len(fs) == 1
    assert fs[0]["field"] == "name_en"
    assert fs[0]["old_value_json"] == "force"
    assert fs[0]["new_value_json"] == "faction"
    assert fs[0]["subject"] == "o1"
    assert fs[0]["subject_label"] == "势力"
    assert fs[0]["version_ref_json"] == {"version_a": "v1", "version_b": "v2"}
    assert fs[0]["source"] == EvolutionSource.VERSION_SNAPSHOT.value


def test_version_diff_added_removed_type():
    a = _snap(object_types=[{"type_id": "o1", "name": "势力"}])
    b = _snap(object_types=[{"type_id": "o2", "name": "人物"}])
    fs = diff_version_snapshots(a, b, version_a="v1", version_b="v2")
    fields = {f["field"] for f in fs}
    assert "__removed__" in fields and "__added__" in fields
    added = next(f for f in fs if f["field"] == "__added__")
    assert added["subject"] == "o2"
    assert added["new_value_json"] == {"type_id": "o2", "name": "人物"}
    assert added["old_value_json"] is None
    removed = next(f for f in fs if f["field"] == "__removed__")
    assert removed["subject"] == "o1"
    assert removed["old_value_json"] == {"type_id": "o1", "name": "势力"}
    assert removed["new_value_json"] is None


def test_version_diff_link_types_uses_link_id_pk():
    # link_types 的主键是 link_id（与 ontology_service.diff_schema_versions 对齐）
    a = _snap(link_types=[{"link_id": "l1", "name": "隶属于"}])
    b = _snap(link_types=[{"link_id": "l1", "name": "归属于"}])
    fs = diff_version_snapshots(a, b, version_a="v1", version_b="v2")
    assert len(fs) == 1
    assert fs[0]["subject"] == "l1"
    assert fs[0]["field"] == "name"
    assert fs[0]["old_value_json"] == "隶属于"
    assert fs[0]["new_value_json"] == "归属于"


def test_version_diff_ignores_timestamp_fields():
    a = _snap(object_types=[{"type_id": "o1", "name": "势力",
                             "created_at": "2026-01-01", "updated_at": "2026-01-02"}])
    b = _snap(object_types=[{"type_id": "o1", "name": "势力",
                             "created_at": "2026-01-01", "updated_at": "2026-03-04"}])
    assert diff_version_snapshots(a, b, version_a="v1", version_b="v2") == []


def test_version_diff_no_change_is_empty():
    a = _snap(object_types=[{"type_id": "o1", "name": "势力"}])
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
