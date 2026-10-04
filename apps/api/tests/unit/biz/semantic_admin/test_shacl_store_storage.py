"""ADR-085 S4a-1：SHACL 治理持久化存储。

两张表（仿 candidate_store 约定，规则 8 每次 connect/close）：
  · sa_shacl_shape    — 版本键控形状派生缓存（ADR-077 裁决 1 操作化，非新事实源）
  · sa_derived_axiom  — L6 AxiomDeriver 公理持久化（停止丢弃，喂形状生成/G2.2）

验收：
  F7-a：形状按 (ontology_version_id, constraint_revision, target_type) 缓存命中；
        同键 upsert 替换；版本/约束 bump 后并存（失效键生效）。
  F7-c：L6 公理可持久化并读回（按 run 整体替换，幂等）。

规则 9：真实 tmp_path SQLite，禁 MagicMock。
"""

from __future__ import annotations

import pytest

from odap.biz.semantic_admin.shacl_store.storage import (
    SQLiteShaclStorage,
    Storage,
)


@pytest.fixture
def store(tmp_path):
    return SQLiteShaclStorage(db_path=str(tmp_path / "shacl.db"))


def _shape(**overrides):
    base = {
        "workspace_id": "ws-1",
        "ontology_version_id": "ov-1",
        "constraint_revision": "rev-1",
        "target_type": "库存周转率",
        "shape_ttl": "@prefix sh: <http://www.w3.org/ns/shacl#> .\n[] a sh:NodeShape .",
        "source_type_defs": [{"name": "库存周转率", "properties": []}],
        "source_axioms": [{"axiom_type": "sub_class_of", "subject": "A", "object": "B"}],
        "checksum": "abc123",
    }
    base.update(overrides)
    return base


def _axiom(**overrides):
    base = {
        "axiom_type": "sub_class_of",
        "subject": "库存周转率",
        "object": "指标",
        "confidence": 0.9,
        "source": "hierarchy_direct",
        "proof": {"direct_edge": True},
    }
    base.update(overrides)
    return base


class TestAliasExport:
    def test_storage_alias_points_to_impl(self):
        assert Storage is SQLiteShaclStorage


class TestShapeCache:
    def test_save_and_get_by_version_key(self, store):
        saved = store.save_shape(_shape())
        assert saved["shape_id"]
        got = store.get_shape(
            ontology_version_id="ov-1",
            constraint_revision="rev-1",
            target_type="库存周转率",
        )
        assert got is not None
        assert got["shape_id"] == saved["shape_id"]
        assert got["shape_ttl"].startswith("@prefix")
        assert got["checksum"] == "abc123"

    def test_get_nonexistent_returns_none(self, store):
        assert (
            store.get_shape(
                ontology_version_id="nope",
                constraint_revision="x",
                target_type="y",
            )
            is None
        )

    def test_upsert_same_key_replaces_single_row(self, store):
        store.save_shape(_shape(checksum="c1"))
        store.save_shape(_shape(checksum="c2"))
        rows, total = store.list_shapes(ontology_version_id="ov-1")
        assert total == 1
        assert rows[0]["checksum"] == "c2"

    def test_constraint_revision_bump_coexists(self, store):
        store.save_shape(_shape(constraint_revision="rev-1"))
        store.save_shape(_shape(constraint_revision="rev-2"))
        _, total = store.list_shapes(ontology_version_id="ov-1")
        assert total == 2

    def test_json_fields_roundtrip(self, store):
        store.save_shape(_shape())
        got = store.get_shape(
            ontology_version_id="ov-1",
            constraint_revision="rev-1",
            target_type="库存周转率",
        )
        assert isinstance(got["source_type_defs"], list)
        assert got["source_type_defs"][0]["name"] == "库存周转率"
        assert isinstance(got["source_axioms"], list)
        assert got["source_axioms"][0]["axiom_type"] == "sub_class_of"

    def test_get_shape_by_id(self, store):
        saved = store.save_shape(_shape())
        got = store.get_shape_by_id(saved["shape_id"])
        assert got is not None
        assert got["target_type"] == "库存周转率"

    def test_delete_shape(self, store):
        saved = store.save_shape(_shape())
        assert store.delete_shape(saved["shape_id"]) is True
        assert store.get_shape_by_id(saved["shape_id"]) is None

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete_shape("no-such-id") is False

    def test_invalidate_by_version(self, store):
        store.save_shape(_shape(target_type="A"))
        store.save_shape(_shape(target_type="B"))
        n = store.delete_shapes_by_version("ov-1", constraint_revision="rev-1")
        assert n == 2
        _, total = store.list_shapes(ontology_version_id="ov-1")
        assert total == 0

    def test_list_pagination(self, store):
        for i in range(5):
            store.save_shape(_shape(target_type=f"T{i}"))
        rows, total = store.list_shapes(ontology_version_id="ov-1", page=1, page_size=2)
        assert total == 5
        assert len(rows) == 2

    def test_save_shape_requires_version_and_target(self, store):
        # 规则 14.2：缺失效键/目标类型必须显式失败，禁止写入幻影缓存行
        with pytest.raises(ValueError):
            store.save_shape(_shape(ontology_version_id=""))
        with pytest.raises(ValueError):
            store.save_shape(_shape(target_type=""))


