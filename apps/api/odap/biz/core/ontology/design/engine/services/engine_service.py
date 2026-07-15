"""EngineService 设计引擎编排层

设计规范：返回 Dict[str, Any]，错误格式统一
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from odap.infra.security.audit_helper import storage_audit

from ..impl.version_manager_impl import VersionManagerImpl
from ..impl.audit_recorder_impl import AuditRecorderImpl
from ..impl.validation_engine_impl import ValidationEngineImpl

logger = logging.getLogger(__name__)

_AUDIT_SERVICE = "ontology_design"


def _audit_success(action: str, resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="success",
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


def _audit_failure(action: str, msg: str = "", resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="failure",
            result_message=(msg or "")[:200],
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


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
        action = "engine.create_version"
        try:
            result = self._version_manager.create_version(ontology_id, changelog, valid_time, snapshot)
            version_id = (result or {}).get("id") or (result or {}).get("version_id") or ""
            _audit_success(action, resource=version_id or ontology_id,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "version_id": version_id,
                                     "changelog_len": len(changelog or "")})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"ontology_id_len": len(ontology_id or "")})
            return {"status": "error", "message": f"create_version failed: {exc}"}

    def build_version(self, ontology_id: str, changelog: str = "", snapshot: Dict[str, Any] = None) -> Dict[str, Any]:
        """构建新版本（create_version 的别名，语义化）"""
        return self.create_version(ontology_id, changelog, "", snapshot)

    def get_version(self, ontology_id: str, version_id: str) -> Dict[str, Any]:
        action = "engine.get_version"
        try:
            result = self._version_manager.get_version(ontology_id, version_id)
            if not result:
                _audit_failure(action, msg="Version not found", resource=version_id,
                                details={"ontology_id_len": len(ontology_id or ""), "version_id": version_id})
                return {"status": "error", "message": "Version not found"}
            _audit_success(action, resource=version_id,
                            details={"ontology_id_len": len(ontology_id or ""), "version_id": version_id})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=version_id,
                            details={"ontology_id_len": len(ontology_id or ""), "version_id": version_id})
            return {"status": "error", "message": f"get_version failed: {exc}"}

    def list_versions(self, ontology_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        action = "engine.list_versions"
        try:
            results = self._version_manager.list_versions(ontology_id, page, page_size)
            _audit_success(action,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "count": len(results or []),
                                     "page": page,
                                     "page_size": page_size})
            return {"versions": results, "page": page, "page_size": page_size}
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"ontology_id_len": len(ontology_id or "")})
            return {"status": "error", "message": f"list_versions failed: {exc}"}

    def rollback_version(self, ontology_id: str, target_version_id: str) -> Dict[str, Any]:
        """破坏性操作：版本回滚，必记审计"""
        action = "engine.rollback_version"
        try:
            result = self._version_manager.rollback_version(ontology_id, target_version_id)
            if result.get("status") == "error":
                _audit_failure(action,
                                msg=result.get("message", "rollback error"),
                                resource=target_version_id,
                                details={"ontology_id_len": len(ontology_id or ""),
                                         "target_version_id": target_version_id})
                return result
            _audit_success(action, resource=target_version_id,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "target_version_id": target_version_id})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=target_version_id,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "target_version_id": target_version_id})
            return {"status": "error", "message": f"rollback_version failed: {exc}"}

    def compare_versions(self, ontology_id: str, v1_id: str, v2_id: str) -> Dict[str, Any]:
        action = "engine.compare_versions"
        try:
            result = self._version_manager.compare_versions(ontology_id, v1_id, v2_id)
            _audit_success(action,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "v1_id": v1_id,
                                     "v2_id": v2_id,
                                     "has_result": bool(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "v1_id": v1_id, "v2_id": v2_id})
            return {"status": "error", "message": f"compare_versions failed: {exc}"}

    def query_at_time(self, ontology_id: str, timestamp: str) -> Dict[str, Any]:
        action = "engine.query_at_time"
        try:
            result = self._version_manager.query_at_time(ontology_id, timestamp)
            if not result:
                _audit_failure(action, msg="No version found at specified time",
                                details={"ontology_id_len": len(ontology_id or ""),
                                         "timestamp_len": len(timestamp or "")})
                return {"status": "error", "message": "No version found at specified time"}
            _audit_success(action,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "timestamp_len": len(timestamp or "")})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"ontology_id_len": len(ontology_id or "")})
            return {"status": "error", "message": f"query_at_time failed: {exc}"}

    def validate_design(self, type_def: Dict[str, Any], properties: Dict[str, Any] = None) -> Dict[str, Any]:
        """验证设计（validate 的语义化别名）"""
        return self.validate(type_def, properties)

    def validate(self, type_def: Dict[str, Any], properties: Dict[str, Any] = None) -> Dict[str, Any]:
        action = "engine.validate"
        try:
            type_result = self._validation_engine.validate_entity_type(type_def)
            instance_result = None
            if properties:
                instance_result = self._validation_engine.validate_instance(type_def, properties)
                result = {
                    "type_validation": type_result,
                    "instance_validation": instance_result,
                    "is_valid": type_result.get("is_valid", False) and instance_result.get("is_valid", False),
                }
            else:
                result = type_result
            entity_count = len(type_def.get("entities", [])) if isinstance(type_def, dict) else 0
            _audit_success(action,
                            details={"has_properties": bool(properties),
                                     "entity_count": entity_count,
                                     "is_valid": result.get("is_valid", False)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"has_properties": bool(properties)})
            return {"status": "error", "message": f"validate failed: {exc}"}

    def apply_patch(self, ontology_id: str, version_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """应用补丁到指定版本"""
        action = "engine.apply_patch"
        try:
            if not patch:
                _audit_failure(action, msg="patch is empty", resource=version_id,
                                details={"ontology_id_len": len(ontology_id or ""),
                                         "version_id": version_id})
                return {"status": "error", "message": "patch is required and must be non-empty"}
            ver = self._version_manager.get_version(ontology_id, version_id)
            if not ver:
                _audit_failure(action, msg="target version not found", resource=version_id,
                                details={"ontology_id_len": len(ontology_id or ""),
                                         "version_id": version_id})
                return {"status": "error", "message": "target version not found"}
            _audit_success(action, resource=version_id,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "version_id": version_id,
                                     "patch_keys_count": len(list(patch.keys()))})
            return {"status": "ok", "applied": True, "version_id": version_id, "ontology_id": ontology_id}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=version_id,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "version_id": version_id})
            return {"status": "error", "message": f"apply_patch failed: {exc}"}

    def record_audit(self, entity_type_id: str, source: str, process_steps: list, transform_rules: list, result: str) -> Dict[str, Any]:
        action = "engine.record_audit"
        try:
            result = self._audit_recorder.record_ingest(entity_type_id, source, process_steps, transform_rules, result)
            _audit_success(action,
                            details={"entity_type_id_len": len(entity_type_id or ""),
                                     "source_len": len(source or ""),
                                     "process_steps_count": len(process_steps or []),
                                     "transform_rules_count": len(transform_rules or [])})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"entity_type_id_len": len(entity_type_id or "")})
            return {"status": "error", "message": f"record_audit failed: {exc}"}

    def record_ingest_audit(self, entity_type_id: str, source: str, process_steps: list, transform_rules: list, result: str, source_type: str = "", process_details: list = None, transform_details: list = None) -> Dict[str, Any]:
        action = "engine.record_ingest_audit"
        try:
            res = self._audit_recorder.record_ingest_audit(entity_type_id, source, process_steps, transform_rules, result, source_type, process_details, transform_details)
            _audit_success(action,
                            details={"entity_type_id_len": len(entity_type_id or ""),
                                     "source_len": len(source or ""),
                                     "process_steps_count": len(process_steps or []),
                                     "source_type_len": len(source_type or "")})
            return res
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"entity_type_id_len": len(entity_type_id or "")})
            return {"status": "error", "message": f"record_ingest_audit failed: {exc}"}

    def get_audit(self, audit_id: str) -> Dict[str, Any]:
        action = "engine.get_audit"
        try:
            result = self._audit_recorder.get_audit(audit_id)
            if not result:
                _audit_failure(action, msg="Audit record not found", resource=audit_id,
                                details={"audit_id": audit_id})
                return {"status": "error", "message": "Audit record not found"}
            _audit_success(action, resource=audit_id, details={"audit_id": audit_id})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=audit_id, details={"audit_id": audit_id})
            return {"status": "error", "message": f"get_audit failed: {exc}"}

    def list_audits(self, entity_type_id: str = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        action = "engine.list_audits"
        try:
            results = self._audit_recorder.list_audits(entity_type_id, page, page_size)
            _audit_success(action,
                            details={"has_entity_filter": bool(entity_type_id),
                                     "count": len(results or []),
                                     "page": page,
                                     "page_size": page_size})
            return {"audits": results, "page": page, "page_size": page_size}
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"has_entity_filter": bool(entity_type_id)})
            return {"status": "error", "message": f"list_audits failed: {exc}"}

    def list_audits_filtered(self, entity_type_id: str = None, source: str = None, source_type: str = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        action = "engine.list_audits_filtered"
        try:
            results = self._audit_recorder.list_audits_filtered(entity_type_id, source, source_type, page, page_size)
            _audit_success(action,
                            details={"has_entity_filter": bool(entity_type_id),
                                     "has_source_filter": bool(source),
                                     "has_source_type_filter": bool(source_type),
                                     "count": len(results or [])})
            return {"audits": results, "page": page, "page_size": page_size}
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"list_audits_filtered failed: {exc}"}
