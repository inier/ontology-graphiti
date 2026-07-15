"""IncrementalComputer (T395)

DAG 反向传播：
- 当依赖属性变化时，仅重算受影响对象
- 通过 DependencyTracker 找到下游属性
- 批量调度 MaterializationJob
- 记录 processed_count + error_message

支持两种重算模式：
- full: 重新计算 target property + 所有下游
- incremental: 仅当下游属性真正依赖 changed 时才重算
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .dependency_tracker import DependencyTracker
from ..interfaces import EvaluationContext, ExpressionEvaluator
from ..models import (
    ComputedProperty,
    JobTrigger,
    MaterializationJob,
    MaterializationStatus,
)
from ..storage import SQLiteComputedStorage

logger = logging.getLogger(__name__)


class IncrementalComputer:
    """增量物化调度器"""

    def __init__(
        self,
        tracker: DependencyTracker,
        evaluator: ExpressionEvaluator,
        storage: SQLiteComputedStorage,
        instance_provider: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
    ):
        self.tracker = tracker
        self.evaluator = evaluator
        self.storage = storage
        self._instance_provider = instance_provider or _default_instance_provider

    def trigger_recompute(
        self,
        target_property: ComputedProperty,
        mode: str = "incremental",
        triggered_by: JobTrigger = JobTrigger.MANUAL,
        changed_property_id: Optional[str] = None,
    ) -> List[MaterializationJob]:
        """触发重算：返回创建的 MaterializationJob 列表

        - mode='full': 仅 target property
        - mode='incremental': target + downstream
        """
        if mode not in ("full", "incremental"):
            raise ValueError("mode must be 'full' or 'incremental'")
        affected = self._collect_affected(target_property, mode, changed_property_id)
        jobs: List[MaterializationJob] = []
        for prop in affected:
            job = self._materialize_one(prop, mode, triggered_by)
            jobs.append(job)
        return jobs

    def _collect_affected(
        self,
        target_property: ComputedProperty,
        mode: str,
        changed_property_id: Optional[str],
    ) -> List[ComputedProperty]:
        """收集受影响的 ComputedProperty 列表（按拓扑序）"""
        target = self.storage.get_property(target_property.id)
        if not target:
            return [target_property]
        props = [self._to_model(target)]
        if mode == "incremental" and changed_property_id:
            downstream = self.tracker.get_downstream(changed_property_id)
            for d_id in downstream:
                row = self.storage.get_property(d_id)
                if row:
                    props.append(self._to_model(row))
        return props

    def _materialize_one(
        self,
        prop: ComputedProperty,
        mode: str,
        triggered_by: JobTrigger,
    ) -> MaterializationJob:
        """物化单个 ComputedProperty；返回 MaterializationJob"""
        job = self._init_materialization_job(prop, mode, triggered_by)
        try:
            instances = self._instance_provider(prop.target_type_id)
            processed = self._run_instance_loop(prop, instances)
            self._mark_job_done(job, processed)
        except Exception as exc:
            logger.exception("materialize property %s failed", prop.id)
            self._mark_job_failed(job, exc)
        self.storage.save_job(self._job_to_dict(job))
        return job

    def _init_materialization_job(
        self,
        prop: ComputedProperty,
        mode: str,
        triggered_by: JobTrigger,
    ) -> MaterializationJob:
        """创建并持久化一个 RUNNING 状态的 MaterializationJob"""
        job = MaterializationJob(
            property_id=prop.id,
            status=MaterializationStatus.RUNNING,
            started_at=datetime.now(),
            processed_count=0,
            error_message="",
            triggered_by=triggered_by,
            mode=mode,
        )
        self.storage.save_job(self._job_to_dict(job))
        return job

    def _run_instance_loop(
        self, prop: ComputedProperty, instances: List[Dict[str, Any]]
    ) -> int:
        """对每个实例执行表达式并持久化结果；返回成功处理数"""
        processed = 0
        for inst in instances:
            if self._process_single_instance(prop, inst):
                processed += 1
        return processed

    def _process_single_instance(
        self, prop: ComputedProperty, inst: Dict[str, Any]
    ) -> bool:
        """对单个实例求值并保存；失败不中断批量；返回是否成功"""
        try:
            value = self.evaluator.evaluate(
                prop.expression,
                EvaluationContext(
                    instance=inst.get("data", inst),
                    properties=inst.get("data", inst),
                ),
            )
            self.storage.save_materialized_value(
                prop.id,
                inst.get("id", ""),
                value,
                datetime.now().isoformat(),
            )
            return True
        except Exception as exc:  # 单实例失败不中断批量
            logger.warning(
                "materialize instance %s failed: %s",
                inst.get("id", ""),
                exc,
            )
            return False

    @staticmethod
    def _mark_job_done(job: MaterializationJob, processed: int) -> None:
        """将 job 标记为 DONE 并记录处理数"""
        job.status = MaterializationStatus.DONE
        job.processed_count = processed
        job.finished_at = datetime.now()

    @staticmethod
    def _mark_job_failed(job: MaterializationJob, exc: Exception) -> None:
        """将 job 标记为 FAILED 并记录异常信息"""
        job.status = MaterializationStatus.FAILED
        job.error_message = str(exc)
        job.finished_at = datetime.now()

    def get_downstream_chain(
        self, changed_property_id: str
    ) -> List[str]:
        """仅返回受 changed_property_id 影响的属性 ID 列表（不含自身）"""
        return self.tracker.get_downstream(changed_property_id)

    @staticmethod
    def _to_model(row: Dict[str, Any]) -> ComputedProperty:
        """持久化 dict → ComputedProperty"""
        from ..models import MaterializationType
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


def _default_instance_provider(
    target_type_id: str
) -> List[Dict[str, Any]]:
    """默认 instance 提供器：返回空列表（无外部数据源时安全降级）"""
    return []


__all__ = ["IncrementalComputer"]
