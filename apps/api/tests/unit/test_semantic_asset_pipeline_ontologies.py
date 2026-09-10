"""semantic_asset_pipeline 本体选项整形测试（ADR-079 §7 domain_code 权威字段）。

验证两件事：
  1. 读路径只认 domain_code，不再从 USL__{code} 命名反推（AGENTS.md 规则 14）；
  2. 遗留行经 SQLiteOntologyStorage._migrate() 回填后在管理界面重新可见
     —— 「删读侧兜底」与「加迁移回填」必须成对生效，单独任一项都会丢数据。
"""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

_ONTOLOGY_SVC = "odap.biz.core.ontology.public.OntologyService"
_USL_SVC = "odap.biz.semantic_admin.usl_manager.services.UslManagerService"

_DOMAINS = [{"code": "sanguo", "display_name": "三国", "description": "三国领域"}]


@pytest.fixture
def pipeline():
    from odap.biz.semantic_admin.semantic_asset_pipeline.services.pipeline_service import (
        SemanticAssetPipeline,
    )
    return SemanticAssetPipeline()


def _stub_ontology_service(ontologies):
    class _Svc:
        def list_ontologies(self, workspace_id=None):
            return {"status": "ok", "ontologies": ontologies}

    return _Svc


def _stub_usl_service(domains=_DOMAINS):
    class _Svc:
        def list_domains(self, page=1, page_size=500):
            return {"status": "ok", "items": domains}

    return _Svc


def _ont(oid, name, domain_code=None, ws="ws-1"):
    return {
        "ontology_id": oid,
        "name": name,
        "domain_code": domain_code,
        "workspace_id": ws,
    }


class TestOptionsDisplayLabel:
    def test_maps_domain_code_to_readable_label(self, pipeline):
        with patch(_ONTOLOGY_SVC, _stub_ontology_service([_ont("o1", "USL__sanguo", "sanguo")])), \
             patch(_USL_SVC, _stub_usl_service()):
            res = pipeline.options()

        item = res["ontologies"][0]
        assert item["display_label"] == "三国（sanguo）"
        assert item["domain_display_name"] == "三国"

    def test_unknown_domain_code_falls_back_to_code(self, pipeline):
        """领域表查不到时展示 code 本身，而非静默留空。"""
        with patch(_ONTOLOGY_SVC, _stub_ontology_service([_ont("o1", "USL__unknown", "unknown")])), \
             patch(_USL_SVC, _stub_usl_service()):
            res = pipeline.options()

        assert res["ontologies"][0]["display_label"] == "unknown"

    def test_keeps_raw_name_without_domain_code(self, pipeline):
        with patch(_ONTOLOGY_SVC, _stub_ontology_service([_ont("o2", "手工本体")])), \
             patch(_USL_SVC, _stub_usl_service()):
            res = pipeline.options()

        assert res["ontologies"][0]["display_label"] == "手工本体"

    def test_does_not_infer_domain_code_from_name(self, pipeline):
        """规则 14 回归闸：命名形如 USL__sanguo 但 domain_code 缺失时禁止反推。"""
        with patch(_ONTOLOGY_SVC, _stub_ontology_service([_ont("o3", "USL__sanguo")])), \
             patch(_USL_SVC, _stub_usl_service()):
            res = pipeline.options()

        item = res["ontologies"][0]
        assert item["display_label"] == "USL__sanguo"
        assert "domain_display_name" not in item


class TestListUslOntologies:
    def test_filters_by_domain_code_only(self, pipeline):
        ontologies = [
            _ont("o1", "USL__sanguo", "sanguo"),
            _ont("o2", "USL__legacy"),
            _ont("o3", "手工本体"),
        ]
        with patch(_ONTOLOGY_SVC, _stub_ontology_service(ontologies)), \
             patch(_USL_SVC, _stub_usl_service()):
            res = pipeline.list_usl_ontologies()

        assert [i["ontology_id"] for i in res["items"]] == ["o1"]
        assert res["items"][0]["domain_display_name"] == "三国"

    def test_does_not_infer_domain_code_from_name(self, pipeline):
        """规则 14 回归闸：o2 命名符合约定但缺 domain_code，不得被当作 USL 本体列出。"""
        ontologies = [_ont("o1", "USL__sanguo", "sanguo"), _ont("o2", "USL__xiyou")]
        with patch(_ONTOLOGY_SVC, _stub_ontology_service(ontologies)), \
             patch(_USL_SVC, _stub_usl_service()):
            res = pipeline.list_usl_ontologies()

        assert [i["ontology_id"] for i in res["items"]] == ["o1"]


class TestMigrationBackfillRestoresVisibility:
    def test_legacy_row_visible_after_storage_migration(self, tmp_path, pipeline):
        """遗留行回填 domain_code 后重新出现在 USL 本体管理界面。"""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )

        db_path = str(tmp_path / "legacy_usl.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE ontologies (
                ontology_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                workspace_id TEXT NOT NULL,
                scenario_id TEXT,
                domain_code TEXT,
                current_version TEXT DEFAULT 'v0.1.0',
                status TEXT DEFAULT 'DRAFT',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO ontologies (ontology_id, name, workspace_id, domain_code,"
            " created_at, updated_at) VALUES ('legacy-1', 'USL__sanguo', 'ws-1', NULL,"
            " '2026-01-01', '2026-01-01')"
        )
        conn.commit()
        conn.close()

        SQLiteOntologyStorage(db_path=db_path)

        conn = sqlite3.connect(db_path)
        backfilled = dict(conn.execute("SELECT ontology_id, domain_code FROM ontologies"))
        conn.close()
        assert backfilled["legacy-1"] == "sanguo"

        migrated = [_ont("legacy-1", "USL__sanguo", backfilled["legacy-1"])]
        with patch(_ONTOLOGY_SVC, _stub_ontology_service(migrated)), \
             patch(_USL_SVC, _stub_usl_service()):
            res = pipeline.list_usl_ontologies()

        assert [i["ontology_id"] for i in res["items"]] == ["legacy-1"]
        assert res["items"][0]["display_label"] == "三国（sanguo）"
