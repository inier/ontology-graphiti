"""
ConflictResolverImpl - 4 种策略实现 (T315)

策略语义：
- FIRST_WINS：按 candidates[].observed_at 升序，取最早的候选
- LAST_WINS：按 candidates[].observed_at 降序，取最新的候选
- LLM_JUDGE：调用 LLM 进行语义判断，失败则降级为 MANUAL
- MANUAL：标记为 AWAITING_HUMAN，不自动选候选
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from odap.infra.security.audit_helper import storage_audit

from ..interfaces import ConflictResolver
from ..models import (
    ConflictCandidate,
    ConflictRecord,
    ConflictResolution,
    ConflictStatus,
    ResolutionResult,
)

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


class ConflictResolverImpl(ConflictResolver):
    """4 策略冲突解决器"""

    def detect_conflicts(self, sources: List[Dict[str, Any]]) -> List[ConflictRecord]:
        """
        从多源数据中检测冲突。

        sources 格式: [{ "source_id": "src1", "entities": [{ "id": ..., "type": ..., "fields": {field: value} }] }]
        冲突定义：同一 (entity_id, field_name) 在不同源中值不同。
        """
        action = "resolver.detect_conflicts"
        try:
            if not sources:
                _audit_success(action, details={"source_count": 0, "conflict_count": 0})
                return []
            cell_index, entity_types = self._index_sources(sources)
            records = [c for c in (self._record_from_cell(k, v, entity_types) for k, v in cell_index.items()) if c]
            _audit_success(action,
                           details={"source_count": len(sources),
                                    "entity_count": len(entity_types),
                                    "conflict_count": len(records)})
            return records
        except Exception as exc:
            _audit_failure(action, msg=str(exc),
                           details={"source_count": len(sources or [])})
            raise

    def _index_sources(self, sources):
        cell_index: Dict[tuple, Dict[str, Any]] = {}
        entity_types: Dict[str, str] = {}
        for src in sources:
            sid = src.get("source_id", "unknown")
            for ent in src.get("entities", []):
                eid = ent.get("id")
                entity_types[eid] = ent.get("type", "unknown")
                for fname, fval in ent.get("fields", {}).items():
                    cell_index.setdefault((eid, fname), {})[sid] = fval
        return cell_index, entity_types

    def _record_from_cell(self, key, by_source, entity_types) -> ConflictRecord | None:
        eid, fname = key
        distinct_values = {repr(v) for v in by_source.values()}
        if len(distinct_values) <= 1:
            return None
        candidates = [ConflictCandidate(source_id=sid, value=val) for sid, val in by_source.items()]
        return ConflictRecord(
            entity_id=eid,
            entity_type=entity_types.get(eid, "unknown"),
            field_name=fname,
            candidates=candidates,
        )

    def resolve(
        self,
        conflict: ConflictRecord,
        strategy: ConflictResolution,
        context: Dict[str, Any] | None = None,
    ) -> ResolutionResult:
        """按策略解决单条冲突"""
        action = "resolver.resolve"
        resource = conflict.id
        start = time.perf_counter()
        ctx = context or {}

        try:
            if strategy == ConflictResolution.FIRST_WINS:
                chosen, rationale = self._first_wins(conflict)
                status = ConflictStatus.RESOLVED
            elif strategy == ConflictResolution.LAST_WINS:
                chosen, rationale = self._last_wins(conflict)
                status = ConflictStatus.RESOLVED
            elif strategy == ConflictResolution.LLM_JUDGE:
                chosen, rationale = self._llm_judge(conflict, ctx)
                status = ConflictStatus.RESOLVED if chosen else ConflictStatus.AWAITING_HUMAN
            elif strategy == ConflictResolution.MANUAL:
                chosen, rationale = None, "Manual resolution by human"
                status = ConflictStatus.AWAITING_HUMAN
            else:
                raise ValueError(f"Unknown strategy: {strategy}")

            duration_ms = (time.perf_counter() - start) * 1000.0
            result = ResolutionResult(
                conflict_id=conflict.id,
                status=status,
                chosen=chosen,
                rationale=rationale,
                strategy_used=strategy,
                duration_ms=duration_ms,
            )
            _audit_success(action, resource=resource,
                           details={"conflict_id": conflict.id,
                                    "strategy": strategy.value,
                                    "status": status.value,
                                    "has_chosen": bool(chosen),
                                    "duration_ms": int(duration_ms)})
            return result
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=resource,
                           details={"conflict_id": conflict.id,
                                    "strategy": strategy.value if hasattr(strategy, "value") else str(strategy)})
            raise

    def apply_resolution(
        self,
        conflict: ConflictRecord,
        result: ResolutionResult,
        target_storage: Any = None,
    ) -> bool:
        """应用解决结果到目标存储（可选操作）"""
        action = "resolver.apply_resolution"
        resource = conflict.id
        try:
            if result.status != ConflictStatus.RESOLVED:
                _audit_failure(action, msg="resolution not in RESOLVED status", resource=resource,
                               details={"conflict_id": conflict.id, "result_status": result.status.value})
                return False
            if target_storage is not None:
                try:
                    target_storage.update_conflict(conflict.id, {
                        "status": result.status.value,
                        "strategy": result.strategy_used.value,
                        "resolved_by": "resolver",
                    })
                except Exception as exc:
                    logger.warning("apply_resolution target_storage update failed: %s", exc)
            _audit_success(action, resource=resource,
                           details={"conflict_id": conflict.id,
                                    "strategy": result.strategy_used.value,
                                    "has_storage": target_storage is not None})
            return True
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=resource,
                           details={"conflict_id": conflict.id})
            raise

    # ---------- 4 strategies ----------

    @staticmethod
    def _first_wins(conflict: ConflictRecord):
        chosen = min(conflict.candidates, key=lambda c: c.observed_at)
        return chosen, f"First-wins: source={chosen.source_id}"

    @staticmethod
    def _last_wins(conflict: ConflictRecord):
        chosen = max(conflict.candidates, key=lambda c: c.observed_at)
        return chosen, f"Last-wins: source={chosen.source_id}"

    def _llm_judge(self, conflict: ConflictRecord, context: Dict[str, Any]):
        """调用 LLM 判断；失败时降级为 MANUAL 并返回 None"""
        llm_client = context.get("llm_client")
        if llm_client is None:
            logger.warning("LLM_JUDGE requested but no llm_client in context; falling back to MANUAL")
            return None, "LLM_JUDGE failed: no llm_client provided; awaiting human"

        try:
            prompt = self._build_llm_prompt(conflict)
            response = llm_client.complete(prompt)
            chosen_source = (response or "").strip()
            chosen = next(
                (c for c in conflict.candidates if c.source_id == chosen_source),
                None,
            )
            if not chosen:
                return None, f"LLM returned unknown source_id; awaiting human"
            return chosen, f"LLM_JUDGE selected source={chosen.source_id}"
        except Exception as exc:
            logger.exception("LLM_JUDGE failed: %s", exc)
            return None, f"LLM_JUDGE exception: {exc}; awaiting human"

    @staticmethod
    def _build_llm_prompt(conflict: ConflictRecord) -> str:
        lines = [
            "You are a data-conflict resolution judge. Choose the most likely correct",
            "value among the candidates below, and reply with ONLY the source_id.",
            "",
            f"entity_id: {conflict.entity_id}",
            f"field_name: {conflict.field_name}",
            f"conflict_type: {conflict.conflict_type.value}",
            "candidates:",
        ]
        for c in conflict.candidates:
            lines.append(f"- source_id={c.source_id} confidence={c.confidence}")
        return "\n".join(lines)
