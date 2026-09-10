"""TDD 单元测试：Ontology.domain_code 权威字段（ADR-079 §7）。

验证：
  T-DC-1: 新建表含 domain_code 列，save_ontology 正确写入
  T-DC-2: 迁移——旧表（无 domain_code 列）初始化后自动补列
  T-DC-3: create_ontology 接受 domain_code 参数并返回
  T-DC-4: resolve_ontology 创建本体时写入 domain_code
  T-DC-5: resolve_ontology 二次调用按 domain_code 精确命中（不重复创建）
  T-DC-6: 迁移——遗留行（domain_code 为空）按 USL__ 前缀一次性回填，
          且不误匹配 USLxy 等形近名称、不覆盖已有值、可重复执行
"""

from __future__ import annotations

import sqlite3

import pytest

from odap.infra.security.encryption import ClassifiedFieldEncryptor


@pytest.fixture(autouse=True)
def _reset_encryptor_singleton():
    ClassifiedFieldEncryptor._instance = None
    ClassifiedFieldEncryptor._key = None
    yield
    ClassifiedFieldEncryptor._instance = None
    ClassifiedFieldEncryptor._key = None


@pytest.fixture
def storage(tmp_path):
    from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
        SQLiteOntologyStorage,
    )
    return SQLiteOntologyStorage(db_path=str(tmp_path / "test_ontology_dc.db"))


class TestDomainCodeStorage:
    def test_save_and_read_domain_code(self, storage):
        ont = {
            "name": "USL__sanguo",
            "workspace_id": "ws-001",
            "domain_code": "sanguo",
            "scenario_id": None,
        }
        saved = storage.save_ontology(ont)
        assert saved["domain_code"] == "sanguo"
        got = storage.get_ontology(saved["ontology_id"])
        assert got["domain_code"] == "sanguo"

    def test_migration_adds_domain_code_column(self, tmp_path):
        """旧表（无 domain_code 列）初始化后自动迁移补列"""
        db_path = str(tmp_path / "legacy_ontology.db")
        # 1. 手工创建"旧版" ontologies 表（无 domain_code 列）
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE ontologies (
                ontology_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                workspace_id TEXT NOT NULL,
                scenario_id TEXT,
                current_version TEXT DEFAULT 'v0.1.0',
                status TEXT DEFAULT 'DRAFT',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

        # 2. 用新代码初始化（触发 _migrate 补列）
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )
        storage = SQLiteOntologyStorage(db_path=db_path)

        # 3. 验证列已补齐
        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(ontologies)")}
        conn.close()
        assert "domain_code" in cols

    def test_domain_code_nullable(self, storage):
        """不传 domain_code 时列为 NULL（可空），不报错"""
        ont = {"name": "plain-ontology", "workspace_id": "ws-001"}
        saved = storage.save_ontology(ont)
        assert saved["domain_code"] is None


