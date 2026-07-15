"""Tests for SQLiteOntologyStorage batch delete methods.

AGENTS.md 规则 9: 新增模块必须同步新增测试文件。
AGENTS.md 规则 C: SQLite 存储层用 tmp_path 真实 DB，禁止 MagicMock。

覆盖:
- 7 个类型定义表的 batch delete by ontology_id
- schema_versions 和 extraction_sessions 的 batch delete by ontology_id
- 空表删除返回 0
- 多行删除返回正确行数
- 不同 ontology_id 的数据不受影响
"""

import pytest


@pytest.fixture
def storage(tmp_path):
    """创建使用临时 DB 的 SQLiteOntologyStorage 实例"""
    from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
        SQLiteOntologyStorage,
    )

    db_path = str(tmp_path / "test_ontology_api.db")
    return SQLiteOntologyStorage(db_path=db_path)


def _save_ontology(storage, ontology_id="ont-1", name="Test Ontology"):
    """辅助：保存一条本体记录"""
    return storage.save_ontology(
        {
            "ontology_id": ontology_id,
            "name": name,
            "workspace_id": "ws-1",
        }
    )


class TestBatchDeleteObjectTypes:
    """delete_object_types_by_ontology"""

    def test_deletes_rows_for_matching_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        storage.save_object_type(
            {"type_id": "ot-1", "ontology_id": "ont-1", "name": "ObjA"}
        )
        storage.save_object_type(
            {"type_id": "ot-2", "ontology_id": "ont-1", "name": "ObjB"}
        )
        deleted = storage.delete_object_types_by_ontology("ont-1")
        assert deleted == 2
        assert storage.list_object_types("ont-1") == []

    def test_returns_zero_when_no_rows(self, storage):
        deleted = storage.delete_object_types_by_ontology("nonexistent")
        assert deleted == 0

    def test_does_not_affect_other_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        _save_ontology(storage, "ont-2")
        storage.save_object_type(
            {"type_id": "ot-1", "ontology_id": "ont-1", "name": "ObjA"}
        )
        storage.save_object_type(
            {"type_id": "ot-2", "ontology_id": "ont-2", "name": "ObjB"}
        )
        storage.delete_object_types_by_ontology("ont-1")
        assert len(storage.list_object_types("ont-2")) == 1


class TestBatchDeleteLinkTypes:
    """delete_link_types_by_ontology"""

    def test_deletes_rows_for_matching_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        storage.save_link_type(
            {"type_id": "lt-1", "ontology_id": "ont-1", "name": "LinkA"}
        )
        deleted = storage.delete_link_types_by_ontology("ont-1")
        assert deleted == 1
        assert storage.list_link_types("ont-1") == []

    def test_returns_zero_when_no_rows(self, storage):
        assert storage.delete_link_types_by_ontology("nonexistent") == 0


class TestBatchDeleteActionTypes:
    """delete_action_types_by_ontology"""

    def test_deletes_rows_for_matching_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        storage.save_action_type(
            {"type_id": "at-1", "ontology_id": "ont-1", "name": "ActA"}
        )
        deleted = storage.delete_action_types_by_ontology("ont-1")
        assert deleted == 1
        assert storage.list_action_types("ont-1") == []

    def test_returns_zero_when_no_rows(self, storage):
        assert storage.delete_action_types_by_ontology("nonexistent") == 0


class TestBatchDeleteProcessTypes:
    """delete_process_types_by_ontology"""

    def test_deletes_rows_for_matching_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        storage.save_process_type(
            {"type_id": "pt-1", "ontology_id": "ont-1", "name": "ProcA"}
        )
        deleted = storage.delete_process_types_by_ontology("ont-1")
        assert deleted == 1
        assert storage.list_process_types("ont-1") == []

    def test_returns_zero_when_no_rows(self, storage):
        assert storage.delete_process_types_by_ontology("nonexistent") == 0


class TestBatchDeleteRuleTypes:
    """delete_rule_types_by_ontology"""

    def test_deletes_rows_for_matching_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        storage.save_rule_type(
            {"type_id": "rt-1", "ontology_id": "ont-1", "name": "RuleA"}
        )
        deleted = storage.delete_rule_types_by_ontology("ont-1")
        assert deleted == 1
        assert storage.list_rule_types("ont-1") == []

    def test_returns_zero_when_no_rows(self, storage):
        assert storage.delete_rule_types_by_ontology("nonexistent") == 0


