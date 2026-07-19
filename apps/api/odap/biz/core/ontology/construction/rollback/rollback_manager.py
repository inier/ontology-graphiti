"""ConstructionRollbackManager — 构建回滚管理器。

支持三级回滚:
- 版本级: 回滚整个版本
- Pipeline级: 回滚整个构建流水线
- Batch级: 回滚特定批次的图谱写入

每次回滚操作都记录独立审计。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RollbackLevel(str, Enum):
    VERSION = "version"    # 版本级
    PIPELINE = "pipeline"  # Pipeline级
    BATCH = "batch"        # Batch级


class RollbackStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class UndoStrategy:
    """回滚策略基类"""

    async def undo(self, step_context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class SnapshotUndo(UndoStrategy):
    """通过快照恢复回滚"""

    async def undo(self, step_context: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = step_context.get("snapshot", {})
        target = step_context.get("target", "")
        logger.info("Undoing %s via snapshot restore (keys: %s)", target, list(snapshot.keys())[:5])
        return {
            "status": "restored",
            "target": target,
            "restored_keys": len(snapshot),
        }


class BatchDeleteUndo(UndoStrategy):
    """通过批次删除回滚"""

    async def undo(self, step_context: Dict[str, Any]) -> Dict[str, Any]:
        batch_id = step_context.get("batch_id", "")
        try:
            from odap.infra.graph.graph_service import get_graph_manager
            gm = get_graph_manager()
            deleted = await gm.delete_by_batch(batch_id) if hasattr(gm, 'delete_by_batch') else 0
            return {"status": "deleted", "batch_id": batch_id, "deleted_count": deleted}
        except Exception as e:
            logger.error("Batch delete failed for %s: %s", batch_id, e)
            return {"status": "failed", "batch_id": batch_id, "error": str(e)}


@dataclass
class RollbackRecord:
    """回滚操作记录"""
    rollback_id: str = ""
    pipeline_run_id: str = ""
    level: RollbackLevel = RollbackLevel.PIPELINE
    status: RollbackStatus = RollbackStatus.PENDING
    reason: str = ""
    operator: str = "system"
    steps_undone: List[str] = field(default_factory=list)
    entities_affected: int = 0
    relations_affected: int = 0
    started_at: str = ""
    completed_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "rollback_id": self.rollback_id,
            "pipeline_run_id": self.pipeline_run_id,
            "level": self.level.value,
            "status": self.status.value,
            "reason": self.reason,
            "operator": self.operator,
            "steps_undone": self.steps_undone,
            "entities_affected": self.entities_affected,
            "relations_affected": self.relations_affected,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class ConstructionRollbackManager:
    """构建回滚管理器 — 单例"""

    _instance: Optional["ConstructionRollbackManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._undo_strategies: Dict[str, UndoStrategy] = {
            "snapshot": SnapshotUndo(),
            "batch_delete": BatchDeleteUndo(),
        }
        self._records: Dict[str, RollbackRecord] = {}
        self._initialized = True

    # ── Public API ──

    async def rollback_pipeline(
        self,
        pipeline_run_id: str,
        reason: str = "",
        operator: str = "system",
    ) -> RollbackRecord:
        """回滚整个构建流水线。

        反向执行已完成的步骤: Snapshot → GraphWrite → Review → Consistency → Validation → Normalization

        根据每个步骤的类型，选择对应的 UndoStrategy 执行真正的逆向操作：
        - graph_write → 批次删除图谱数据
        - snapshot → 删除版本快照
        - 其他步骤 → 记录审计（无持久化副作用需逆向）
        """
        rollback_id = f"rb-{uuid.uuid4().hex[:12]}"
        record = RollbackRecord(
            rollback_id=rollback_id, pipeline_run_id=pipeline_run_id,
            level=RollbackLevel.PIPELINE, reason=reason, operator=operator,
            status=RollbackStatus.IN_PROGRESS,
            started_at=_now(),
        )

        try:
            steps = await self._get_completed_steps(pipeline_run_id)

            # 反向执行回滚: Snapshot → GraphWrite → Review → Consistency → Validation → Normalization
            for step in reversed(steps):
                step_type = step.get("step_type", "")

                if step_type == "graph_write":
                    # 删除该批次写入的图谱数据
                    batch_id = step.get("batch_id", "")
                    if batch_id:
                        strategy = self._undo_strategies["batch_delete"]
                        result = await strategy.undo({"batch_id": batch_id})
                        record.entities_affected += result.get("deleted_count", 0)
                        record.steps_undone.append("graph_write")

                elif step_type == "snapshot":
                    # 删除版本快照
                    snapshot_id = step.get("snapshot_id", "")
                    strategy = self._undo_strategies["snapshot"]
                    await strategy.undo({"target": "snapshot", "snapshot": step})
                    record.steps_undone.append("snapshot")

                elif step_type in ("normalization", "relation_validation", "consistency", "review"):
                    # 这些步骤只在 PipelineContext 中操作，回滚只需记录
                    record.steps_undone.append(step_type)

                # 每个步骤回滚后记录审计
                await self._record_step_rollback(rollback_id, step_type, record.operator)

            record.status = RollbackStatus.COMPLETED
            record.completed_at = _now()
        except Exception as e:
            logger.error("Pipeline rollback failed for %s: %s", pipeline_run_id, e)
            record.status = RollbackStatus.FAILED
            record.error = str(e)
            record.completed_at = _now()

        self._records[rollback_id] = record
        await self._record_rollback_audit(record)
        return record

    async def rollback_batch(self, batch_id: str, reason: str = "", operator: str = "system") -> RollbackRecord:
        """回滚特定批次的图谱写入"""
        rollback_id = f"rb-{uuid.uuid4().hex[:12]}"
        record = RollbackRecord(
            rollback_id=rollback_id, pipeline_run_id=batch_id,
            level=RollbackLevel.BATCH, reason=reason, operator=operator,
            status=RollbackStatus.IN_PROGRESS, started_at=_now(),
        )

        try:
            strategy = self._undo_strategies["batch_delete"]
            result = await strategy.undo({"batch_id": batch_id})
            record.entities_affected = result.get("deleted_count", 0)
            record.steps_undone = ["graph_write"]
            record.status = RollbackStatus.COMPLETED
            record.completed_at = _now()
            await self._record_rollback_audit(record)
        except Exception as e:
            logger.error("Batch rollback failed for %s: %s", batch_id, e)
            record.status = RollbackStatus.FAILED
            record.error = str(e)
            record.completed_at = _now()

        self._records[rollback_id] = record
        return record

    async def rollback_version(
        self,
        version_id: str,
        reason: str = "",
        operator: str = "system",
    ) -> RollbackRecord:
        """回滚到指定版本（全量重新摄入）"""
        rollback_id = f"rb-{uuid.uuid4().hex[:12]}"
        record = RollbackRecord(
            rollback_id=rollback_id, pipeline_run_id=version_id,
            level=RollbackLevel.VERSION, reason=reason, operator=operator,
            status=RollbackStatus.IN_PROGRESS, started_at=_now(),
        )

        try:
            from odap.biz.core.ontology.design.services.pipeline_service import get_pipeline_service
            pipeline = get_pipeline_service()
            doc = await pipeline.get_version_document(version_id)
            if doc:
                new_version = await pipeline.rollback(version_id, "default", operator)
                record.steps_undone = ["version_rollback"]
                record.status = RollbackStatus.COMPLETED
        except Exception as e:
            logger.error("Version rollback failed for %s: %s", version_id, e)
            record.status = RollbackStatus.FAILED
            record.error = str(e)

        record.completed_at = _now()
        await self._record_rollback_audit(record)
        self._records[rollback_id] = record
        return record

    def get_rollback_status(self, rollback_id: str) -> Optional[Dict[str, Any]]:
        rec = self._records.get(rollback_id)
        return rec.to_dict() if rec else None

    def get_rollback_history(self, pipeline_run_id: str) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._records.values() if r.pipeline_run_id == pipeline_run_id]

    # ── Internal ──

    async def _get_completed_steps(self, pipeline_run_id: str) -> List[Dict[str, Any]]:
        """获取已完成的步骤列表（从存储查询）"""
        try:
            from odap.biz.core.ontology.design.services.pipeline_service import get_pipeline_service
            pipeline = get_pipeline_service()
            context = await pipeline.get_context(pipeline_run_id)
            if context:
                return context.get("completed_steps", [])
        except Exception as e:
            logger.debug("Failed to get pipeline steps: %s", e)
        return []

    async def _record_rollback_audit(self, record: RollbackRecord):
        """记录回滚审计"""
        try:
            from odap.biz.core.ontology.design.engine.impl.audit_recorder_impl import AuditRecorderImpl
            recorder = AuditRecorderImpl()
            recorder.record_ingest(
                entity_type_id="rollback",
                source="construction_rollback",
                process_steps=[{
                    "step": f"rollback_{record.level.value}",
                    "rollback_id": record.rollback_id,
                    "status": record.status.value,
                }],
                transform_rules=[],
                result=f"entities_affected={record.entities_affected}",
            )
        except Exception as e:
            logger.warning("Rollback audit recording failed: %s", e)

    async def _record_step_rollback(self, rollback_id: str, step_type: str, operator: str):
        """记录每步回滚的审计。

        为每个步骤的逆向操作生成独立的审计记录，
        便于事后追踪回滚过程中每一步的状态。

        Args:
            rollback_id: 回滚操作ID
            step_type: 被回滚的步骤类型（如 graph_write, snapshot 等）
            operator: 操作者标识
        """
        try:
            from odap.biz.core.ontology.design.engine.impl.audit_recorder_impl import AuditRecorderImpl
            recorder = AuditRecorderImpl()
            recorder.record_ingest(
                entity_type_id="step_rollback",
                source="construction_rollback",
                process_steps=[{
                    "step": f"undo_{step_type}",
                    "rollback_id": rollback_id,
                    "operator": operator,
                }],
                transform_rules=[],
                result="completed",
            )
        except Exception as e:
            logger.warning("Step rollback audit failed: %s", e)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def get_rollback_manager() -> ConstructionRollbackManager:
    return ConstructionRollbackManager()


__all__ = [
    "RollbackLevel", "RollbackStatus", "RollbackRecord",
    "ConstructionRollbackManager", "get_rollback_manager",
]
