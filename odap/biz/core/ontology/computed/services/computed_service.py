"""ComputedService 编排层 (T397)

服务层规范（AGENTS.md 规则 2）：
- 必须返回 Dict[str, Any]，禁止抛 HTTPException
- 错误格式: {"status": "error", "message": "..."}
- 成功格式: 扁平 dict
- 类型转换: Enum→.value, datetime→.isoformat(), BaseModel→扁平 dict

主要职责：
- CRUD: create / get / list / update / delete ComputedProperty
- 评估: evaluate(property_id, instance_id, instance_data) -> value
- 物化: trigger_recompute(property_id, mode="full"|"incremental") -> job_id
- 状态: get_job_status / list_jobs
- 依赖追踪 + 增量反向传播
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..impl import (
    ComputedRepositoryImpl,
    DependencyTracker,
    IncrementalComputer,
    SafeExpressionEvaluator,
)
from ..interfaces import EvaluationContext, ExpressionEvaluator
from ..models import (
    ComputedProperty,
    JobTrigger,
    MaterializationJob,
    MaterializationStatus,
    MaterializationType,
)
from ..storage import SQLiteComputedStorage

logger = logging.getLogger(__name__)


class ComputedService:
    """Computed Property 编排服务"""

    def __init__(
        self,
        repository: ComputedRepositoryImpl = None,
        evaluator: ExpressionEvaluator = None,
        tracker: DependencyTracker = None,
        storage: SQLiteComputedStorage = None,
    ):
        self.storage = storage or SQLiteComputedStorage()
        self.repository = repository or ComputedRepositoryImpl(storage=self.storage)
        self.evaluator = evaluator or SafeExpressionEvaluator()
        self.tracker = tracker or DependencyTracker()
        self._computer = IncrementalComputer(
            tracker=self.tracker,
            evaluator=self.evaluator,
            storage=self.storage,
        )

    # ---------- ComputedProperty CRUD ----------

    def create_property(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建 ComputedProperty；自动提取依赖并注册到 DependencyTracker"""
        try:
            prop = self._build_property(payload, new_id=True)
            deps = self._resolve_dependencies(prop)
            prop.dependencies = deps
            self.repository.save_property(prop)
            self.tracker.add_property(prop.id, deps)
            return self._prop_to_dict(prop)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "message": f"create_property failed: {exc}"}

    def get_property(self, prop_id: str) -> Dict[str, Any]:
        """获取 ComputedProperty"""
        try:
            prop = self.repository.get_property(prop_id)
            if not prop:
                return {"status": "error", "message": f"property not found: {prop_id}"}
            return self._prop_to_dict(prop)
        except Exception as exc:
            return {"status": "error", "message": f"get_property failed: {exc}"}

    def list_properties(
        self,
        target_type: Optional[str] = None,
        enabled_only: bool = False,
    ) -> Dict[str, Any]:
        """列出 ComputedProperty；支持 target_type / enabled_only 过滤"""
        try:
            items = self.repository.list_properties(
                target_type_id=target_type,
                enabled_only=enabled_only,
            )
            return {
                "properties": [self._prop_to_dict(p) for p in items],
                "count": len(items),
            }
        except Exception as exc:
            return {"status": "error", "message": f"list_properties failed: {exc}"}

    def update_property(
        self, prop_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新 ComputedProperty（部分字段）"""
        try:
            existing = self.repository.get_property(prop_id)
            if not existing:
                return {"status": "error", "message": f"property not found: {prop_id}"}
            merged = self._merge_property(existing, payload)
            if payload.get("expression") and payload["expression"] != existing.expression:
                merged.dependencies = self._resolve_dependencies(merged)
            merged.updated_at = datetime.now()
            self.repository.save_property(merged)
            self.tracker.add_property(merged.id, merged.dependencies)
            return self._prop_to_dict(merged)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "message": f"update_property failed: {exc}"}

    def delete_property(self, prop_id: str) -> Dict[str, Any]:
        """删除 ComputedProperty；级联删除物化值"""
        try:
            ok = self.repository.delete_property(prop_id)
            if not ok:
                return {"status": "error", "message": f"property not found: {prop_id}"}
            self.storage.delete_materialized_values(prop_id)
            self.tracker.remove_property(prop_id)
            return {"property_id": prop_id, "deleted": True}
        except Exception as exc:
            return {"status": "error", "message": f"delete_property failed: {exc}"}

    # ---------- 评估 ----------

    def evaluate_property(
        self,
        prop_id: str,
        instance_id: str,
        instance_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """对单实例求值（不写库）"""
        try:
            prop = self.repository.get_property(prop_id)
            if not prop:
                return {"status": "error", "message": f"property not found: {prop_id}"}
            ctx = EvaluationContext(
                instance=instance_data or {},
                properties=instance_data or {},
            )
            value = self.evaluator.evaluate(prop.expression, ctx)
            return {
                "property_id": prop_id,
                "instance_id": instance_id,
                "value": value,
            }
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "message": f"evaluate_property failed: {exc}"}

    # ---------- 物化 ----------

    def trigger_recompute(
        self,
        prop_id: str,
        mode: str = "incremental",
        changed_property_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """触发重算；返回首个 job_id + 受影响属性数"""
        try:
            if mode not in ("full", "incremental"):
                return {"status": "error", "message": "mode must be 'full' or 'incremental'"}
            target = self.repository.get_property(prop_id)
            if not target:
                return {"status": "error", "message": f"property not found: {prop_id}"}
            jobs = self._computer.trigger_recompute(
                target_property=target,
                mode=mode,
                triggered_by=JobTrigger.MANUAL,
                changed_property_id=changed_property_id,
            )
            return {
                "mode": mode,
                "affected": [j.property_id for j in jobs],
                "job_ids": [j.id for j in jobs],
                "first_job_id": jobs[0].id if jobs else None,
            }
        except Exception as exc:
            logger.exception("trigger_recompute failed")
            return {"status": "error", "message": f"trigger_recompute failed: {exc}"}

    # ---------- 任务状态 ----------

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """根据 ID 获取 MaterializationJob"""
        try:
            job = self.repository.get_job(job_id)
            if not job:
                return {"status": "error", "message": f"job not found: {job_id}"}
            return self._job_to_dict(job)
        except Exception as exc:
            return {"status": "error", "message": f"get_job_status failed: {exc}"}

    def list_jobs(
        self, prop_id: str, limit: int = 50
    ) -> Dict[str, Any]:
        """列出某 ComputedProperty 的任务历史"""
        try:
            jobs = self.repository.list_jobs(prop_id, limit=limit)
            return {
                "jobs": [self._job_to_dict(j) for j in jobs],
                "count": len(jobs),
            }
        except Exception as exc:
            return {"status": "error", "message": f"list_jobs failed: {exc}"}

    # ---------- 内部工具 ----------

    def _resolve_dependencies(self, prop: ComputedProperty) -> List[str]:
        """从表达式中解析依赖；如果用户已指定则优先使用"""
        explicit = list(prop.dependencies or [])
        extracted = self.evaluator.extract_dependencies(prop.expression)
        merged = list(dict.fromkeys(extracted + explicit))
        return merged

    @staticmethod
    def _build_property(
        payload: Dict[str, Any], new_id: bool
    ) -> ComputedProperty:
        """从 payload 构造 ComputedProperty；进行字段校验"""
        name = payload.get("name")
        if not name or not str(name).strip():
            raise ValueError("name is required and must be non-empty")
        target_type_id = payload.get("target_type_id")
        if not target_type_id or not str(target_type_id).strip():
            raise ValueError("target_type_id is required and must be non-empty")
        expression = payload.get("expression")
        if not expression or not str(expression).strip():
            raise ValueError("expression is required and must be non-empty")
        prop_id = None if new_id else payload.get("id")
        materialization_raw = payload.get("materialization", "incremental")
        try:
            materialization = MaterializationType(materialization_raw)
        except ValueError:
            materialization = MaterializationType.INCREMENTAL
        return ComputedProperty(
            id=prop_id or payload.get("id") or _new_id(),
            name=name,
            target_type_id=target_type_id,
            expression=expression,
            dependencies=payload.get("dependencies", []) or [],
            materialization=materialization,
            return_type=payload.get("return_type", "any") or "any",
            description=payload.get("description", "") or "",
            enabled=bool(payload.get("enabled", True)),
        )

    @staticmethod
    def _merge_property(
        existing: ComputedProperty, payload: Dict[str, Any]
    ) -> ComputedProperty:
        """合并更新字段；不传则保留原值"""
        merged_payload = {
            "id": existing.id,
            "name": payload.get("name", existing.name),
            "target_type_id": payload.get("target_type_id", existing.target_type_id),
            "expression": payload.get("expression", existing.expression),
            "dependencies": payload.get("dependencies", existing.dependencies),
            "materialization": payload.get(
                "materialization", existing.materialization.value
            ),
            "return_type": payload.get("return_type", existing.return_type),
            "description": payload.get("description", existing.description),
            "enabled": payload.get("enabled", existing.enabled),
        }
        return ComputedService._build_property(merged_payload, new_id=False)

    @staticmethod
    def _prop_to_dict(prop: ComputedProperty) -> Dict[str, Any]:
        """ComputedProperty → 扁平 dict"""
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
    def _job_to_dict(job: MaterializationJob) -> Dict[str, Any]:
        """MaterializationJob → 扁平 dict"""
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


def _new_id() -> str:
    """生成 UUID 字符串"""
    import uuid
    return str(uuid.uuid4())


__all__ = ["ComputedService"]
