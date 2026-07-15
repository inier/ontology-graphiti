import logging
import uuid
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class KnowledgeNavigator:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._navigation_history: List[str] = []
        self._initialized = True

    def navigate(self, entity_id: str, direction: str = "outbound", depth: int = 1) -> Dict[str, Any]:
        path = [entity_id]
        related = []
        context = {"entity_id": entity_id, "neighbors": [], "attributes": {}, "history": []}

        try:
            from odap.infra.query.service import QueryService
            qs = QueryService()
            qr = qs.execute(
                workspace_id="default",
                query=f".topo neighbors(id='{entity_id}', direction='{direction}', depth={depth})",
                limit=20,
            )
            if qr.rows:
                path.extend([n.get("id", str(uuid.uuid4())) for n in qr.rows[:5]])
                related = qr.rows
            entity_qr = qs.execute(
                workspace_id="default",
                query=f".entity with(id='{entity_id}')",
                limit=1,
            )
            if entity_qr.rows:
                context["attributes"] = entity_qr.rows[0].get("properties", {})
        except Exception as e:
            logger.debug("KnowledgeNavigator navigate fallback: %s", e)

        context["neighbors"] = related
        self._navigation_history.extend(path)

        result = {
            "navigation_id": str(uuid.uuid4()),
            "entity_id": entity_id,
            "direction": direction,
            "depth": depth,
            "navigation_path": path,
            "related_entities": related,
            "entity_context": context,
        }
        self._cache[result["navigation_id"]] = result
        return result

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 10) -> Dict[str, Any]:
        results = []
        try:
            from odap.infra.query.service import QueryService
            qs = QueryService()
            qr = qs.execute(
                workspace_id=filters.get("workspace_id", "default") if filters else "default",
                query=f".entity with(search='{query}')" if query else ".entity",
                limit=limit,
            )
            results = qr.rows
        except Exception as e:
            logger.debug("KnowledgeNavigator search fallback: %s", e)

        return {
            "search_id": str(uuid.uuid4()),
            "query": query,
            "results": results,
            "total": len(results),
        }

    def get_reasoning_path(self, from_id: str, to_id: str, max_depth: int = 5) -> Dict[str, Any]:
        path_nodes = []
        try:
            from odap.infra.query.service import QueryService
            qs = QueryService()
            subgraph = qs.execute(
                workspace_id="default",
                query=f".topo path(from='{from_id}', to='{to_id}', max_hops={max_depth})",
                limit=1,
            )
            if subgraph.rows:
                path_nodes = subgraph.rows
        except Exception as e:
            logger.debug("KnowledgeNavigator reasoning_path fallback: %s", e)

        return {
            "path_id": str(uuid.uuid4()),
            "from_id": from_id,
            "to_id": to_id,
            "path": path_nodes,
            "found": len(path_nodes) > 0,
        }

    def get_history(self, limit: int = 20) -> List[str]:
        return self._navigation_history[-limit:]