class TestDomainCodeBackfill:
    """T-DC-6: 遗留行 domain_code 回填——USL__ 命名约定只在迁移中解释一次。"""

    LEGACY_ROWS = [
        ("ont-1", "USL__sanguo", None),        # 遗留 USL 行 → 回填 sanguo
        ("ont-2", "USL__xiyou", ""),           # 空串同样视为缺失 → 回填 xiyou
        ("ont-3", "plain-ontology", None),     # 非 USL → 保持 NULL
        ("ont-4", "USLxy_sanguo", None),       # 形近名称 → 不得误匹配
        ("ont-5", "USL__", None),              # 前缀后为空 → 不得回填成空串
        ("ont-6", "USL__manual", "manual2"),   # 已有权威值 → 不得覆盖
    ]

    def _migrate_and_read(self, tmp_path):
        """建遗留库 → 触发 _migrate → 回读 ontology_id→domain_code 映射。"""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )
        db_path = str(tmp_path / "legacy_backfill.db")
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
        conn.executemany(
            "INSERT INTO ontologies (ontology_id, name, workspace_id, domain_code,"
            " created_at, updated_at) VALUES (?, ?, 'ws-001', ?, '2026-01-01', '2026-01-01')",
            self.LEGACY_ROWS,
        )
        conn.commit()
        conn.close()

        SQLiteOntologyStorage(db_path=db_path)

        conn = sqlite3.connect(db_path)
        rows = dict(conn.execute("SELECT ontology_id, domain_code FROM ontologies"))
        conn.close()
        return db_path, rows

    def test_backfills_legacy_usl_rows(self, tmp_path):
        _, got = self._migrate_and_read(tmp_path)
        assert got["ont-1"] == "sanguo"
        assert got["ont-2"] == "xiyou"

    def test_ignores_non_usl_and_lookalike_names(self, tmp_path):
        """USLxy_sanguo 是 LIKE 'USL__%' 的误匹配陷阱（'_' 为单字符通配符）"""
        _, got = self._migrate_and_read(tmp_path)
        assert got["ont-3"] is None
        assert got["ont-4"] is None
        assert got["ont-5"] is None

    def test_does_not_overwrite_authoritative_value(self, tmp_path):
        _, got = self._migrate_and_read(tmp_path)
        assert got["ont-6"] == "manual2"

    def test_migration_is_idempotent(self, tmp_path):
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )
        db_path, first = self._migrate_and_read(tmp_path)
        SQLiteOntologyStorage(db_path=db_path)
        conn = sqlite3.connect(db_path)
        second = dict(conn.execute("SELECT ontology_id, domain_code FROM ontologies"))
        conn.close()
        assert second == first


class TestOntologyService:
    def test_create_ontology_accepts_domain_code(self, tmp_path):
        from odap.biz.core.ontology.ontology_api.services.ontology_service import (
            OntologyService,
        )
        svc = OntologyService(db_path=str(tmp_path / "svc_dc.db"))
        created = svc.create_ontology(
            name="USL__sanguo",
            workspace_id="ws-001",
            domain_code="sanguo",
        )
        assert created["domain_code"] == "sanguo"
        assert created["ontology_id"]


class TestResolveOntology:
    def _make_svc(self, tmp_path):
        from odap.biz.core.ontology.ontology_api.services.ontology_service import (
            OntologyService,
        )
        return OntologyService(db_path=str(tmp_path / "resolve_dc.db"))

    def _make_usl_storage(self, domain_code="sanguo"):
        """构造带 get_domain 的 USL storage stub（真实类，非 MagicMock）"""
        class _UslStorage:
            def get_domain(self, domain_id):
                return {"id": domain_id, "code": domain_code, "display_name": "三国"}
        return _UslStorage()

    def test_resolve_ontology_writes_domain_code(self, tmp_path):
        from odap.biz.semantic_admin.usl_writeback.impl.graphiti_writeback_adapter import (
            GraphitiWritebackAdapter,
        )
        adapter = GraphitiWritebackAdapter(
            ontology_service=self._make_svc(tmp_path),
            usl_storage=self._make_usl_storage("sanguo"),
        )
        result = adapter.resolve_ontology("d-sanguo-1", workspace_id="ws-001")
        assert result.get("ontology_id")
        assert result.get("domain_code") == "sanguo"

    def test_resolve_ontology_idempotent_by_domain_code(self, tmp_path):
        from odap.biz.semantic_admin.usl_writeback.impl.graphiti_writeback_adapter import (
            GraphitiWritebackAdapter,
        )
        svc = self._make_svc(tmp_path)
        adapter = GraphitiWritebackAdapter(
            ontology_service=svc,
            usl_storage=self._make_usl_storage("sanguo"),
        )
        first = adapter.resolve_ontology("d-sanguo-1", workspace_id="ws-001")
        # 清缓存，模拟二次调用（真实场景可能重启进程）
        adapter._domain_ontology_cache.clear()
        second = adapter.resolve_ontology("d-sanguo-1", workspace_id="ws-001")
        assert first["ontology_id"] == second["ontology_id"]
        assert second.get("created_new") is False
