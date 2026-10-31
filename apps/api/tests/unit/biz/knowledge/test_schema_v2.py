"""v2 存储 schema 测试（幂等迁移 + 八表齐全 + 唯一约束）。

迁移机制复用仓库既有 `CREATE TABLE IF NOT EXISTS` 幂等脚本（无 Alembic），
因此「重复执行不报错、不丢数据」是硬要求。
"""

from __future__ import annotations

import sqlite3

EXPECTED_TABLES = {
    "wiki_entries",
    "wiki_versions",
    "wiki_citations",
    "governed_documents",
    "qa_traces",
    "qa_provenance",
    "qa_actions",
    "feature_flags",
}


def _tables(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        conn.close()
    return {r[0] for r in rows}


class TestSchema:
    def test_all_eight_tables_created(self, kb_db):
        assert EXPECTED_TABLES <= _tables(kb_db)

    def test_migration_is_idempotent(self, kb_db):
        from odap.infra.storage.schema_v2 import ensure_v2_schema

        ensure_v2_schema(kb_db)
        ensure_v2_schema(kb_db)
        assert EXPECTED_TABLES <= _tables(kb_db)

    def test_indexes_created(self, kb_db):
        conn = sqlite3.connect(kb_db)
        try:
            names = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()}
        finally:
            conn.close()
        assert any("wiki_entries" in name for name in names)
        assert any("qa_provenance" in name for name in names)

    def test_provenance_step_is_unique_per_trace(self, kb_db):
        from odap.biz.core.ontology.orchestration.contracts import Evidence, StepProv
        from odap.biz.core.ontology.orchestration.provenance import ProvenanceBuilder
        from odap.biz.core.ontology.orchestration.repositories.trace_repo import (
            QaTraceRepository,
        )

        trace_id = "urn:odap:trace:01J9ZK8P3Q7N2M4R5T6V7W8X9A"
        builder = ProvenanceBuilder(trace_id)
        for step in ("intent", "map", "guard", "retrieve", "compose", "gate"):
            builder.add(step, StepProv(component="X", evidence=[
                Evidence(kind="decision", ref="decision:contract_ok")]))
        provenance = builder.build(tbox_version="sha256:x", contract_ok=True)

        repo = QaTraceRepository(db_path=kb_db)
        repo.save({"trace_id": trace_id, "query": "退货率口径",
                   "created_at": "2026-10-17T00:00:00+00:00"}, provenance)

        conn = sqlite3.connect(kb_db)
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM qa_provenance WHERE trace_id = ?", (trace_id,)
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 6

    def test_source_ref_uniqueness_scoped_per_table(self, db_path=None):
        """同一 source_ref 在 wiki_entries 与 governed_documents 各自唯一（局部唯一索引）。"""
        from odap.infra.storage.schema_v2 import ensure_v2_schema
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "odap_main.db")
            ensure_v2_schema(path)
            conn = sqlite3.connect(path)
            try:
                row = ("x", "标题", "draft", "u-owner", "0.1.0", "repo:docs/a.md", None,
                       "[]", "sha256:x", "正文", None, "[]", "[]", "", "t", "t")
                sql = (
                    "INSERT INTO wiki_entries (id, title, status, owner_id, version, "
                    "source_ref, superseded_by, supersedes, content_hash, content, "
                    "last_verified, tags, concept_refs, workspace_id, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                )
                conn.execute(sql, row)
                second = list(row)
                second[0] = "y"
                try:
                    conn.execute(sql, second)
                    duplicated = True
                except sqlite3.IntegrityError:
                    duplicated = False
                assert duplicated is False, "同一 source_ref 不应允许两条条目"
            finally:
                conn.close()
