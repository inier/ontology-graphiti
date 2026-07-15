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

from odap.infra.security.audit_helper import storage_audit

from ..impl import ConflictResolverImpl
from ..models import (
    ConflictRecord,
    ConflictResolution,
    ConflictStatus,
    ResolutionResult,
)
from ..storage import SQLiteConflictStorage

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
        action = "conflict.detect_conflicts"
        try:
            if not isinstance(sources, list):
                _audit_failure(action, msg="sources must be a list",
                               details={"sources_type": type(sources).__name__})
                return {"status": "error", "message": "sources must be a list"}
            records = self.resolver.detect_conflicts(sources)
            persist_count = 0
            for r in records:
                try:
                    self.storage.save_conflict(self._record_to_dict(r))
                    persist_count += 1
                except Exception as exc:
                    logger.warning("Failed to persist conflict %s: %s", r.id, exc)
            result = {
                "conflicts": [self._record_to_dict(r) for r in records],
                "count": len(records),
            }
            _audit_success(action,
                           details={"source_count": len(sources),
                                    "conflict_count": len(records),
                                    "persist_count": persist_count})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"source_count": len(sources or [])})
            return {"status": "error", "message": f"detect_conflicts failed: {exc}"}

    def get_conflicts(
        self, status: str | None = None, entity_id: str | None = None,
    ) -> Dict[str, Any]:
        """列出冲突（可选按 status / entity_id 过滤）"""
        action = "conflict.get_conflicts"
        try:
            if status is not None:
                try:
                    ConflictStatus(status)
                except ValueError:
                    _audit_failure(action, msg=f"unknown status: {status}")
                    return {"status": "error", "message": f"unknown status: {status}"}
            conflicts = self.storage.list_conflicts(status=status)
            if entity_id:
                conflicts = [c for c in conflicts if c.get("entity_id") == entity_id]
            total = self.storage.count_conflicts(status=status)
            _audit_success(action,
                           details={"count": len(conflicts),
                                    "total": total,
                                    "has_status_filter": bool(status),
                                    "has_entity_filter": bool(entity_id)})
            return {
                "conflicts": conflicts,
                "count": len(conflicts),
                "total": total,
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"has_status_filter": bool(status)})
            return {"status": "error", "message": f"get_conflicts failed: {exc}"}

    def get_conflict_stats(self) -> Dict[str, Any]:
        """获取冲突统计：按 status / conflict_type 聚合"""
        action = "conflict.get_conflict_stats"
        try:
            all_conflicts = self.storage.list_conflicts()
            by_status: Dict[str, int] = {}
            by_type: Dict[str, int] = {}
            for c in all_conflicts:
                s = c.get("status", "unknown")
                by_status[s] = by_status.get(s, 0) + 1
                t = c.get("conflict_type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1
            result = {
                "total": len(all_conflicts),
                "by_status": by_status,
                "by_conflict_type": by_type,
            }
            _audit_success(action,
                           details={"total": len(all_conflicts),
                                    "status_groups": len(by_status),
                                    "type_groups": len(by_type)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"get_conflict_stats failed: {exc}"}

    def resolve_conflict(
        self,
        conflict: ConflictRecord,
        strategy: str,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """按 strategy 解决单条冲突，并更新 storage 中的记录状态。"""
        action = "conflict.resolve_conflict"
        resource = conflict.id
        try:
            strategy_enum = ConflictResolution(strategy)
        except ValueError:
            _audit_failure(action, msg=f"unknown strategy: {strategy}", resource=resource,
                           details={"conflict_id": conflict.id})
            return {"status": "error", "message": f"unknown strategy: {strategy}"}

        try:
            result: ResolutionResult = self.resolver.resolve(conflict, strategy_enum, context)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=resource,
                           details={"conflict_id": conflict.id, "strategy": strategy})
            return {"status": "error", "message": f"resolve failed: {exc}"}

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

        _audit_success(action, resource=resource,
                       details={"conflict_id": conflict.id,
                                "strategy": strategy,
                                "status": result.status.value,
                                "duration_ms": int(result.duration_ms or 0)})
        return self._result_to_dict(result)

    def auto_resolve(
        self,
        status: str | None = None,
        default_strategy: str = "LAST_WINS",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """批量自动解决未处理的冲突（AWAITING_HUMAN 跳过）"""
        action = "conflict.auto_resolve"
        try:
            try:
                strategy_enum = ConflictResolution(default_strategy)
            except ValueError:
                _audit_failure(action, msg=f"unknown strategy: {default_strategy}")
                return {"status": "error", "message": f"unknown strategy: {default_strategy}"}

            raw_conflicts = self.storage.list_conflicts(status=status or ConflictStatus.PENDING.value)
            resolved: List[Dict[str, Any]] = []
            skipped = 0
            for row in raw_conflicts[:limit]:
                try:
                    cr = ConflictRecord(
                        id=row.get("id", ""),
                        entity_id=row.get("entity_id", ""),
                        entity_type=row.get("entity_type", "unknown"),
                        field_name=row.get("field_name", ""),
                        conflict_type=row.get("conflict_type", "value_mismatch"),
                        candidates=[],
                        status=ConflictStatus(row.get("status", "pending")),
                    )
                    if cr.status == ConflictStatus.AWAITING_HUMAN:
                        skipped += 1
                        continue
                    res: ResolutionResult = self.resolver.resolve(cr, strategy_enum, {})
                    try:
                        self.storage.update_conflict(cr.id, {
                            "status": res.status.value,
                            "strategy": res.strategy_used.value,
                            "resolved_at": datetime.now().isoformat(),
                        })
                    except Exception as up_exc:
                        logger.warning("update_conflict failed %s: %s", cr.id, up_exc)
                    resolved.append(self._result_to_dict(res))
                except Exception as r_exc:
                    logger.warning("auto resolve one failed: %s", r_exc)
                    skipped += 1
                    continue
            _audit_success(action,
                           details={"attempted": len(raw_conflicts[:limit]),
                                    "resolved_count": len(resolved),
                                    "skipped": skipped,
                                    "strategy": default_strategy})
            return {
                "resolved": resolved,
                "resolved_count": len(resolved),
                "skipped": skipped,
                "attempted": len(raw_conflicts[:limit]),
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"strategy": default_strategy, "limit": limit})
            return {"status": "error", "message": f"auto_resolve failed: {exc}"}

    def list_conflicts(self, status: str | None = None) -> Dict[str, Any]:
        """从 storage 列出冲突（可选按 status 过滤）"""
        action = "conflict.list_conflicts"
        if status is not None:
            try:
                ConflictStatus(status)
            except ValueError:
                _audit_failure(action, msg=f"unknown status: {status}")
                return {"status": "error", "message": f"unknown status: {status}"}

        try:
            conflicts = self.storage.list_conflicts(status=status)
            total = self.storage.count_conflicts(status=status)
            _audit_success(action,
                           details={"count": len(conflicts),
                                    "total": total,
                                    "has_status_filter": bool(status)})
            return {
                "conflicts": conflicts,
                "count": len(conflicts),
                "total": total,
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"has_status_filter": bool(status)})
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
