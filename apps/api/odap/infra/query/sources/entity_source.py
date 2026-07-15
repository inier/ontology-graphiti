from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class EntitySourceImpl:
    def __init__(self, graph_manager=None, model_storage=None):
        self._graph_manager = graph_manager
        self._model_storage = model_storage

    def _get_graph_manager(self):
        if self._graph_manager is None:
            from odap.infra.graph import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    def _get_model_storage(self):
        """获取模型存储（备用搜索源）

        通过构造函数注入获取，避免 infra 层直接导入 design 层（P0-3）。
        """
        return self._model_storage

    def query_entities(self, filters: Dict[str, Any], workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        gm = self._get_graph_manager()
        entity_type = filters.get("type") or filters.get("entity_type")
        area = filters.get("area")
        if entity_type or area:
            result = gm.query_entities(entity_type=entity_type, area=area, workspace_id=workspace_id)
            if result:
                return result
        else:
            result = gm.get_all_entities(workspace_id=workspace_id)
            if result:
                return result
        # Fallback: 从模型存储查询
        return self._query_model_storage(entity_type, workspace_id)

    def _query_model_storage(self, entity_type: Optional[str] = None,
                              workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        storage = self._get_model_storage()
        if not storage:
            return []
        try:
            data = storage.list_instances(type_id=entity_type, workspace_id=workspace_id, page_size=200)
            if isinstance(data, dict):
                data = data.get("instances", data.get("items", data.get("data", [])))
            if not data:
                data = storage.list_instances(type_id=entity_type, workspace_id="default", page_size=200)
                if isinstance(data, dict):
                    data = data.get("instances", data.get("items", data.get("data", [])))
            return data if isinstance(data, list) else []
        except Exception as e:
            logger.debug("Model storage query failed: %s", e)
            return []

    def get_entity(self, entity_id: str, workspace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        gm = self._get_graph_manager()
        result = gm.get_entity(entity_id)
        if result:
            return result
        # Fallback to model storage
        storage = self._get_model_storage()
        if storage:
            try:
                return storage.get_instance(entity_id)
            except Exception:
                pass
        return None

    def search_entities(self, query: str, top_k: int = 10, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        # Try Neo4j/Graphiti search first
        gm = self._get_graph_manager()
        if gm._mode in ("neo4j_driver", "graphiti") and gm._connected:
            try:
                result = gm.search_hybrid(query_text=query, top_k=top_k)
                if result:
                    return result
            except Exception:
                pass
        neo4j_result = gm.search(query=query, limit=top_k)
        if neo4j_result:
            return neo4j_result

        # Fallback: search model storage by matching name/properties
        storage = self._get_model_storage()
        if not storage:
            return []
        try:
            all_instances = storage.list_instances(workspace_id=workspace_id or "default", page_size=500)
            if isinstance(all_instances, dict):
                all_instances = all_instances.get("instances", all_instances.get("items", []))
            if not all_instances:
                all_instances = storage.list_instances(workspace_id="default", page_size=500)
                if isinstance(all_instances, dict):
                    all_instances = all_instances.get("instances", all_instances.get("items", []))

            matched = []
            query_lower = query.lower()
            for inst in (all_instances if isinstance(all_instances, list) else []):
                props = inst.get("properties", {})
                if isinstance(props, str):
                    try:
                        import json
                        props = json.loads(props)
                    except Exception:
                        continue
                # Search in name and all property values
                name = props.get("name", "")
                if query_lower in str(name).lower():
                    matched.append(inst)
                    continue
                for key, val in props.items():
                    if query_lower in str(val).lower():
                        matched.append(inst)
                        break
                if len(matched) >= top_k:
                    break
            return matched
        except Exception as e:
            logger.debug("Model storage search fallback failed: %s", e)
            return []
