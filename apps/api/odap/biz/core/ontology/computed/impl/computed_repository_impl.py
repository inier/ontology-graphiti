"""ComputedRepositoryImpl

实现 ComputedRepository 抽象基类，依赖 SQLiteComputedStorage 持久化。
Domain Object ↔ dict 转换在这里完成。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from odap.infra.security.audit_helper import storage_audit

from ..interfaces import ComputedRepository
from ..models import (
    ComputedProperty,
    JobTrigger,
    MaterializationJob,
    MaterializationStatus,
    MaterializationType,
)
from ..storage import SQLiteComputedStorage

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


class ComputedRepositoryImpl(ComputedRepository):
    """Computed Property 仓储实现（基于 SQLite）"""

    def __init__(self, storage: SQLiteComputedStorage = None):
        self.storage = storage or SQLiteComputedStorage()

    # ---------- ComputedProperty CRUD ----------

    def save_property(self, prop: ComputedProperty) -> ComputedProperty:
        """保存或更新 ComputedProperty（upsert）"""
        action = "computed_repo.save_property"
        try:
            prop.updated_at = datetime.now()
            self.storage.save_property(self._prop_to_dict(prop))
            _audit_success(action, resource=prop.id,
                            details={"property_id": prop.id,
                                     "enabled": prop.enabled,
                                     "dependency_count": len(prop.dependencies or [])})
            return prop
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=prop.id,
                            details={"property_id": getattr(prop, "id", "")})
            raise

    def get_property(self, prop_id: str) -> Optional[ComputedProperty]:
        """根据 ID 获取"""
        action = "computed_repo.get_property"
        try:
            row = self.storage.get_property(prop_id)
            _audit_success(action, resource=prop_id,
                            details={"property_id": prop_id,
                                     "found": bool(row)})
            return self._dict_to_prop(row) if row else None
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=prop_id,
                            details={"property_id": prop_id})
            raise

    def list_properties(
        self,
        target_type_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[ComputedProperty]:
        """列出 ComputedProperty；可按 target_type / enabled 过滤"""
        action = "computed_repo.list_properties"
        try:
            rows = self.storage.list_properties(
                target_type_id=target_type_id,
                enabled_only=enabled_only,
            )
            _audit_success(action,
                            details={"has_target_type_filter": bool(target_type_id),
                                     "enabled_only": enabled_only,
                                     "count": len(rows)})
            return [self._dict_to_prop(r) for r in rows]
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"has_target_type_filter": bool(target_type_id),
                                     "enabled_only": enabled_only})
            raise

    def delete_property(self, prop_id: str) -> bool:
        """删除 ComputedProperty；返回是否成功"""
        action = "computed_repo.delete_property"
        try:
            result = self.storage.delete_property(prop_id)
            _audit_success(action, resource=prop_id,
                            details={"property_id": prop_id,
                                     "deleted": bool(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=prop_id,
                            details={"property_id": prop_id})
            raise

    # ---------- MaterializationJob ----------

    def save_job(self, job: MaterializationJob) -> MaterializationJob:
        """保存 MaterializationJob（upsert）"""
        action = "computed_repo.save_job"
        try:
            self.storage.save_job(self._job_to_dict(job))
            _audit_success(action, resource=job.id,
                            details={"job_id": job.id,
                                     "property_id": job.property_id,
                                     "status": job.status.value,
                                     "processed_count": job.processed_count})
            return job
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"job_id": getattr(job, "id", "")})
            raise

    def get_job(self, job_id: str) -> Optional[MaterializationJob]:
        """根据 ID 获取 MaterializationJob；不存在返回 None"""
        action = "computed_repo.get_job"
        try:
            row = self.storage.get_job(job_id)
            _audit_success(action, resource=job_id,
                            details={"job_id": job_id,
                                     "found": bool(row)})
            return self._dict_to_job(row) if row else None
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=job_id,
                            details={"job_id": job_id})
            raise

    def list_jobs(
        self, property_id: str, limit: int = 50
    ) -> List[MaterializationJob]:
        """列出某 ComputedProperty 的最近 N 个任务"""
        action = "computed_repo.list_jobs"
        try:
            rows = self.storage.list_jobs(property_id, limit=limit)
            _audit_success(action,
                            details={"property_id": property_id,
                                     "count": len(rows),
                                     "limit": limit})
            return [self._dict_to_job(r) for r in rows]
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"property_id": property_id})
            raise

    # ---------- Materialized Values ----------

    def save_materialized_value(
        self,
        property_id: str,
        instance_id: str,
        value: Any,
        computed_at_iso: str,
    ) -> None:
        """保存物化值（upsert by (property_id, instance_id)）"""
        action = "computed_repo.save_materialized_value"
        try:
            self.storage.save_materialized_value(
                property_id, instance_id, value, computed_at_iso
            )
            _audit_success(action,
                            details={"property_id": property_id,
                                     "instance_id_len": len(instance_id or ""),
                                     "has_value": value is not None})
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"property_id": property_id,
                                     "instance_id_len": len(instance_id or "")})
            raise

    def get_materialized_value(
        self, property_id: str, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取物化值；不存在返回 None"""
        action = "computed_repo.get_materialized_value"
        try:
            result = self.storage.get_materialized_value(property_id, instance_id)
            _audit_success(action,
                            details={"property_id": property_id,
                                     "instance_id_len": len(instance_id or ""),
                                     "found": bool(result)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"property_id": property_id})
            raise

    def list_materialized_values(
        self, property_id: str, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """列出某 ComputedProperty 的所有物化值"""
        action = "computed_repo.list_materialized_values"
        try:
            result = self.storage.list_materialized_values(
                property_id, limit=limit
            )
            _audit_success(action,
                            details={"property_id": property_id,
                                     "count": len(result),
                                     "limit": limit})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"property_id": property_id})
            raise

    def delete_materialized_values(self, property_id: str) -> int:
        """删除某 ComputedProperty 的全部物化值；返回删除条数"""
        action = "computed_repo.delete_materialized_values"
        try:
            count = self.storage.delete_materialized_values(property_id)
            _audit_success(action,
                            details={"property_id": property_id,
                                     "deleted_count": int(count or 0)})
            return count
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                            details={"property_id": property_id})
            raise

    # ---------- 内部转换工具 ----------

    @staticmethod
    def _prop_to_dict(prop: ComputedProperty) -> Dict[str, Any]:
        """ComputedProperty → 持久化 dict"""
        return {
            "id": prop.id,
            "name": prop.name,
            "target_type_id": prop.target_type_id,
            "expression": prop.expression,
            "dependencies": list(prop.dependencies or []),
            "materialization": prop.materialization.value,
            "return_type": prop.return_type,
            "description": prop.description,
            "enabled": prop.enabled,
            "created_at": prop.created_at.isoformat(),
            "updated_at": prop.updated_at.isoformat(),
        }

    @staticmethod
    def _dict_to_prop(row: Dict[str, Any]) -> ComputedProperty:
        """持久化 dict → ComputedProperty"""
        return ComputedProperty(
            id=row.get("id", ""),
            name=row.get("name", ""),
            target_type_id=row.get("target_type_id", ""),
            expression=row.get("expression", ""),
            dependencies=row.get("dependencies", []) or [],
            materialization=MaterializationType(
                row.get("materialization", "incremental")
            ),
            return_type=row.get("return_type", "any"),
            description=row.get("description", "") or "",
            enabled=bool(row.get("enabled", True)),
            created_at=_parse_dt(row.get("created_at")) or datetime.now(),
            updated_at=_parse_dt(row.get("updated_at")) or datetime.now(),
        )

    @staticmethod
    def _job_to_dict(job: MaterializationJob) -> Dict[str, Any]:
        """MaterializationJob → 持久化 dict"""
        finished = job.finished_at
        return {
            "id": job.id,
            "property_id": job.property_id,
            "status": job.status.value,
            "started_at": job.started_at.isoformat(),
            "finished_at": finished.isoformat() if finished else None,
            "processed_count": job.processed_count,
            "error_message": job.error_message,
            "triggered_by": job.triggered_by.value,
            "mode": job.mode,
        }

    @staticmethod
    def _dict_to_job(row: Dict[str, Any]) -> MaterializationJob:
        """持久化 dict → MaterializationJob"""
        finished_raw = row.get("finished_at")
        finished = _parse_dt(finished_raw) if finished_raw else None
        triggered_raw = row.get("triggered_by", "manual")
        try:
            triggered = JobTrigger(triggered_raw)
        except ValueError:
            triggered = JobTrigger.MANUAL
        return MaterializationJob(
            id=row.get("id", ""),
            property_id=row.get("property_id", ""),
            status=MaterializationStatus(row.get("status", "pending")),
            started_at=_parse_dt(row.get("started_at")) or datetime.now(),
            finished_at=finished,
            processed_count=int(row.get("processed_count", 0) or 0),
            error_message=row.get("error_message", "") or "",
            triggered_by=triggered,
            mode=row.get("mode", "incremental"),
        )


def _parse_dt(value: Any):
    """从 ISO 字符串解析 datetime；失败时返回 None"""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


__all__ = ["ComputedRepositoryImpl"]
