"""ImpactAnalyzerImpl (T424)

静态分析 JSON Patch 的 path 字段，识别受影响的 ObjectType / ActionType，
估算迁移成本与风险等级。

Path 规则约定 (与 odap/biz/core/ontology/model 的存储结构对齐):
- /object_types/{name}/properties/{prop_name}  -> ObjectType property
- /object_types/{name}/required              -> ObjectType required fields
- /object_types/{name}                        -> 整个 ObjectType
- /action_types/{name}                        -> 整个 ActionType
- /action_types/{name}/parameters             -> ActionType 参数

Breaking change 规则:
- 修改 /required（添加或删除必填字段） -> 破坏性
- 修改 /type (字段类型)                -> 破坏性
- remove 整个 /object_types/* 或 /action_types/*  -> 破坏性
- replace /object_types/*/properties/*/type  -> 破坏性
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from ..interfaces import ImpactAnalyzer
from ..models import ImpactAnalysis, ImpactCost, RiskLevel


# 路径正则
_RE_OBJECT_TYPE_PROP = re.compile(
    r"^/object_types/(?P<ot>[^/]+)/properties/(?P<prop>[^/]+)(/.*)?$"
)
_RE_OBJECT_TYPE_REQUIRED = re.compile(
    r"^/object_types/(?P<ot>[^/]+)/required(/.*)?$"
)
_RE_OBJECT_TYPE = re.compile(r"^/object_types/(?P<ot>[^/]+)(/.*)?$")
_RE_ACTION_TYPE = re.compile(r"^/action_types/(?P<at>[^/]+)(/.*)?$")
_RE_FIELD_TYPE = re.compile(r"^.*/type(/.*)?$")


class ImpactAnalyzerImpl(ImpactAnalyzer):
    """静态 JSON Patch 变更影响分析器"""

    def __init__(self, instance_counter: Optional[Callable[[str], int]] = None):
        """instance_counter: 可选回调，传入 type_name 返回其实例数估算。
        默认为 None（所有 instance 计数视为 0）。
        """
        self.instance_counter = instance_counter

    def analyze(
        self,
        changes: List[Dict[str, Any]],
        proposal_id: str = "",
    ) -> ImpactAnalysis:
        """分析 JSON Patch 列表"""
        affected_objects: List[str] = []
        affected_actions: List[str] = []
        breaking: List[str] = []
        affected_instances: List[int] = [0]

        for change in changes or []:
            self._apply_patch(
                change, affected_objects, affected_actions, breaking,
                affected_instances,
            )

        breaking_count = len(breaking)
        cost = self._estimate_migration_cost(breaking_count)
        risk = self._map_risk_level(cost, len(affected_objects),
                                    len(affected_actions))

        metadata = {
            "analyzed_patches": len(changes or []),
            "object_types_count": len(affected_objects),
            "action_types_count": len(affected_actions),
        }
        return ImpactAnalysis(
            proposal_id=proposal_id,
            affected_object_types=affected_objects,
            affected_action_types=affected_actions,
            affected_instances_count=affected_instances[0],
            breaking_changes=breaking,
            estimated_migration_cost=cost,
            risk_level=risk,
            analysis_metadata=metadata,
        )

    def _count_instances(self, type_name: str) -> int:
        if self.instance_counter and type_name:
            return self.instance_counter(type_name)
        return 0

    def _apply_patch(
        self,
        change: Dict[str, Any],
        affected_objects: List[str],
        affected_actions: List[str],
        breaking: List[str],
        affected_instances: List[int],
    ) -> None:
        op = str(change.get("op", "")).lower()
        path = str(change.get("path", ""))
        if not path:
            return

        ot_match = _RE_OBJECT_TYPE_PROP.match(path) or _RE_OBJECT_TYPE.match(path)
        at_match = _RE_ACTION_TYPE.match(path)
        req_match = _RE_OBJECT_TYPE_REQUIRED.match(path)
        type_match = _RE_FIELD_TYPE.match(path)

        if ot_match:
            ot_name = ot_match.group("ot")
            self._handle_object_patch(
                op, path, ot_name, req_match, type_match,
                affected_objects, breaking,
            )
            if ot_name:
                affected_instances[0] += self._count_instances(ot_name)
        elif at_match:
            at_name = at_match.group("at")
            self._handle_action_patch(op, path, at_name, affected_actions, breaking)

    @staticmethod
    def _handle_object_patch(
        op: str,
        path: str,
        ot_name: Optional[str],
        req_match: Optional[re.Match],
        type_match: Optional[re.Match],
        affected_objects: List[str],
        breaking: List[str],
    ) -> None:
        if ot_name and ot_name not in affected_objects:
            affected_objects.append(ot_name)
        if req_match and op in {"add", "remove", "replace"}:
            breaking.append(f"Required field change on {ot_name}: {op} {path}")
        if type_match and op in {"replace", "remove"}:
            breaking.append(f"Field type change on {ot_name}: {op} {path}")
        if op == "remove" and _RE_OBJECT_TYPE.fullmatch(path):
            breaking.append(f"ObjectType removed: {ot_name}")

    @staticmethod
    def _handle_action_patch(
        op: str,
        path: str,
        at_name: Optional[str],
        affected_actions: List[str],
        breaking: List[str],
    ) -> None:
        if at_name and at_name not in affected_actions:
            affected_actions.append(at_name)
        if op == "remove" and _RE_ACTION_TYPE.fullmatch(path):
            breaking.append(f"ActionType removed: {at_name}")
        elif op == "replace" and "/parameters" in path:
            breaking.append(f"ActionType parameter change: {at_name} {path}")

    @staticmethod
    def _estimate_migration_cost(breaking_count: int) -> ImpactCost:
        """根据 breaking_changes 数量估算迁移成本"""
        if breaking_count <= 0:
            return ImpactCost.LOW
        if breaking_count <= 2:
            return ImpactCost.MEDIUM
        return ImpactCost.HIGH

    @staticmethod
    def _map_risk_level(
        cost: ImpactCost,
        object_count: int,
        action_count: int,
    ) -> RiskLevel:
        """根据成本 + 范围映射风险等级

        规则:
        - cost=HIGH 且同时影响 ObjectType 与 ActionType (跨类型破坏) -> CRITICAL
        - cost=HIGH (单一类型大量破坏)                          -> HIGH
        - cost=MEDIUM                                            -> MEDIUM
        - cost=LOW                                               -> LOW
        """
        if (
            cost == ImpactCost.HIGH
            and object_count > 0
            and action_count > 0
        ):
            return RiskLevel.CRITICAL
        if cost == ImpactCost.HIGH:
            return RiskLevel.HIGH
        if cost == ImpactCost.MEDIUM:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW


__all__ = ["ImpactAnalyzerImpl"]
