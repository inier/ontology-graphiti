"""
ConflictService - 编排层 (T316)

服务层规范（AGENTS.md 规则 2）：
- 必须返回 Dict[str, Any]，禁止抛 HTTPException
- 错误格式: {"status": "error", "message": "..."}
- 成功格式: 扁平 dict
- 类型转换: Enum→.value, datetime→.isoformat(), BaseModel→扁平 dict
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..impl import ConflictResolverImpl
from ..models import (
    ConflictRecord,
    ConflictResolution,
    ConflictStatus,
    ResolutionResult,
)
from ..storage import SQLiteConflictStorage

logger = logging.getLogger(__name__)


class ConflictService:
    """冲突解决编排服务"""

    def __init__(
        self,
        resolver: ConflictResolverImpl | None = None,
        storage: SQLiteConflictStorage | None = None,
    ):
        self.resolver = resolver or ConflictResolverImpl()
        self.storage = storage or SQLiteConflictStorage()

    # ---------- 业务流程 ----------

    def detect_conflicts(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        检测多源数据冲突，并自动持久化到 storage。
        返回: {"conflicts": [ConflictRecord dict...], "count": int}
        """
        try:
            if not isinstance(sources, list):
                return {"status": "error", "message": "sources must be a list"}
            records = self.resolver.detect_conflicts(sources)
            # 持久化每条检测到的冲突
            for r in records:
                try:
                    self.storage.save_conflict(self._record_to_dict(r))
                except Exception as exc:
                    logger.warning("Failed to persist conflict %s: %s", r.id, exc)
            return {
                "conflicts": [self._record_to_dict(r) for r in records],
                "count": len(records),
            }
        except Exception as exc:
            return {"status": "error", "message": f"detect_conflicts failed: {exc}"}

    def resolve_conflict(
        self,
        conflict: ConflictRecord,
        strategy: str,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """按 strategy 解决单条冲突，并更新 storage 中的记录状态。"""
        try:
            strategy_enum = ConflictResolution(strategy)
        except ValueError:
            return {"status": "error", "message": f"unknown strategy: {strategy}"}

        try:
            result: ResolutionResult = self.resolver.resolve(conflict, strategy_enum, context)
        except Exception as exc:
            return {"status": "error", "message": f"resolve failed: {exc}"}

        # 更新 storage 中的冲突记录
        try:
            updates: Dict[str, Any] = {
                "status": result.status.value,
                "strategy": result.strategy_used.value,
                "resolved_at": datetime.now().isoformat(),
            }
            if result.chosen:
                updates["chosen"] = {
                    "source_id": result.chosen.source_id,
                    "value": result.chosen.value,
                    "confidence": result.chosen.confidence,
                }
            self.storage.update_conflict(conflict.id, updates)
        except Exception as exc:
            logger.warning("Failed to update conflict %s in storage: %s", conflict.id, exc)

        return self._result_to_dict(result)

    def list_conflicts(self, status: str | None = None) -> Dict[str, Any]:
        """从 storage 列出冲突（可选按 status 过滤）"""
        # 校验 status 枚举值
        if status is not None:
            try:
                ConflictStatus(status)
            except ValueError:
                return {"status": "error", "message": f"unknown status: {status}"}

        try:
            conflicts = self.storage.list_conflicts(status=status)
            total = self.storage.count_conflicts(status=status)
            return {
                "conflicts": conflicts,
                "count": len(conflicts),
                "total": total,
            }
        except Exception as exc:
            return {"status": "error", "message": f"list_conflicts failed: {exc}"}

    # ---------- 类型转换 ----------

    @staticmethod
    def _record_to_dict(record: ConflictRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "entity_id": record.entity_id,
            "entity_type": record.entity_type,
            "field_name": record.field_name,
            "conflict_type": record.conflict_type.value,
            "candidates": [
                {
                    "source_id": c.source_id,
                    "value": c.value,
                    "confidence": c.confidence,
                    "observed_at": c.observed_at.isoformat(),
                }
                for c in record.candidates
            ],
            "status": record.status.value,
            "strategy": record.strategy.value if record.strategy else None,
            "chosen": (
                {
                    "source_id": record.chosen.source_id,
                    "value": record.chosen.value,
                    "confidence": record.chosen.confidence,
                }
                if record.chosen
                else None
            ),
            "detected_at": record.detected_at.isoformat(),
            "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
            "resolver_id": record.resolver_id,
            "notes": record.notes,
        }

    @staticmethod
    def _result_to_dict(result: ResolutionResult) -> Dict[str, Any]:
        return {
            "conflict_id": result.conflict_id,
            "status": result.status.value,
            "chosen": (
                {
                    "source_id": result.chosen.source_id,
                    "value": result.chosen.value,
                    "confidence": result.chosen.confidence,
                }
                if result.chosen
                else None
            ),
            "rationale": result.rationale,
            "strategy_used": result.strategy_used.value,
            "duration_ms": result.duration_ms,
        }
