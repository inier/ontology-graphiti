"""ComputedRepositoryImpl

实现 ComputedRepository 抽象基类，依赖 SQLiteComputedStorage 持久化。
Domain Object ↔ dict 转换在这里完成。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..interfaces import ComputedRepository
from ..models import (
    ComputedProperty,
    JobTrigger,
    MaterializationJob,
    MaterializationStatus,
    MaterializationType,
)
from ..storage import SQLiteComputedStorage


class ComputedRepositoryImpl(ComputedRepository):
    """Computed Property 仓储实现（基于 SQLite）"""

    def __init__(self, storage: SQLiteComputedStorage = None):
        self.storage = storage or SQLiteComputedStorage()

    # ---------- ComputedProperty CRUD ----------

    def save_property(self, prop: ComputedProperty) -> ComputedProperty:
        """保存或更新 ComputedProperty（upsert）"""
        prop.updated_at = datetime.now()
        self.storage.save_property(self._prop_to_dict(prop))
        return prop

    def get_property(self, prop_id: str) -> Optional[ComputedProperty]:
        """根据 ID 获取"""
        row = self.storage.get_property(prop_id)
        return self._dict_to_prop(row) if row else None

    def list_properties(
        self,
        target_type_id: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[ComputedProperty]:
        """列出 ComputedProperty；可按 target_type / enabled 过滤"""
        rows = self.storage.list_properties(
            target_type_id=target_type_id,
            enabled_only=enabled_only,
        )
        return [self._dict_to_prop(r) for r in rows]

    def delete_property(self, prop_id: str) -> bool:
        """删除 ComputedProperty；返回是否成功"""
        return self.storage.delete_property(prop_id)

    # ---------- MaterializationJob ----------

    def save_job(self, job: MaterializationJob) -> MaterializationJob:
        """保存 MaterializationJob（upsert）"""
        self.storage.save_job(self._job_to_dict(job))
        return job

    def get_job(self, job_id: str) -> Optional[MaterializationJob]:
        """根据 ID 获取 MaterializationJob；不存在返回 None"""
        row = self.storage.get_job(job_id)
        return self._dict_to_job(row) if row else None

    def list_jobs(
        self, property_id: str, limit: int = 50
    ) -> List[MaterializationJob]:
        """列出某 ComputedProperty 的最近 N 个任务"""
        rows = self.storage.list_jobs(property_id, limit=limit)
        return [self._dict_to_job(r) for r in rows]

    # ---------- Materialized Values ----------

    def save_materialized_value(
        self,
        property_id: str,
        instance_id: str,
        value: Any,
        computed_at_iso: str,
    ) -> None:
        """保存物化值（upsert by (property_id, instance_id)）"""
        self.storage.save_materialized_value(
            property_id, instance_id, value, computed_at_iso
        )

    def get_materialized_value(
        self, property_id: str, instance_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取物化值；不存在返回 None"""
        return self.storage.get_materialized_value(property_id, instance_id)

    def list_materialized_values(
        self, property_id: str, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """列出某 ComputedProperty 的所有物化值"""
        return self.storage.list_materialized_values(
            property_id, limit=limit
        )

    def delete_materialized_values(self, property_id: str) -> int:
        """删除某 ComputedProperty 的全部物化值；返回删除条数"""
        return self.storage.delete_materialized_values(property_id)

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
