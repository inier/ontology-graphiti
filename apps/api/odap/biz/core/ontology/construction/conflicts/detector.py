"""ConflictDetector — 属性/类型/关系/时态冲突检测（ADR-078 §3.6）。

在构建期（HE feed 产出后、写图前）检测多源汇聚分歧，产出 ConflictReport
进质量闸。核心：冲突**标记而非覆盖**。

输入：实体/关系候选列表，每项带 source_id 标识来源。
输出：ConflictReport（含 Conflict 列表）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .models import Conflict, ConflictType, ConflictReport, ConflictSeverity

logger = logging.getLogger(__name__)


class ConflictDetector:
    """多源汇聚冲突检测器"""

    def detect(
        self,
        entities: List[Dict[str, Any]],
        workspace_id: str = "default",
    ) -> ConflictReport:
        """检测实体列表中的冲突。

        Args:
            entities: 实体候选列表，每项形如：
                {
                    "entity_id": str,
                    "type": str,
                    "source_id": str,
                    "properties": {key: value},
                    "relations": [{name, target}],
                    "valid_from": str, "valid_to": str,
                }
            workspace_id: 工作空间

        Returns:
            ConflictReport（finalize 已调用）
        """
        conflicts: List[Conflict] = []

        # 按 entity_id 分组
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for ent in entities:
            eid = ent.get("entity_id") or ent.get("id", "")
            if not eid:
                continue
            grouped.setdefault(eid, []).append(ent)

        for eid, group in grouped.items():
            if len(group) < 2:
                continue
            conflicts.extend(self._detect_type_conflict(eid, group))
            conflicts.extend(self._detect_property_conflicts(eid, group))
            conflicts.extend(self._detect_relation_conflicts(eid, group))
            conflicts.extend(self._detect_temporal_conflicts(eid, group))

        report = ConflictReport(workspace_id=workspace_id, conflicts=conflicts)
        return report.finalize()

    # ── 类型冲突 ──

    def _detect_type_conflict(self, eid: str, group: List[Dict[str, Any]]) -> List[Conflict]:
        types = {}
        for ent in group:
            t = ent.get("type")
            if t is not None:
                types.setdefault(t, []).append(ent.get("source_id", "unknown"))
        if len(types) > 1:
            return [Conflict(
                conflict_type=ConflictType.TYPE,
                entity_id=eid,
                values=list(types.keys()),
                sources=[s for v in types.values() for s in v],
                severity=ConflictSeverity.ERROR,
                message=f"实体类型分歧: {list(types.keys())}",
            )]
        return []

    # ── 属性冲突 ──

    def _detect_property_conflicts(self, eid: str, group: List[Dict[str, Any]]) -> List[Conflict]:
        # 收集每个属性的多源取值
        attr_values: Dict[str, Dict[Any, List[str]]] = {}
        for ent in group:
            for key, val in ent.get("properties", {}).items():
                if val is None:
                    continue
                bucket = attr_values.setdefault(key, {})
                # 用可哈希表示作为 key（简单值直接哈希，复杂值用 str）
                vkey = self._hashable(val)
                bucket.setdefault(vkey, []).append(ent.get("source_id", "unknown"))

        conflicts = []
        for attr, bucket in attr_values.items():
            if len(bucket) > 1:
                conflicts.append(Conflict(
                    conflict_type=ConflictType.PROPERTY,
                    entity_id=eid,
                    attribute=attr,
                    values=[self._unhash(v) for v in bucket.keys()],
                    sources=[s for v in bucket.values() for s in v],
                    severity=ConflictSeverity.WARN,
                    message=f"属性 {attr} 取值分歧: {len(bucket)} 种",
                ))
        return conflicts

    # ── 关系冲突 ──

    def _detect_relation_conflicts(self, eid: str, group: List[Dict[str, Any]]) -> List[Conflict]:
        rel_targets: Dict[str, Dict[Any, List[str]]] = {}
        for ent in group:
            for rel in ent.get("relations", []):
                name = rel.get("name", "")
                target = rel.get("target", "")
                if not name:
                    continue
                bucket = rel_targets.setdefault(name, {})
                bucket.setdefault(str(target), []).append(ent.get("source_id", "unknown"))

        conflicts = []
        for name, bucket in rel_targets.items():
            if len(bucket) > 1:
                conflicts.append(Conflict(
                    conflict_type=ConflictType.RELATION,
                    entity_id=eid,
                    attribute=name,
                    values=list(bucket.keys()),
                    sources=[s for v in bucket.values() for s in v],
                    severity=ConflictSeverity.WARN,
                    message=f"关系 {name} 目标分歧: {len(bucket)} 种",
                ))
        return conflicts

    # ── 时态冲突 ──

    def _detect_temporal_conflicts(self, eid: str, group: List[Dict[str, Any]]) -> List[Conflict]:
        intervals = {}
        for ent in group:
            vf = ent.get("valid_from")
            vt = ent.get("valid_to")
            if vf is not None and vt is not None:
                key = (str(vf), str(vt))
                intervals.setdefault(key, []).append(ent.get("source_id", "unknown"))
        if len(intervals) > 1:
            return [Conflict(
                conflict_type=ConflictType.TEMPORAL,
                entity_id=eid,
                values=[list(k) for k in intervals.keys()],
                sources=[s for v in intervals.values() for s in v],
                severity=ConflictSeverity.WARN,
                message=f"时态区间分歧: {len(intervals)} 种",
            )]
        return []

    # ── 辅助 ──

    @staticmethod
    def _hashable(val: Any):
        """将值转为可哈希 key（简单值直接用，复杂值用 repr）"""
        try:
            hash(val)
            return val
        except TypeError:
            return repr(val)

    @staticmethod
    def _unhash(v: Any) -> Any:
        return v


__all__ = ["ConflictDetector"]
