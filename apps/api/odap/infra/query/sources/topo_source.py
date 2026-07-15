from typing import Any, Dict, List, Optional


class TopoSourceImpl:
    def __init__(self, graph_manager=None):
        self._graph_manager = graph_manager

    def _get_graph_manager(self):
        if self._graph_manager is None:
            from odap.infra.graph import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    def get_neighbors(self, entity_id: str, direction: str = "both", depth: int = 1, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        gm = self._get_graph_manager()
        return gm.get_neighbors(entity_id, direction=direction, depth=depth, workspace_id=workspace_id)

    def get_relations(self, entity_id: str, relation_type: Optional[str] = None, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        gm = self._get_graph_manager()
        relations = gm.get_entity_relations(entity_id)
        if relation_type:
            relations = [r for r in relations if r.get("type") == relation_type]
        return relations

    def traverse(self, start_id: str, max_depth: int = 3, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        gm = self._get_graph_manager()
        return gm.traverse(start_id, max_depth=max_depth, workspace_id=workspace_id)
