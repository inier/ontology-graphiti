import pytest
from datetime import datetime


class TestSQLiteEngineStorage:
    @pytest.fixture
    def storage(self, tmp_path):
        from odap.biz.core.ontology.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        return SQLiteEngineStorage(db_path=str(tmp_path / "engine_test.db"))

    def test_save_and_get_version(self, storage):
        version = {
            "version_id": "v-1",
            "ontology_id": "ont-1",
            "version_number": "1.0.0",
            "changelog": "initial",
            "valid_time": "2026-01-01T00:00:00",
            "transaction_time": "2026-01-01T00:00:00",
            "status": "active",
            "snapshot": {"entities": 5},
        }
        storage.save_version(version)
        result = storage.get_version("v-1")
        assert result is not None
        assert result["version_id"] == "v-1"
        assert result["snapshot"]["entities"] == 5

    def test_get_version_not_found(self, storage):
        result = storage.get_version("nonexistent")
        assert result is None

    def test_list_versions(self, storage):
        for i in range(3):
            storage.save_version({
                "version_id": f"v-{i}",
                "ontology_id": "ont-1",
                "version_number": f"1.0.{i}",
                "changelog": f"change {i}",
                "valid_time": f"2026-01-0{i+1}T00:00:00",
                "transaction_time": f"2026-01-0{i+1}T00:00:00",
                "status": "active",
                "snapshot": {},
            })
        results = storage.list_versions("ont-1")
        assert len(results) == 3

    def test_get_version_at_time(self, storage):
        storage.save_version({
            "version_id": "v-1",
            "ontology_id": "ont-1",
            "version_number": "1.0.0",
            "changelog": "initial",
            "valid_time": "2026-01-01T00:00:00",
            "transaction_time": "2026-01-01T00:00:00",
            "status": "active",
            "snapshot": {},
        })
        storage.save_version({
            "version_id": "v-2",
            "ontology_id": "ont-1",
            "version_number": "1.0.1",
            "changelog": "update",
            "valid_time": "2026-02-01T00:00:00",
            "transaction_time": "2026-02-01T00:00:00",
            "status": "active",
            "snapshot": {},
        })
        result = storage.get_version_at_time("ont-1", "2026-01-15T00:00:00")
        assert result is not None
        assert result["version_id"] == "v-1"

    def test_save_and_get_audit(self, storage):
        audit = {
            "audit_id": "a-1",
            "entity_type_id": "et-1",
            "source": "manual",
            "process_steps": [{"step": "extract"}],
            "transform_rules": [{"rule": "normalize"}],
            "result": "success",
            "timestamp": "2026-01-01T00:00:00",
        }
        storage.save_audit(audit)
        result = storage.get_audit("a-1")
        assert result is not None
        assert result["audit_id"] == "a-1"
        assert len(result["process_steps"]) == 1
        assert len(result["transform_rules"]) == 1

    def test_list_audits(self, storage):
        for i in range(3):
            storage.save_audit({
                "audit_id": f"a-{i}",
                "entity_type_id": "et-1",
                "source": "manual",
                "process_steps": [],
                "transform_rules": [],
                "result": "success",
                "timestamp": f"2026-01-0{i+1}T00:00:00",
            })
        results = storage.list_audits(entity_type_id="et-1")
        assert len(results) == 3

    def test_list_audits_filter_by_entity_type(self, storage):
        storage.save_audit({
            "audit_id": "a-1",
            "entity_type_id": "et-1",
            "source": "manual",
            "process_steps": [],
            "transform_rules": [],
            "result": "success",
            "timestamp": "2026-01-01T00:00:00",
        })
        storage.save_audit({
            "audit_id": "a-2",
            "entity_type_id": "et-2",
            "source": "manual",
            "process_steps": [],
            "transform_rules": [],
            "result": "success",
            "timestamp": "2026-01-01T00:00:00",
        })
        results = storage.list_audits(entity_type_id="et-1")
        assert len(results) == 1
        assert results[0]["entity_type_id"] == "et-1"


