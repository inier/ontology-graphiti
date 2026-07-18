import hashlib
import logging
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger("ontology_mapper")


# ODAP 5 output categories for entity classification
_ACTION_ENTITY_KEYWORDS = ("action", "act", "buy", "sell", "execute", "transfer", "perform")
_RULE_ENTITY_KEYWORDS = ("rule", "constraint", "policy", "regulation", "law")
_PROCESS_ENTITY_KEYWORDS = ("process", "workflow", "procedure", "flow", "step")


class OntologyMapper:
    """将 HE 抽取结果映射到 ODAP 本体结构

    根据 ontology_id 从 OntologyService 加载合法的类型名称集合，
    在 map 阶段对实体类型和关系类型进行校验与映射。
    """

    def __init__(self, ontology_id: str = "", strict: bool = True):
        self._ontology_id = ontology_id
        self._strict = strict
        self._object_type_names: Set[str] = set()
        self._link_type_names: Set[str] = set()

        if ontology_id:
            self._load_ontology_types()

    def _load_ontology_types(self) -> None:
        """从 OntologyService 加载合法的对象类型和关系类型名称"""
        try:
            from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

            svc = OntologyService()

            obj_result = svc.list_object_types(self._ontology_id)
            if obj_result.get("status") == "error":
                logger.warning(
                    "加载对象类型失败: %s", obj_result.get("message", "unknown")
                )
            else:
                for obj in obj_result.get("object_types", []):
                    name = obj.get("name")
                    if name:
                        self._object_type_names.add(name)

            link_result = svc.list_link_types(self._ontology_id)
            if link_result.get("status") == "error":
                logger.warning(
                    "加载关系类型失败: %s", link_result.get("message", "unknown")
                )
            else:
                for link in link_result.get("link_types", []):
                    name = link.get("name")
                    if name:
                        self._link_type_names.add(name)

            logger.info(
                "本体类型加载完成: ontology_id=%s, object_types=%d, link_types=%d",
                self._ontology_id,
                len(self._object_type_names),
                len(self._link_type_names),
            )
        except Exception as exc:
            logger.warning("加载本体类型异常: %s", exc)

    def map(self, ka: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """将 HE 抽取结果映射到 ODAP 本体结构

        Args:
            ka: 抽取结果，包含 "entities" 和 "relations" 列表

        Returns:
            映射后的结构，包含 "entities" 和 "relations"；
            输入无效时返回 {"status": "error", "message": "..."}
        """
        if not ka:
            return {"status": "error", "message": "抽取结果为空"}

        raw_entities = ka.get("entities")
        raw_relations = ka.get("relations")
        if raw_entities is None and raw_relations is None:
            return {"status": "error", "message": "抽取结果缺少 entities 和 relations"}

        mapped_entities = []
        for ent in (raw_entities or []):
            mapped = self._map_entity(ent)
            if mapped is not None:
                mapped_entities.append(mapped)

        mapped_relations = []
        for rel in (raw_relations or []):
            mapped = self._map_relation(rel)
            if mapped is not None:
                mapped_relations.append(mapped)

        logger.info(
            "本体映射完成: entities=%d→%d, relations=%d→%d",
            len(raw_entities or []),
            len(mapped_entities),
            len(raw_relations or []),
            len(mapped_relations),
        )

        return {
            "entities": mapped_entities,
            "relations": mapped_relations,
        }

    # ------------------------------------------------------------------
    # Multi-template merge (US2 / T056)
    # ------------------------------------------------------------------

    def merge_and_map(
        self,
        multi_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge multi-template extraction results and map to ODAP 5 classes.

        Steps:
            1. Collect entities and relations from all template results.
            2. Deduplicate entities by name (keep first, mark conflicts).
            3. Deduplicate relations by (source, relation_type, target).
            4. Classify entities into ODAP 5 classes:
               object_types, link_types, action_types, rule_types, process_types.
            5. Preserve source_template provenance per entity.

        Args:
            multi_results: List of {"entities": [...], "relations": [...],
                           "source_template": str}

        Returns:
            {
                "entities": [...],       # merged, deduplicated
                "relations": [...],      # merged, deduplicated
                "object_types": [...],
                "link_types": [...],
                "action_types": [...],
                "rule_types": [...],
                "process_types": [...],
                "conflicts": [...],      # name collisions with differing props
            }
        """
        if not multi_results:
            return {
                "entities": [],
                "relations": [],
                "object_types": [],
                "link_types": [],
                "action_types": [],
                "rule_types": [],
                "process_types": [],
                "conflicts": [],
            }

        merged_entities: List[Dict[str, Any]] = []
        seen_entity_names: Dict[str, Dict[str, Any]] = {}
        conflicts: List[Dict[str, Any]] = []

        merged_relations: List[Dict[str, Any]] = []
        seen_rel_keys: Set[Tuple[str, str, str]] = set()

        for result in multi_results:
            source_template = result.get("source_template", "unknown")

            # Merge entities
            for ent in result.get("entities", []):
                name = ent.get("name", "")
                original_type = ent.get("type", "")
                if not name or not original_type:
                    continue

                # Classify by original type BEFORE mapping (which may change type)
                category = self._classify_entity_category(original_type)

                if category == "object":
                    # Object entities go through full type validation
                    mapped = self._map_entity(ent)
                    if mapped is None:
                        continue
                else:
                    # Action/Rule/Process entities skip object_type validation
                    mapped = {
                        "entity_id": self._deterministic_entity_id(original_type, name),
                        "name": name,
                        "type": original_type,
                        "description": ent.get("description", ""),
                    }
                    raw_props = ent.get("properties", {})
                    if isinstance(raw_props, dict):
                        mapped.update(self._map_properties(raw_props))

                # Add source_template provenance
                mapped["source_template"] = source_template

                if name in seen_entity_names:
                    # Check for conflicts (different properties)
                    existing = seen_entity_names[name]
                    if self._entities_conflict(existing, mapped):
                        conflicts.append({
                            "name": name,
                            "source_template_1": existing.get("source_template", ""),
                            "source_template_2": source_template,
                            "field": "properties",
                        })
                    # Keep first occurrence, skip duplicate
                    continue

                seen_entity_names[name] = mapped
                merged_entities.append(mapped)

            # Merge relations
            for rel in result.get("relations", []):
                source = rel.get("source", "")
                target = rel.get("target", "")
                rel_type = rel.get("relation_type", "")
                key = (source, rel_type, target)

                if key in seen_rel_keys:
                    continue

                mapped_rel = self._map_relation(rel)
                if mapped_rel is not None:
                    mapped_rel["source_template"] = source_template
                    seen_rel_keys.add(key)
                    merged_relations.append(mapped_rel)

        # Classify entities into ODAP 5 classes
        object_types: List[Dict[str, Any]] = []
        action_types: List[Dict[str, Any]] = []
        rule_types: List[Dict[str, Any]] = []
        process_types: List[Dict[str, Any]] = []
        link_types: List[Dict[str, Any]] = []

        for ent in merged_entities:
            category = self._classify_entity_category(ent.get("type", ""))
            type_entry = {
                "name": ent.get("name", ""),
                "type": ent.get("type", ""),
                "description": ent.get("description", ""),
                "source_template": ent.get("source_template", ""),
            }
            if category == "action":
                action_types.append(type_entry)
            elif category == "rule":
                rule_types.append(type_entry)
            elif category == "process":
                process_types.append(type_entry)
            else:
                object_types.append(type_entry)

        # Relations → link_types
        for rel in merged_relations:
            link_types.append({
                "name": rel.get("relation_type", ""),
                "source": rel.get("source", ""),
                "target": rel.get("target", ""),
                "source_template": rel.get("source_template", ""),
            })

        logger.info(
            "merge_and_map 完成: entities=%d, relations=%d, conflicts=%d, "
            "object_types=%d, action_types=%d, rule_types=%d, process_types=%d",
            len(merged_entities),
            len(merged_relations),
            len(conflicts),
            len(object_types),
            len(action_types),
            len(rule_types),
            len(process_types),
        )

        return {
            "entities": merged_entities,
            "relations": merged_relations,
            "object_types": object_types,
            "link_types": link_types,
            "action_types": action_types,
            "rule_types": rule_types,
            "process_types": process_types,
            "conflicts": conflicts,
        }

    @staticmethod
    def _entities_conflict(e1: Dict[str, Any], e2: Dict[str, Any]) -> bool:
        """Check if two entities with same name have conflicting properties."""
        # Compare description and properties
        desc1 = e1.get("description", "")
        desc2 = e2.get("description", "")
        if desc1 != desc2:
            return True
        # Compare basic_properties if present
        props1 = e1.get("basic_properties", e1.get("properties", {}))
        props2 = e2.get("basic_properties", e2.get("properties", {}))
        if props1 != props2:
            return True
        return False

    @staticmethod
    def _classify_entity_category(entity_type: str) -> str:
        """Classify an entity type into an ODAP category.

        Returns one of: "object", "action", "rule", "process".
        """
        t_lower = entity_type.lower()
        if any(kw in t_lower for kw in _ACTION_ENTITY_KEYWORDS):
            return "action"
        if any(kw in t_lower for kw in _RULE_ENTITY_KEYWORDS):
            return "rule"
        if any(kw in t_lower for kw in _PROCESS_ENTITY_KEYWORDS):
            return "process"
        return "object"

    def _map_entity(self, ent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """映射单个实体"""
        entity_type = ent.get("type", "")
        entity_name = ent.get("name", "")

        if not entity_type or not entity_name:
            logger.warning("实体缺少 type 或 name，跳过: %s", ent)
            return None

        if self._object_type_names and entity_type not in self._object_type_names:
            if self._strict:
                logger.warning(
                    "实体类型 '%s' 不在本体定义中，strict 模式跳过: %s",
                    entity_type,
                    entity_name,
                )
                return None
            else:
                logger.info(
                    "实体类型 '%s' 不在本体定义中，标记为 unclassified: %s",
                    entity_type,
                    entity_name,
                )
                entity_type = "unclassified"

        entity_id = self._deterministic_entity_id(entity_type, entity_name)
        raw_props = ent.get("properties", {})
        if not isinstance(raw_props, dict):
            raw_props = {}

        mapped_props = self._map_properties(raw_props)

        return {
            "entity_id": entity_id,
            "name": entity_name,
            "type": entity_type,
            "description": ent.get("description", ""),
            **mapped_props,
        }

    def _map_relation(self, rel: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """映射单个关系"""
        source = rel.get("source", "")
        target = rel.get("target", "")
        relation_type = rel.get("relation_type", "")

        if not source or not target or not relation_type:
            logger.warning("关系缺少 source/target/relation_type，跳过: %s", rel)
            return None

        if self._link_type_names and relation_type not in self._link_type_names:
            if self._strict:
                logger.warning(
                    "关系类型 '%s' 不在本体定义中，strict 模式跳过: %s→%s",
                    relation_type,
                    source,
                    target,
                )
                return None
            else:
                logger.info(
                    "关系类型 '%s' 不在本体定义中，标记为 unclassified: %s→%s",
                    relation_type,
                    source,
                    target,
                )
                relation_type = "unclassified"

        raw_props = rel.get("properties", {})
        if not isinstance(raw_props, dict):
            raw_props = {}

        return {
            "source": source,
            "target": target,
            "relation_type": relation_type,
            "properties": raw_props,
        }

    @staticmethod
    def _deterministic_entity_id(entity_type: str, entity_name: str) -> str:
        """基于 entity_type:entity_name 生成确定性 ID"""
        return hashlib.sha256(f"{entity_type}:{entity_name}".encode()).hexdigest()[:16]

    @staticmethod
    def _map_properties(raw_props: Dict[str, Any]) -> Dict[str, Any]:
        """将原始属性拆分为四层结构

        - basic_properties: 名称、描述、类型及简单字符串/数值字段
        - statistical_properties: 含 count/rate/ratio/avg/sum/total 的字段
        - capabilities: 含 can_/supports_/enabled 的字段
        - constraints: 含 max_/min_/limit/constraint 的字段
        """
        basic: Dict[str, Any] = {}
        statistical: Dict[str, Any] = {}
        capabilities: Dict[str, Any] = {}
        constraints: Dict[str, Any] = {}

        stat_keywords = ("count", "rate", "ratio", "avg", "sum", "total")
        cap_keywords = ("can_", "supports_", "enabled")
        constraint_keywords = ("max_", "min_", "limit", "constraint")

        for key, value in raw_props.items():
            key_lower = key.lower()

            if key_lower in ("name", "description", "type"):
                basic[key] = value
            elif any(kw in key_lower for kw in stat_keywords):
                statistical[key] = value
            elif any(kw in key_lower for kw in cap_keywords):
                capabilities[key] = value
            elif any(kw in key_lower for kw in constraint_keywords):
                constraints[key] = value
            else:
                basic[key] = value

        return {
            "basic_properties": basic,
            "statistical_properties": statistical,
            "capabilities": capabilities,
            "constraints": constraints,
        }