class TestDerivedAxiom:
    def test_replace_persists_and_reads_back(self, store):
        axioms = [
            _axiom(),
            _axiom(axiom_type="disjoint_classes", subject="A", object="B"),
        ]
        n = store.replace_axioms_for_run(
            axioms, pipeline_run_id="run-1", domain_id="d-fin"
        )
        assert n == 2
        rows, total = store.list_axioms(pipeline_run_id="run-1")
        assert total == 2
        assert {r["axiom_type"] for r in rows} == {"sub_class_of", "disjoint_classes"}
        assert all(r["domain_id"] == "d-fin" for r in rows)

    def test_replace_is_idempotent_per_run(self, store):
        store.replace_axioms_for_run([_axiom()], pipeline_run_id="run-1")
        store.replace_axioms_for_run(
            [_axiom(), _axiom(subject="X")], pipeline_run_id="run-1"
        )
        _, total = store.list_axioms(pipeline_run_id="run-1")
        assert total == 2

    def test_cardinality_min_max_roundtrip(self, store):
        ax = _axiom(
            axiom_type="object_property_cardinality",
            subject="持有",
            object="",
            min_card=1,
            max_card=3,
        )
        store.replace_axioms_for_run([ax], pipeline_run_id="run-2")
        rows, _ = store.list_axioms(pipeline_run_id="run-2")
        assert rows[0]["min_card"] == 1
        assert rows[0]["max_card"] == 3

    def test_nullable_cardinality_stays_none(self, store):
        store.replace_axioms_for_run([_axiom()], pipeline_run_id="run-2b")
        rows, _ = store.list_axioms(pipeline_run_id="run-2b")
        assert rows[0]["min_card"] is None
        assert rows[0]["max_card"] is None

    def test_proof_json_roundtrip(self, store):
        store.replace_axioms_for_run(
            [_axiom(proof={"direct_edge": True, "depth": 2})], pipeline_run_id="run-3"
        )
        rows, _ = store.list_axioms(pipeline_run_id="run-3")
        assert rows[0]["proof"] == {"direct_edge": True, "depth": 2}

    def test_list_filter_by_type(self, store):
        store.replace_axioms_for_run(
            [
                _axiom(axiom_type="sub_class_of"),
                _axiom(axiom_type="disjoint_classes", subject="A", object="B"),
            ],
            pipeline_run_id="run-4",
        )
        rows, total = store.list_axioms(axiom_type="disjoint_classes")
        assert total == 1
        assert rows[0]["axiom_type"] == "disjoint_classes"

    def test_delete_by_run(self, store):
        store.replace_axioms_for_run([_axiom()], pipeline_run_id="run-5")
        n = store.delete_axioms_by_run("run-5")
        assert n == 1
        _, total = store.list_axioms(pipeline_run_id="run-5")
        assert total == 0

    def test_empty_run_persists_zero(self, store):
        n = store.replace_axioms_for_run([], pipeline_run_id="run-empty")
        assert n == 0
        _, total = store.list_axioms(pipeline_run_id="run-empty")
        assert total == 0

    def test_get_axiom_by_id(self, store):
        store.replace_axioms_for_run([_axiom(subject="唯一")], pipeline_run_id="run-6")
        rows, _ = store.list_axioms(pipeline_run_id="run-6")
        got = store.get_axiom(rows[0]["axiom_id"])
        assert got is not None
        assert got["subject"] == "唯一"

    def test_get_nonexistent_axiom_returns_none(self, store):
        assert store.get_axiom("no-such-axiom") is None

    def test_replace_axioms_requires_run_id(self, store):
        # 规则 14.2：公理必须归属某个 run，缺 run_id 显式失败
        with pytest.raises(ValueError):
            store.replace_axioms_for_run([_axiom()], pipeline_run_id="")
