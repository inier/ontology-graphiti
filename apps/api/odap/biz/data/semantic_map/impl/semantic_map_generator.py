import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

from ..models.semantic_map import (
    SemanticMap, SemanticMapObject, SemanticMapRelation,
    SemanticMapCluster, SemanticMapStatistics, SemanticMapStatus,
)

logger = logging.getLogger("semantic_map_generator")


class SemanticMapGenerator:
    """
    语义地图生成器

    生成流程:
    1. 加载本体版本数据（实体/关系/事件）
    2. 匹配本体定义（OMS ObjectTypeDefinition），为实体赋予类型定义
    3. 构建语义对象（SemanticMapObject），合并实体属性与类型定义
    4. 构建语义关系（SemanticMapRelation），从 OntologyRelation 提取
    5. 按类型聚类，生成 SemanticMapCluster
    6. 计算统计信息
    7. 组装 SemanticMap
    """

    ENTITY_TYPE_TO_OMS_TYPE = {
        "Unit": "Unit",
        "Equipment": "Equipment",
        "Location": "Location",
        "Person": "Person",
        "Organization": "Organization",
        "EventNode": "Event",
    }

    def __init__(self, oms_storage=None, ingest_storage=None):
        self._oms_storage = oms_storage
        self._ingest_storage = ingest_storage

    def generate(
        self,
        name: str,
        ontology_version_id: str,
        ontology_id: str,
        scenario_id: Optional[str] = None,
        description: str = "",
        created_by: str = "system",
        generation_config: Optional[Dict[str, Any]] = None,
    ) -> SemanticMap:
        config = generation_config or {}

        semantic_map = SemanticMap(
            name=name,
            description=description,
            ontology_version_id=ontology_version_id,
            ontology_id=ontology_id,
            scenario_id=scenario_id,
            status=SemanticMapStatus.GENERATING,
            created_by=created_by,
            generation_config=config,
        )

        try:
            entities = self._load_entities(ontology_id, scenario_id)
            relations = self._load_relations(ontology_id, scenario_id)

            type_definitions = self._load_type_definitions()

            objects = self._build_objects(entities, type_definitions)
            object_index = {o.entity_id: o for o in objects}

            map_relations = self._build_relations(relations, object_index)

            clusters = self._build_clusters(objects)

            statistics = self._calculate_statistics(objects, map_relations, clusters)

            semantic_map.objects = objects
            semantic_map.relations = map_relations
            semantic_map.clusters = clusters
            semantic_map.statistics = statistics
            semantic_map.status = SemanticMapStatus.COMPLETED

        except Exception as e:
            logger.error(f"语义地图生成失败: {e}")
            semantic_map.status = SemanticMapStatus.FAILED
            semantic_map.error_message = str(e)

        return semantic_map

    def _load_entities(self, ontology_id: str, scenario_id: Optional[str]) -> List[Dict[str, Any]]:
        if self._ingest_storage is None:
            return []

        if scenario_id:
            return self._ingest_storage.get_scenario_entities(scenario_id)

        registry = self._ingest_storage.get_registry_entities(ontology_id=ontology_id)
        return registry

    def _load_relations(self, ontology_id: str, scenario_id: Optional[str]) -> List[Dict[str, Any]]:
        if self._ingest_storage is None:
            return []

        if scenario_id:
            result = self._ingest_storage.get_scenario_relations(scenario_id)
            return result.get("links", [])

        return []

    def _load_type_definitions(self) -> Dict[str, Dict[str, Any]]:
        if self._oms_storage is None:
            return {}

        type_defs = {}
        try:
            for obj_type in self._oms_storage.list_object_types(active_only=True):
                type_defs[obj_type.get("type_id", "")] = obj_type
                type_defs[obj_type.get("name", "")] = obj_type
        except Exception as e:
            logger.warning(f"加载 OMS 类型定义失败: {e}")

        return type_defs

    def _build_objects(
        self,
        entities: List[Dict[str, Any]],
        type_definitions: Dict[str, Dict[str, Any]],
    ) -> List[SemanticMapObject]:
        objects = []
        for entity in entities:
            entity_type = entity.get("entity_type", "")
            oms_type_name = self.ENTITY_TYPE_TO_OMS_TYPE.get(entity_type, entity_type)
            type_def = type_definitions.get(oms_type_name)

            merged_properties = {}
            if entity.get("basic_properties"):
                merged_properties["basic"] = entity["basic_properties"]
            if entity.get("statistical_properties"):
                merged_properties["statistical"] = entity["statistical_properties"]
            if entity.get("capabilities"):
                merged_properties["capabilities"] = entity["capabilities"]

            type_def_id = None
            type_def_name = None
            if type_def:
                type_def_id = type_def.get("type_id")
                type_def_name = type_def.get("display_name") or type_def.get("name")
                if type_def.get("properties"):
                    prop_schema = {}
                    for p in type_def["properties"]:
                        prop_schema[p.get("name")] = {
                            "type": p.get("property_type"),
                            "required": p.get("required", False),
                            "display_name": p.get("display_name", p.get("name")),
                        }
                    merged_properties["_schema"] = prop_schema

            obj = SemanticMapObject(
                entity_id=entity.get("entity_id") or entity.get("canonical_id", ""),
                object_type=oms_type_name,
                name=entity.get("name", ""),
                name_en=entity.get("name_en", ""),
                aliases=entity.get("aliases", []),
                properties=merged_properties,
                type_definition_id=type_def_id,
                type_definition_name=type_def_name,
                confidence=entity.get("confidence", 1.0),
            )
            objects.append(obj)

        return objects

    def _build_relations(
        self,
        raw_relations: List[Dict[str, Any]],
        object_index: Dict[str, SemanticMapObject],
    ) -> List[SemanticMapRelation]:
        map_relations = []

        for raw in raw_relations:
            source_id = raw.get("source", "")
            target_id = raw.get("target", "")

            if source_id not in object_index or target_id not in object_index:
                continue

            source_obj = object_index[source_id]
            target_obj = object_index[target_id]

            rel = SemanticMapRelation(
                relation_id=raw.get("id", ""),
                source_object_id=source_obj.object_id,
                target_object_id=target_obj.object_id,
                relation_type=raw.get("type", "related_to"),
                display_name=raw.get("type", "related_to"),
                properties=raw.get("properties", {}),
                is_bidirectional=raw.get("is_bidirectional", False),
            )

            source_obj.relation_ids.append(rel.relation_id)
            target_obj.relation_ids.append(rel.relation_id)

            map_relations.append(rel)

        return map_relations

    def _build_clusters(self, objects: List[SemanticMapObject]) -> List[SemanticMapCluster]:
        type_groups: Dict[str, List[SemanticMapObject]] = defaultdict(list)
        for obj in objects:
            type_groups[obj.object_type].append(obj)

        clusters = []
        for type_name, group in type_groups.items():
            cluster = SemanticMapCluster(
                cluster_id=f"cluster-{type_name.lower()}",
                cluster_name=type_name,
                cluster_type="entity_type",
                object_ids=[o.object_id for o in group],
                properties={"count": len(group)},
            )
            for obj in group:
                obj.cluster = cluster.cluster_id
            clusters.append(cluster)

        return clusters

    def _calculate_statistics(
        self,
        objects: List[SemanticMapObject],
        relations: List[SemanticMapRelation],
        clusters: List[SemanticMapCluster],
    ) -> SemanticMapStatistics:
        objects_by_type: Dict[str, int] = defaultdict(int)
        for obj in objects:
            objects_by_type[obj.object_type] += 1

        relations_by_type: Dict[str, int] = defaultdict(int)
        for rel in relations:
            relations_by_type[rel.relation_type] += 1

        avg_relations = 0.0
        if objects:
            total_rels = sum(len(o.relation_ids) for o in objects)
            avg_relations = round(total_rels / len(objects), 2)

        typed_count = sum(1 for o in objects if o.type_definition_id)
        coverage_score = round(typed_count / len(objects), 2) if objects else 0.0

        return SemanticMapStatistics(
            total_objects=len(objects),
            total_relations=len(relations),
            total_clusters=len(clusters),
            objects_by_type=dict(objects_by_type),
            relations_by_type=dict(relations_by_type),
            avg_relations_per_object=avg_relations,
            coverage_score=coverage_score,
        )
