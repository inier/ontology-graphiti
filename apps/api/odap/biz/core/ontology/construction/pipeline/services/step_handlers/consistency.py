"""Step 3: 一致性检查 — 检测冲突、冗余、孤立节点"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ConsistencyResult:
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    redundancies: List[Dict[str, Any]] = field(default_factory=list)
    orphans: List[str] = field(default_factory=list)
    cycles: List[List[str]] = field(default_factory=list)
    schema_violations: List[Dict[str, Any]] = field(default_factory=list)
    total_issues: int = 0

    @property
    def is_clean(self) -> bool:
        return self.total_issues == 0


class ConsistencyCheckStep:
    """一致性检查处理器"""

    async def execute(
        self,
        entities: List[Dict],
        relations: List[Dict],
        ontology_schema: Dict = None,
    ) -> ConsistencyResult:
        result = ConsistencyResult()

        # 1. 冲突检测: 同类型实体有冲突属性
        type_groups: Dict[str, List[Dict]] = {}
        for e in entities:
            etype = e.get("entity_type", e.get("type", "unknown"))
            if etype not in type_groups:
                type_groups[etype] = []
            type_groups[etype].append(e)

        for etype, ents in type_groups.items():
            props_seen = {}
            for e in ents:
                props = e.get("properties", {})
                for key, val in props.items():
                    if key in props_seen and props_seen[key] != val:
                        result.conflicts.append({
                            "type": "property_conflict",
                            "entity_type": etype,
                            "property": key,
                            "values": [props_seen[key], val],
                        })
                    props_seen[key] = val

        # 2. 冗余检测: 几乎相同的实体（同类型+同名+相似属性）
        for etype, ents in type_groups.items():
            name_groups: Dict[str, List[Dict]] = {}
            for e in ents:
                name = e.get("name", "")
                if name not in name_groups:
                    name_groups[name] = []
                name_groups[name].append(e)
            for name, duplicates in name_groups.items():
                if len(duplicates) > 1:
                    result.redundancies.append({
                        "type": "duplicate_entity",
                        "entity_type": etype,
                        "name": name,
                        "count": len(duplicates),
                    })

        # 3. 孤立节点检测
        linked_ids = set()
        for r in relations:
            linked_ids.add(r.get("source_entity_id", r.get("source", "")))
            linked_ids.add(r.get("target_entity_id", r.get("target", "")))
        for e in entities:
            eid = e.get("id", e.get("entity_id", ""))
            if eid and eid not in linked_ids:
                result.orphans.append(eid)

        result.total_issues = (
            len(result.conflicts)
            + len(result.redundancies)
            + len(result.orphans)
            + len(result.cycles)
            + len(result.schema_violations)
        )
        logger.info("Consistency: %d total issues found", result.total_issues)
        return result
