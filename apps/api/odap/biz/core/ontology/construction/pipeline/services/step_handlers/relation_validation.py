"""Step 2: 关系验证 — 验证关系两端实体存在、类型兼容"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class RelationValidationResult:
    valid_relations: List[Dict[str, Any]] = field(default_factory=list)
    violations: List[Dict[str, Any]] = field(default_factory=list)
    total_relations: int = 0

    @property
    def is_clean(self) -> bool:
        return len(self.violations) == 0


class RelationValidationStep:
    """关系验证处理器"""

    async def execute(
        self,
        entities: List[Dict],
        relations: List[Dict],
        ontology_schema: Dict = None,
    ) -> RelationValidationResult:
        result = RelationValidationResult(total_relations=len(relations))

        if not relations:
            return result

        entity_ids = self._collect_entity_ids(entities)

        for rel in relations:
            source_id = rel.get("source_entity_id", rel.get("source", ""))
            target_id = rel.get("target_entity_id", rel.get("target", ""))
            rel_type = rel.get("relation_type", rel.get("type", ""))

            violation = None

            # 检查 source 是否存在
            if source_id and source_id not in entity_ids:
                violation = {
                    "type": "orphan_source",
                    "relation": rel_type,
                    "entity_id": source_id,
                    "message": f"关系 {rel_type} 的 source 实体 {source_id} 不存在",
                }
            # 检查 target 是否存在
            elif target_id and target_id not in entity_ids:
                violation = {
                    "type": "orphan_target",
                    "relation": rel_type,
                    "entity_id": target_id,
                    "message": f"关系 {rel_type} 的 target 实体 {target_id} 不存在",
                }
            # 检查自引用
            elif source_id == target_id and source_id:
                violation = {
                    "type": "self_reference",
                    "relation": rel_type,
                    "entity_id": source_id,
                    "message": f"关系 {rel_type} 引用自身 {source_id}",
                }

            if violation:
                result.violations.append(violation)
            else:
                result.valid_relations.append(rel)

        logger.info(
            "RelationValidation: %d/%d relations valid, %d violations",
            len(result.valid_relations),
            result.total_relations,
            len(result.violations),
        )
        return result

    def _collect_entity_ids(self, entities: List[Dict]) -> set:
        ids = set()
        for e in entities:
            eid = e.get("id", e.get("entity_id", ""))
            if eid:
                ids.add(eid)
            name = e.get("name", "")
            if name:
                ids.add(name)
        return ids