class TestVersionManagerImpl:
    @pytest.fixture
    def version_manager(self, tmp_path):
        from odap.biz.core.ontology.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        from odap.biz.core.ontology.engine.impl.version_manager_impl import VersionManagerImpl
        storage = SQLiteEngineStorage(db_path=str(tmp_path / "vm_test.db"))
        return VersionManagerImpl(storage=storage)

    def test_create_version(self, version_manager):
        result = version_manager.create_version("ont-1", "initial version")
        assert "version_id" in result
        assert result["ontology_id"] == "ont-1"
        assert result["version_number"] == "1.0.0"
        assert result["status"] == "active"

    def test_get_version(self, version_manager):
        created = version_manager.create_version("ont-1", "initial")
        result = version_manager.get_version("ont-1", created["version_id"])
        assert result is not None
        assert result["changelog"] == "initial"

    def test_get_version_wrong_ontology(self, version_manager):
        created = version_manager.create_version("ont-1", "initial")
        result = version_manager.get_version("ont-2", created["version_id"])
        assert result is None

    def test_list_versions(self, version_manager):
        version_manager.create_version("ont-1", "v1")
        version_manager.create_version("ont-1", "v2")
        results = version_manager.list_versions("ont-1")
        assert len(results) == 2

    def test_rollback_version(self, version_manager):
        v1 = version_manager.create_version("ont-1", "initial", snapshot={"key": "val1"})
        v2 = version_manager.create_version("ont-1", "update", snapshot={"key": "val2"})
        rollback = version_manager.rollback_version("ont-1", v1["version_id"])
        assert rollback["status"] == "rolled_back"
        assert "Rollback" in rollback["changelog"]

    def test_rollback_version_not_found(self, version_manager):
        result = version_manager.rollback_version("ont-1", "nonexistent")
        assert result.get("status") == "error"

    def test_compare_versions(self, version_manager):
        v1 = version_manager.create_version("ont-1", "v1", snapshot={"a": 1})
        v2 = version_manager.create_version("ont-1", "v2", snapshot={"a": 2})
        result = version_manager.compare_versions("ont-1", v1["version_id"], v2["version_id"])
        assert "v1" in result
        assert "v2" in result

    def test_compare_versions_not_found(self, version_manager):
        result = version_manager.compare_versions("ont-1", "nonexistent1", "nonexistent2")
        assert result.get("status") == "error"

    def test_temporal_query(self, version_manager):
        version_manager.create_version("ont-1", "v1", valid_time="2026-01-01T00:00:00")
        version_manager.create_version("ont-1", "v2", valid_time="2026-06-01T00:00:00")
        result = version_manager.query_at_time("ont-1", "2026-03-01T00:00:00")
        assert result is not None
        assert result["changelog"] == "v1"

    def test_version_number_auto_increment(self, version_manager):
        v1 = version_manager.create_version("ont-1", "v1")
        v2 = version_manager.create_version("ont-1", "v2")
        assert v1["version_number"] == "1.0.0"
        assert v2["version_number"] == "1.0.1"


class TestValidationEngineImpl:
    @pytest.fixture
    def validation_engine(self):
        from odap.biz.core.ontology.engine.impl.validation_engine_impl import ValidationEngineImpl
        return ValidationEngineImpl()

    def test_validate_entity_type_valid(self, validation_engine):
        type_def = {"name": "Unit", "properties": [{"name": "unit_id"}]}
        result = validation_engine.validate_entity_type(type_def)
        assert result["is_valid"] is True

    def test_validate_entity_type_no_name(self, validation_engine):
        type_def = {"properties": [{"name": "unit_id"}]}
        result = validation_engine.validate_entity_type(type_def)
        assert result["is_valid"] is False
        assert any("name is required" in e for e in result["errors"])

    def test_validate_entity_type_no_properties(self, validation_engine):
        type_def = {"name": "Unit"}
        result = validation_engine.validate_entity_type(type_def)
        assert len(result["warnings"]) > 0

    def test_validate_entity_type_primary_key_not_in_props(self, validation_engine):
        type_def = {
            "name": "Unit",
            "properties": [{"name": "name"}],
            "primary_key": ["unit_id"],
        }
        result = validation_engine.validate_entity_type(type_def)
        assert result["is_valid"] is False
        assert any("unit_id" in e for e in result["errors"])

    def test_validate_instance_missing_required(self, validation_engine):
        type_def = {
            "name": "Unit",
            "properties": [{"name": "unit_id", "required": True}],
        }
        result = validation_engine.validate_instance(type_def, {})
        assert result["is_valid"] is False
        assert any("unit_id" in e for e in result["errors"])

    def test_validate_instance_valid(self, validation_engine):
        type_def = {
            "name": "Unit",
            "properties": [{"name": "unit_id", "required": True}],
        }
        result = validation_engine.validate_instance(type_def, {"unit_id": "U-1"})
        assert result["is_valid"] is True

    def test_check_consistency(self, validation_engine):
        result = validation_engine.check_consistency("ont-1")
        assert "is_valid" in result
        assert "ontology_id" in result


