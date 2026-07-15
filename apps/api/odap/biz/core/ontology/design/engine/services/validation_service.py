"""ValidationService 设计验证服务

校验类服务：不直接写数据库，主要输出 valid/invalid 与 errors
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from odap.infra.security.audit_helper import storage_audit

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


class ValidationService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._validation_engine = ValidationEngineImpl()
        self._initialized = True

    def validate_entity_type(self, type_def: Dict[str, Any]) -> Dict[str, Any]:
        action = "validation.validate_entity_type"
        resource = type_def.get("id") if isinstance(type_def, dict) else None
        try:
            if not isinstance(type_def, dict):
                _audit_failure(action, msg="type_def must be dict",
                                details={"type_def_type": type(type_def).__name__})
                return {"is_valid": False, "errors": ["type_def must be a dict"]}
            result = self._validation_engine.validate_entity_type(type_def)
            _audit_success(action, resource=resource,
                            details={"type_id": str(type_def.get("id", ""))[:50],
                                     "is_valid": result.get("is_valid", False),
                                     "error_count": len(result.get("errors", []) or [])})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=resource)
            return {"is_valid": False, "errors": [f"validate_entity_type exception: {exc}"]}

    def validate_instance(self, type_def: Dict[str, Any], properties: Dict[str, Any]) -> Dict[str, Any]:
        action = "validation.validate_instance"
        try:
            if not properties:
                _audit_failure(action, msg="properties must be non-empty",
                                details={"properties_count": 0})
                return {"is_valid": False, "errors": ["properties required"]}
            result = self._validation_engine.validate_instance(type_def, properties)
            _audit_success(action,
                            details={"property_count": len(properties or {}),
                                     "is_valid": result.get("is_valid", False),
                                     "error_count": len(result.get("errors", []) or [])})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"property_count": len(properties or {})})
            return {"is_valid": False, "errors": [f"validate_instance exception: {exc}"]}

    def validate_design(self, ontology_id: str, design: Dict[str, Any]) -> Dict[str, Any]:
        """完整设计校验：逐 entity_type 校验并汇总结果"""
        action = "validation.validate_design"
        try:
            if not design:
                _audit_failure(action, msg="design empty",
                                details={"ontology_id_len": len(ontology_id or "")})
                return {"is_valid": False, "errors": ["design required"]}
            types = design.get("entity_types", [])
            overall_errors = []
            type_valid = True
            for t in types:
                r = self.validate_entity_type(t)
                type_valid = type_valid and r.get("is_valid", False)
                overall_errors.extend(r.get("errors", []) or [])
            result = {
                "is_valid": type_valid,
                "entity_type_count": len(types),
                "error_count": len(overall_errors),
                "errors": overall_errors,
            }
            _audit_success(action,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "entity_type_count": len(types),
                                     "is_valid": result["is_valid"],
                                     "error_count": result["error_count"]})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"ontology_id_len": len(ontology_id or "")})
            return {"is_valid": False, "errors": [f"validate_design exception: {exc}"]}

    def batch_validate(self, type_defs: List[Dict[str, Any]]) -> Dict[str, Any]:
        action = "validation.batch_validate"
        try:
            if not type_defs:
                _audit_success(action, details={"count": 0, "is_valid": True, "error_count": 0})
                return {"is_valid": True, "errors": [], "count": 0}
            errors = []
            valid = True
            for t in type_defs:
                r = self.validate_entity_type(t)
                if not r.get("is_valid", False):
                    valid = False
                    errors.extend(r.get("errors", []) or [])
            _audit_success(action,
                            details={"count": len(type_defs),
                                     "is_valid": valid,
                                     "error_count": len(errors)})
            return {"is_valid": valid, "errors": errors, "count": len(type_defs)}
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"count": len(type_defs or [])})
            return {"is_valid": False, "errors": [f"batch_validate exception: {exc}"]}
