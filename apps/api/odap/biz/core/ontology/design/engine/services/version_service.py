"""VersionService 版本管理服务（设计引擎 domain）

负责 ontology 版本的 CRUD + 回滚 + 时间点查询 + 版本对比
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from odap.infra.security.audit_helper import storage_audit

from ..impl.version_manager_impl import VersionManagerImpl

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


class VersionService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._version_manager = VersionManagerImpl()
        self._initialized = True

    def create_version(self, ontology_id: str, changelog: str, valid_time: str = "", snapshot: Dict[str, Any] = None) -> Dict[str, Any]:
        action = "version.create_version"
        try:
            if not ontology_id:
                _audit_failure(action, msg="ontology_id required",
                                details={"ontology_id_len": 0})
                return {"status": "error", "message": "ontology_id required"}
            result = self._version_manager.create_version(ontology_id, changelog, valid_time, snapshot)
            version_id = (result or {}).get("id") or (result or {}).get("version_id") or ""
            _audit_success(action, resource=version_id or ontology_id,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "version_id": version_id,
                                     "changelog_len": len(changelog or ""),
                                     "has_snapshot": bool(snapshot)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"ontology_id_len": len(ontology_id or "")})
            return {"status": "error", "message": f"create_version failed: {exc}"}

    def save_snapshot(self, version_id: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """为指定版本写入快照数据"""
        action = "version.save_snapshot"
        try:
            if not version_id:
                _audit_failure(action, msg="version_id required",
                                details={"version_id": ""})
                return {"status": "error", "message": "version_id required"}
            snapshot_size = len(str(snapshot or {}))
            result = self._version_manager.save_snapshot(version_id, snapshot)
            _audit_success(action, resource=version_id,
                            details={"version_id": version_id,
                                     "snapshot_size": snapshot_size,
                                     "key_count": len(list(snapshot.keys())) if snapshot else 0})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=version_id,
                            details={"version_id": version_id})
            return {"status": "error", "message": f"save_snapshot failed: {exc}"}

    def get_version(self, ontology_id: str, version_id: str) -> Dict[str, Any]:
        action = "version.get_version"
        try:
            if not version_id:
                _audit_failure(action, msg="version_id required",
                                details={"ontology_id_len": len(ontology_id or "")})
                return {"status": "error", "message": "version_id required"}
            result = self._version_manager.get_version(ontology_id, version_id)
            if not result:
                _audit_failure(action, msg="version not found", resource=version_id,
                                details={"ontology_id_len": len(ontology_id or ""),
                                         "version_id": version_id})
                return {"status": "error", "message": "version not found"}
            _audit_success(action, resource=version_id,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "version_id": version_id})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=version_id,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "version_id": version_id})
            return {"status": "error", "message": f"get_version failed: {exc}"}

    def list_versions(self, ontology_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        action = "version.list_versions"
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

    def delete_version(self, version_id: str) -> Dict[str, Any]:
        """破坏性操作：版本删除，必记审计"""
        action = "version.delete_version"
        try:
            if not version_id:
                _audit_failure(action, msg="version_id required", details={"version_id": ""})
                return {"status": "error", "message": "version_id required"}
            result = self._version_manager.delete_version(version_id)
            if isinstance(result, dict) and result.get("status") == "error":
                _audit_failure(action, msg=result.get("message", "delete error"),
                                resource=version_id, details={"version_id": version_id})
                return result
            deleted = bool(result)
            _audit_success(action, resource=version_id,
                            details={"version_id": version_id, "deleted": deleted})
            return {"status": "ok", "deleted": deleted}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=version_id,
                            details={"version_id": version_id})
            return {"status": "error", "message": f"delete_version failed: {exc}"}

    def rollback_version(self, ontology_id: str, target_version_id: str) -> Dict[str, Any]:
        """破坏性操作：版本回滚"""
        action = "version.rollback_version"
        try:
            result = self._version_manager.rollback_version(ontology_id, target_version_id)
            if isinstance(result, dict) and result.get("status") == "error":
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
        action = "version.compare_versions"
        try:
            result = self._version_manager.compare_versions(ontology_id, v1_id, v2_id)
            diff_count = len(result.get("diff", [])) if isinstance(result, dict) else 0
            _audit_success(action,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "v1_id": v1_id,
                                     "v2_id": v2_id,
                                     "diff_count": diff_count})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "v1_id": v1_id, "v2_id": v2_id})
            return {"status": "error", "message": f"compare_versions failed: {exc}"}

    def query_at_time(self, ontology_id: str, timestamp: str) -> Dict[str, Any]:
        action = "version.query_at_time"
        try:
            if not timestamp:
                _audit_failure(action, msg="timestamp required",
                                details={"ontology_id_len": len(ontology_id or "")})
                return {"status": "error", "message": "timestamp required"}
            result = self._version_manager.query_at_time(ontology_id, timestamp)
            if not result:
                _audit_failure(action, msg="no version found at specified time",
                                details={"ontology_id_len": len(ontology_id or ""),
                                         "timestamp_len": len(timestamp or "")})
                return {"status": "error", "message": "no version found at specified time"}
            _audit_success(action,
                            details={"ontology_id_len": len(ontology_id or ""),
                                     "timestamp_len": len(timestamp or ""),
                                     "has_result": bool(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"ontology_id_len": len(ontology_id or "")})
            return {"status": "error", "message": f"query_at_time failed: {exc}"}

    def list_all_versions(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        action = "version.list_all_versions"
        try:
            results = self._version_manager.list_all_versions(page, page_size)
            _audit_success(action,
                            details={"count": len(results or []),
                                     "page": page,
                                     "page_size": page_size})
            return {"versions": results, "page": page, "page_size": page_size}
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"list_all_versions failed: {exc}"}
