"""ProvOMapper — 审计事件 → PROV-O 映射（扩展 ADR-074 §增补）。

映射规则（ADR-074 增补 §2）：
- AuditEvent 的 action/event_type → prov:Activity
- resource → prov:Entity（资源对象）
- actor → prov:Agent（操作者）
- 关联：wasGeneratedBy / used / wasAssociatedWith / wasDerivedFrom / wasInformedBy

事件类型 → Activity 语义（按审计项分类）：
- data.ingest        → 数据采集（prov:Activity，generated 原始数据 Entity）
- 抽取类             → 抽取活动
- 确认类（*create/update）→ 确认活动
- agent.decision/推理 → 推理活动
- query.execute      → 查询活动
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# PROV-O 命名空间
PROV = "http://www.w3.org/ns/prov#"
ODAP = "https://odap.local/prov/"


class ProvOMapper:
    """审计事件 → PROV-O 三元组映射器"""

    def __init__(self, base_uri: str = ODAP):
        self.base_uri = base_uri

    def map_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """将单个审计事件（dict）映射为 PROV-O 三元组列表。

        Args:
            event: AuditEvent.model_dump() 或扁平 dict

        Returns:
            {
                "activity": activity_iri,
                "agent": agent_iri,
                "entity": entity_iri,
                "triples": [(subj, pred, obj), ...],
            }
        """
        event_id = event.get("id") or event.get("event_id") or ""
        event_type = str(event.get("event_type", ""))
        action = str(event.get("action", ""))
        activity_iri = f"{self.base_uri}activity/{event_id}"

        actor = event.get("actor", {}) or {}
        actor_id = actor.get("actor_id", "") if isinstance(actor, dict) else ""
        agent_iri = f"{self.base_uri}agent/{actor_id}" if actor_id else f"{self.base_uri}agent/system"

        resource = event.get("resource", {}) or {}
        resource_id = resource.get("resource_id", "") if isinstance(resource, dict) else ""
        entity_iri = f"{self.base_uri}entity/{resource_id}" if resource_id else f"{self.base_uri}entity/{event_id}"

        triples: List[tuple] = []
        # Activity 声明
        triples.append((activity_iri, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"{PROV}Activity"))
        triples.append((activity_iri, f"{PROV}startedAtTime", self._literal_time(event.get("timestamp"))))

        # Agent 声明 + wasAssociatedWith
        triples.append((agent_iri, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"{PROV}Agent"))
        if actor_id:
            triples.append((agent_iri, f"{PROV}label", self._literal(actor.get("actor_name", ""))))
        triples.append((activity_iri, f"{PROV}wasAssociatedWith", agent_iri))

        # Entity 声明 + 关联
        triples.append((entity_iri, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"{PROV}Entity"))
        triples.append((entity_iri, f"{PROV}wasGeneratedBy", activity_iri))
        if resource_id:
            triples.append((entity_iri, f"{PROV}label", self._literal(resource.get("resource_name", resource_id))))

        # 按审计项补充关系（活动类型 → used/derived/informed）
        self._add_semantic_links(triples, activity_iri, entity_iri, event_type, action)

        return {
            "activity": activity_iri,
            "agent": agent_iri,
            "entity": entity_iri,
            "triples": triples,
        }

    def map_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量映射审计事件"""
        return [self.map_event(e) for e in events]

    def _add_semantic_links(self, triples, activity_iri, entity_iri, event_type, action):
        """按审计项类型补充 PROV-O 语义关系"""
        et = event_type.lower()
        # 推理类：结论 wasDerivedFrom 输入事实
        if "decision" in et or "reasoning" in et or "infer" in et:
            triples.append((entity_iri, f"{PROV}wasDerivedFrom", f"{self.base_uri}entity/input_facts"))
        # 抽取/摄入类：活动 used 原始数据
        if "ingest" in et or "extract" in et or "extraction" in et:
            triples.append((activity_iri, f"{PROV}used", f"{self.base_uri}entity/raw_data"))
        # 查询类：仅活动，无实体生成（轻量）
        if "query" in et:
            triples.append((activity_iri, f"{PROV}label", self._literal(f"query:{action}")))

    @staticmethod
    def _literal(val: Any) -> str:
        if val is None:
            return '""'
        return f'"{str(val)}"'

    @staticmethod
    def _literal_time(val: Any) -> str:
        if val is None:
            return '""'
        return f'"{str(val)}"'


__all__ = ["ProvOMapper"]