class TestAuditRecorderImpl:
    @pytest.fixture
    def audit_recorder(self, tmp_path):
        from odap.biz.core.ontology.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        from odap.biz.core.ontology.engine.impl.audit_recorder_impl import AuditRecorderImpl
        storage = SQLiteEngineStorage(db_path=str(tmp_path / "audit_test.db"))
        return AuditRecorderImpl(storage=storage)

    def test_record_ingest(self, audit_recorder):
        result = audit_recorder.record_ingest(
            entity_type_id="et-1",
            source="manual",
            process_steps=[{"step": "extract"}],
            transform_rules=[{"rule": "normalize"}],
            result="success",
        )
        assert "audit_id" in result
        assert result["entity_type_id"] == "et-1"
        assert len(result["process_steps"]) == 1

    def test_get_audit(self, audit_recorder):
        created = audit_recorder.record_ingest("et-1", "manual", [], [], "success")
        result = audit_recorder.get_audit(created["audit_id"])
        assert result is not None
        assert result["audit_id"] == created["audit_id"]

    def test_get_audit_not_found(self, audit_recorder):
        result = audit_recorder.get_audit("nonexistent")
        assert result is None

    def test_list_audits(self, audit_recorder):
        audit_recorder.record_ingest("et-1", "manual", [], [], "success")
        audit_recorder.record_ingest("et-1", "api", [], [], "success")
        results = audit_recorder.list_audits(entity_type_id="et-1")
        assert len(results) == 2

    def test_list_audits_filter_by_source(self, audit_recorder):
        audit_recorder.record_ingest("et-1", "manual", [], [], "success")
        audit_recorder.record_ingest("et-2", "api", [], [], "success")
        results = audit_recorder.list_audits(entity_type_id="et-1")
        assert all(r["entity_type_id"] == "et-1" for r in results)


class TestEngineService:
    @pytest.fixture
    def engine_service(self, tmp_path):
        from odap.biz.core.ontology.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        from odap.biz.core.ontology.engine.impl.version_manager_impl import VersionManagerImpl
        from odap.biz.core.ontology.engine.impl.audit_recorder_impl import AuditRecorderImpl
        from odap.biz.core.ontology.engine.impl.validation_engine_impl import ValidationEngineImpl
        from odap.biz.core.ontology.engine.services.engine_service import EngineService
        EngineService._instance = None
        storage = SQLiteEngineStorage(db_path=str(tmp_path / "engine_svc_test.db"))
        svc = EngineService.__new__(EngineService)
        svc._version_manager = VersionManagerImpl(storage=storage)
        svc._audit_recorder = AuditRecorderImpl(storage=storage)
        svc._validation_engine = ValidationEngineImpl()
        svc._initialized = True
        EngineService._instance = svc
        return svc

    def test_create_version(self, engine_service):
        result = engine_service.create_version("ont-1", "initial")
        assert "version_id" in result

    def test_get_version_not_found(self, engine_service):
        result = engine_service.get_version("ont-1", "nonexistent")
        assert result.get("status") == "error"

    def test_list_versions(self, engine_service):
        engine_service.create_version("ont-1", "v1")
        engine_service.create_version("ont-1", "v2")
        result = engine_service.list_versions("ont-1")
        assert len(result["versions"]) == 2

    def test_rollback_version(self, engine_service):
        v1 = engine_service.create_version("ont-1", "v1")
        rollback = engine_service.rollback_version("ont-1", v1["version_id"])
        assert rollback["status"] == "rolled_back"

    def test_compare_versions(self, engine_service):
        v1 = engine_service.create_version("ont-1", "v1")
        v2 = engine_service.create_version("ont-1", "v2")
        result = engine_service.compare_versions("ont-1", v1["version_id"], v2["version_id"])
        assert "v1" in result
        assert "v2" in result

    def test_temporal_query(self, engine_service):
        engine_service.create_version("ont-1", "v1", valid_time="2026-01-01T00:00:00")
        result = engine_service.query_at_time("ont-1", "2026-06-01T00:00:00")
        assert result is not None

    def test_temporal_query_no_result(self, engine_service):
        result = engine_service.query_at_time("ont-1", "2020-01-01T00:00:00")
        assert result.get("status") == "error"

    def test_validate_entity_type(self, engine_service):
        result = engine_service.validate({"name": "Unit", "properties": [{"name": "id"}]})
        assert result["is_valid"] is True

    def test_validate_instance(self, engine_service):
        result = engine_service.validate(
            {"name": "Unit", "properties": [{"name": "id", "required": True}]},
            properties={"id": "U-1"},
        )
        assert "type_validation" in result
        assert "instance_validation" in result

    def test_record_audit(self, engine_service):
        result = engine_service.record_audit("et-1", "manual", [], [], "success")
        assert "audit_id" in result

    def test_list_audit_records(self, engine_service):
        engine_service.record_audit("et-1", "manual", [], [], "success")
        result = engine_service.list_audits()
        assert len(result["audits"]) == 1

    def test_version_conflict_detection(self, engine_service):
        v1 = engine_service.create_version("ont-1", "v1")
        v2 = engine_service.create_version("ont-1", "v2")
        assert v1["version_id"] != v2["version_id"]
        assert v1["version_number"] != v2["version_number"]

    def test_rollback_creates_new_version(self, engine_service):
        v1 = engine_service.create_version("ont-1", "v1", snapshot={"key": "val"})
        rollback = engine_service.rollback_version("ont-1", v1["version_id"])
        assert rollback["version_id"] != v1["version_id"]
        assert rollback["snapshot"] == {"key": "val"}

    def test_validation_error_messages(self, engine_service):
        result = engine_service.validate({"properties": []}, properties={})
        assert result["is_valid"] is False
        assert len(result.get("errors", [])) > 0
