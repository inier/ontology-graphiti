from typing import Any, Dict, List, Optional


class EntitySourceImpl:
    def __init__(self, graph_manager=None):
        self._graph_manager = graph_manager

    def _get_graph_manager(self):
        if self._graph_manager is None:
            from odap.infra.graph import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    def query_entities(self, filters: Dict[str, Any], workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        gm = self._get_graph_manager()
        entity_type = filters.get("type") or filters.get("entity_type")
        area = filters.get("area")
        if entity_type or area:
            return gm.query_entities(entity_type=entity_type, area=area, workspace_id=workspace_id)
        return gm.get_all_entities(workspace_id=workspace_id)

    def get_entity(self, entity_id: str, workspace_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        gm = self._get_graph_manager()
        return gm.get_entity(entity_id)

    def search_entities(self, query: str, top_k: int = 10, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        gm = self._get_graph_manager()
        if gm._mode in ("neo4j_driver", "graphiti") and gm._connected:
            try:
                return gm.search_hybrid(query_text=query, top_k=top_k)
            except Exception:
                pass
        return gm.search(query=query, limit=top_k)