class TestBatchDeleteFunctionTypes:
    """delete_function_types_by_ontology"""

    def test_deletes_rows_for_matching_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        storage.save_function_type(
            {"type_id": "ft-1", "ontology_id": "ont-1", "name": "FuncA"}
        )
        deleted = storage.delete_function_types_by_ontology("ont-1")
        assert deleted == 1
        assert storage.list_function_types("ont-1") == []

    def test_returns_zero_when_no_rows(self, storage):
        assert storage.delete_function_types_by_ontology("nonexistent") == 0


class TestBatchDeleteIndicatorTypes:
    """delete_indicator_types_by_ontology"""

    def test_deletes_rows_for_matching_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        storage.save_indicator_type(
            {"type_id": "it-1", "ontology_id": "ont-1", "name": "IndA"}
        )
        deleted = storage.delete_indicator_types_by_ontology("ont-1")
        assert deleted == 1
        assert storage.list_indicator_types("ont-1") == []

    def test_returns_zero_when_no_rows(self, storage):
        assert storage.delete_indicator_types_by_ontology("nonexistent") == 0


class TestBatchDeleteSchemaVersions:
    """delete_schema_versions_by_ontology"""

    def test_deletes_rows_for_matching_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        storage.save_schema_version(
            {"version_id": "sv-1", "ontology_id": "ont-1", "version_number": "v1"}
        )
        storage.save_schema_version(
            {"version_id": "sv-2", "ontology_id": "ont-1", "version_number": "v2"}
        )
        deleted = storage.delete_schema_versions_by_ontology("ont-1")
        assert deleted == 2

    def test_returns_zero_when_no_rows(self, storage):
        assert storage.delete_schema_versions_by_ontology("nonexistent") == 0

    def test_does_not_affect_other_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        _save_ontology(storage, "ont-2")
        storage.save_schema_version(
            {"version_id": "sv-1", "ontology_id": "ont-1", "version_number": "v1"}
        )
        storage.save_schema_version(
            {"version_id": "sv-2", "ontology_id": "ont-2", "version_number": "v1"}
        )
        storage.delete_schema_versions_by_ontology("ont-1")
        assert storage.get_schema_version("sv-2") is not None


class TestBatchDeleteExtractionSessions:
    """delete_extraction_sessions_by_ontology"""

    def test_deletes_rows_for_matching_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        storage.save_extraction_session(
            {
                "session_id": "es-1",
                "ontology_id": "ont-1",
                "extraction_type": "document",
            }
        )
        deleted = storage.delete_extraction_sessions_by_ontology("ont-1")
        assert deleted == 1

    def test_returns_zero_when_no_rows(self, storage):
        assert storage.delete_extraction_sessions_by_ontology("nonexistent") == 0

    def test_does_not_affect_other_ontology(self, storage):
        _save_ontology(storage, "ont-1")
        _save_ontology(storage, "ont-2")
        storage.save_extraction_session(
            {
                "session_id": "es-1",
                "ontology_id": "ont-1",
                "extraction_type": "document",
            }
        )
        storage.save_extraction_session(
            {
                "session_id": "es-2",
                "ontology_id": "ont-2",
                "extraction_type": "document",
            }
        )
        storage.delete_extraction_sessions_by_ontology("ont-1")
        assert storage.get_extraction_session("es-2") is not None


class TestCascadeDeleteIntegration:
    """Integration: OntologyService.delete_ontology calls all batch deletes"""

    def test_delete_ontology_cascades_to_all_type_tables(self, tmp_path):
        """Verify that deleting an ontology removes all associated type definitions"""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )
        from odap.biz.core.ontology.ontology_api.services.ontology_service import (
            OntologyService,
        )

        db_path = str(tmp_path / "test_cascade.db")
        storage = SQLiteOntologyStorage(db_path=db_path)

        _save_ontology(storage, "ont-1")
        storage.save_object_type(
            {"type_id": "ot-1", "ontology_id": "ont-1", "name": "ObjA"}
        )
        storage.save_link_type(
            {"type_id": "lt-1", "ontology_id": "ont-1", "name": "LinkA"}
        )
        storage.save_schema_version(
            {"version_id": "sv-1", "ontology_id": "ont-1", "version_number": "v1"}
        )
        storage.save_extraction_session(
            {
                "session_id": "es-1",
                "ontology_id": "ont-1",
                "extraction_type": "document",
            }
        )

        svc = OntologyService(db_path=db_path)
        result = svc.delete_ontology("ont-1")

        assert result.get("deleted") is True
        # Verify cascade: re-check using the same storage instance
        assert storage.list_object_types("ont-1") == []
        assert storage.list_link_types("ont-1") == []
