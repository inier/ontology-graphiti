import logging
from typing import Dict, Any, Optional

from ..models.semantic_map import SemanticMap, SemanticMapStatus, SemanticMapSummary
from ..storage import Storage
from ..impl.semantic_map_generator import SemanticMapGenerator

logger = logging.getLogger("semantic_map_service")


class SemanticMapService:
    def __init__(self, storage=None, generator=None):
        self.storage = storage or Storage()
        if generator:
            self.generator = generator
        else:
            try:
                from odap.biz.core.ontology.services.ingest_service import IngestService
                from odap.biz.core.ontology.oms.services import get_oms_service
                self.generator = SemanticMapGenerator(
                    oms_storage=get_oms_service(),
                    ingest_storage=IngestService().storage,
                )
            except Exception as e:
                logger.warning(f"语义地图生成器存储注入失败: {e}，使用默认空存储")
                self.generator = SemanticMapGenerator()

    def create_semantic_map(self, **kwargs) -> Dict[str, Any]:
        name = kwargs.get("name", "")
        ontology_version_id = kwargs.get("ontology_version_id", "")
        ontology_id = kwargs.get("ontology_id", "")

        if not name:
            return {"status": "error", "message": "名称不能为空"}
        if not ontology_version_id:
            return {"status": "error", "message": "本体版本ID不能为空"}
        if not ontology_id:
            return {"status": "error", "message": "本体ID不能为空"}

        semantic_map = self.generator.generate(
            name=name,
            ontology_version_id=ontology_version_id,
            ontology_id=ontology_id,
            scenario_id=kwargs.get("scenario_id"),
            description=kwargs.get("description", ""),
            created_by=kwargs.get("created_by", "system"),
            generation_config=kwargs.get("generation_config"),
        )

        self.storage.save(semantic_map)

        return self._to_response(semantic_map)

    def get_semantic_map(self, map_id: str) -> Dict[str, Any]:
        semantic_map = self.storage.get(map_id)
        if not semantic_map:
            return {"status": "error", "message": "语义地图不存在"}
        return self._to_response(semantic_map)

    def list_semantic_maps(
        self,
        ontology_version_id: Optional[str] = None,
        ontology_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        if ontology_version_id:
            maps = self.storage.list_by_version(ontology_version_id)
        elif ontology_id:
            maps = self.storage.list_by_ontology(ontology_id)
        elif scenario_id:
            maps = self.storage.list_by_scenario(scenario_id)
        else:
            maps = self.storage.list_all(limit=limit)

        summaries = []
        for m in maps:
            summaries.append({
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "ontology_version_id": m.ontology_version_id,
                "ontology_id": m.ontology_id,
                "scenario_id": m.scenario_id,
                "status": m.status.value,
                "total_objects": m.statistics.total_objects,
                "total_relations": m.statistics.total_relations,
                "total_clusters": m.statistics.total_clusters,
                "created_at": m.created_at.isoformat() if hasattr(m.created_at, "isoformat") else str(m.created_at),
                "created_by": m.created_by,
            })

        return {
            "semantic_maps": summaries,
            "total": len(summaries),
        }

    def delete_semantic_map(self, map_id: str) -> Dict[str, Any]:
        existing = self.storage.get(map_id)
        if not existing:
            return {"status": "error", "message": "语义地图不存在"}

        success = self.storage.delete(map_id)
        if success:
            return {"status": "ok", "message": "删除成功"}
        return {"status": "error", "message": "删除失败"}

    def regenerate(self, map_id: str) -> Dict[str, Any]:
        existing = self.storage.get(map_id)
        if not existing:
            return {"status": "error", "message": "语义地图不存在"}

        new_map = self.generator.generate(
            name=existing.name,
            ontology_version_id=existing.ontology_version_id,
            ontology_id=existing.ontology_id,
            scenario_id=existing.scenario_id,
            description=existing.description,
            created_by=existing.created_by,
            generation_config=existing.generation_config,
        )

        new_map.id = existing.id
        new_map.created_at = existing.created_at

        self.storage.save(new_map)
        return self._to_response(new_map)

    def get_map_graph(self, map_id: str) -> Dict[str, Any]:
        semantic_map = self.storage.get(map_id)
        if not semantic_map:
            return {"status": "error", "message": "语义地图不存在"}

        nodes = []
        for obj in semantic_map.objects:
            nodes.append({
                "id": obj.object_id,
                "entity_id": obj.entity_id,
                "name": obj.name,
                "type": obj.object_type,
                "cluster": obj.cluster,
                "properties": obj.properties,
                "type_definition_id": obj.type_definition_id,
                "type_definition_name": obj.type_definition_name,
            })

        edges = []
        for rel in semantic_map.relations:
            edges.append({
                "id": rel.relation_id,
                "source": rel.source_object_id,
                "target": rel.target_object_id,
                "type": rel.relation_type,
                "display_name": rel.display_name,
                "properties": rel.properties,
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "clusters": [c.model_dump() for c in semantic_map.clusters],
            "statistics": semantic_map.statistics.model_dump(),
        }

    def _to_response(self, semantic_map: SemanticMap) -> Dict[str, Any]:
        return {
            "id": semantic_map.id,
            "name": semantic_map.name,
            "description": semantic_map.description,
            "ontology_version_id": semantic_map.ontology_version_id,
            "ontology_id": semantic_map.ontology_id,
            "scenario_id": semantic_map.scenario_id,
            "status": semantic_map.status.value,
            "objects": [o.model_dump() for o in semantic_map.objects],
            "relations": [r.model_dump() for r in semantic_map.relations],
            "clusters": [c.model_dump() for c in semantic_map.clusters],
            "statistics": semantic_map.statistics.model_dump(),
            "generation_config": semantic_map.generation_config,
            "error_message": semantic_map.error_message,
            "created_at": semantic_map.created_at.isoformat() if hasattr(semantic_map.created_at, "isoformat") else str(semantic_map.created_at),
            "created_by": semantic_map.created_by,
            "updated_at": semantic_map.updated_at.isoformat() if semantic_map.updated_at and hasattr(semantic_map.updated_at, "isoformat") else semantic_map.updated_at,
        }
