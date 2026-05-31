from typing import Any, Dict, List

from ..impl.version_manager_impl import VersionManagerImpl
from ..impl.audit_recorder_impl import AuditRecorderImpl
from ..impl.validation_engine_impl import ValidationEngineImpl


class EngineService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._version_manager = VersionManagerImpl()
        self._audit_recorder = AuditRecorderImpl()
        self._validation_engine = ValidationEngineImpl()
        self._initialized = True

    def create_version(self, ontology_id: str, changelog: str, valid_time: str = "", snapshot: Dict[str, Any] = None) -> Dict[str, Any]:
        result = self._version_manager.create_version(ontology_id, changelog, valid_time, snapshot)
        return result

    def get_version(self, ontology_id: str, version_id: str) -> Dict[str, Any]:
        result = self._version_manager.get_version(ontology_id, version_id)
        if not result:
            return {"status": "error", "message": "Version not found"}
        return result

    def list_versions(self, ontology_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        results = self._version_manager.list_versions(ontology_id, page, page_size)
        return {"versions": results, "page": page, "page_size": page_size}

    def rollback_version(self, ontology_id: str, target_version_id: str) -> Dict[str, Any]:
        result = self._version_manager.rollback_version(ontology_id, target_version_id)
        if result.get("status") == "error":
            return result
        return result

    def compare_versions(self, ontology_id: str, v1_id: str, v2_id: str) -> Dict[str, Any]:
        return self._version_manager.compare_versions(ontology_id, v1_id, v2_id)

    def query_at_time(self, ontology_id: str, timestamp: str) -> Dict[str, Any]:
        result = self._version_manager.query_at_time(ontology_id, timestamp)
        if not result:
            return {"status": "error", "message": "No version found at specified time"}
        return result

    def validate(self, type_def: Dict[str, Any], properties: Dict[str, Any] = None) -> Dict[str, Any]:
        type_result = self._validation_engine.validate_entity_type(type_def)
        if properties:
            instance_result = self._validation_engine.validate_instance(type_def, properties)
            return {
                "type_validation": type_result,
                "instance_validation": instance_result,
                "is_valid": type_result.get("is_valid", False) and instance_result.get("is_valid", False),
            }
        return type_result

    def record_audit(self, entity_type_id: str, source: str, process_steps: list, transform_rules: list, result: str) -> Dict[str, Any]:
        return self._audit_recorder.record_ingest(entity_type_id, source, process_steps, transform_rules, result)

    def record_ingest_audit(self, entity_type_id: str, source: str, process_steps: list, transform_rules: list, result: str, source_type: str = "", process_details: list = None, transform_details: list = None) -> Dict[str, Any]:
        return self._audit_recorder.record_ingest_audit(entity_type_id, source, process_steps, transform_rules, result, source_type, process_details, transform_details)

    def get_audit(self, audit_id: str) -> Dict[str, Any]:
        result = self._audit_recorder.get_audit(audit_id)
        if not result:
            return {"status": "error", "message": "Audit record not found"}
        return result

    def list_audits(self, entity_type_id: str = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        results = self._audit_recorder.list_audits(entity_type_id, page, page_size)
        return {"audits": results, "page": page, "page_size": page_size}

    def list_audits_filtered(self, entity_type_id: str = None, source: str = None, source_type: str = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        results = self._audit_recorder.list_audits_filtered(entity_type_id, source, source_type, page, page_size)
        return {"audits": results, "page": page, "page_size": page_size}
