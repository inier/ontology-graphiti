"""
ConflictService - 编排层 (T316)

服务层规范（AGENTS.md 规则 2）：
- 必须返回 Dict[str, Any]，禁止抛 HTTPException
- 错误格式: {"status": "error", "message": "..."}
- 成功格式: 扁平 dict
- 类型转换: Enum→.value, datetime→.isoformat(), BaseModel→扁平 dict
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..impl import ConflictResolverImpl
from ..models import (
    ConflictRecord,
    ConflictResolution,
    ConflictStatus,
    ResolutionResult,
)


class ConflictService:
    """冲突解决编排服务"""

    def __init__(self, resolver: ConflictResolverImpl | None = None):
        self.resolver = resolver or ConflictResolverImpl()

    # ---------- 业务流程 ----------

    def detect_conflicts(self, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        检测多源数据冲突。
        返回: {"conflicts": [ConflictRecord dict...]}
        """
        try:
            if not isinstance(sources, list):
                return {"status": "error", "message": "sources must be a list"}
            records = self.resolver.detect_conflicts(sources)
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
        """按 strategy 解决单条冲突。strategy: str 形式如 'first_wins'"""
        try:
            strategy_enum = ConflictResolution(strategy)
        except ValueError:
            return {"status": "error", "message": f"unknown strategy: {strategy}"}

        try:
            result: ResolutionResult = self.resolver.resolve(conflict, strategy_enum, context)
        except Exception as exc:
            return {"status": "error", "message": f"resolve failed: {exc}"}

        return self._result_to_dict(result)

    def list_conflicts(self, conflicts: List[ConflictRecord], status: str | None = None) -> Dict[str, Any]:
        """列出冲突（可选按 status 过滤）"""
        # 先校验 status 枚举值（即使 conflicts 为空也要拒绝非法 status）
        if status is not None:
            try:
                status_enum = ConflictStatus(status)
            except ValueError:
                return {"status": "error", "message": f"unknown status: {status}"}
            filtered = [c for c in conflicts if c.status == status_enum]
        else:
            filtered = list(conflicts)
        return {
            "conflicts": [self._record_to_dict(c) for c in filtered],
            "count": len(filtered),
        }

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
