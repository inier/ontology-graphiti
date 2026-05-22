import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class GraphitiMemoryAdapter:
    """Graphiti 双时态图谱作为 OpenHarness 的长期记忆适配器"""

    def __init__(self, graph_manager=None):
        self._graph_manager = graph_manager

    @property
    def graph(self):
        if self._graph_manager is None:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    async def read(self, query: str, limit: int = 10) -> List[Dict]:
        results = self.graph.search(query, limit=limit)
        return [{"content": r.get("content", ""), "score": r.get("score", 0), **r} for r in results]

    async def write(self, event_type: str, content: str, metadata: Dict = None) -> bool:
        try:
            from datetime import timezone
            self.graph.add_episode(
                name=f"memory_{event_type}",
                content=content,
                source_description=f"OpenHarness Memory: {event_type}",
                reference_time=datetime.now(timezone.utc),
            )
            return True
        except Exception as e:
            logger.warning(f"GraphitiMemoryAdapter write failed: {e}")
            return False

    async def search_by_time_window(self, start: datetime, end: datetime,
                                     workspace_id: Optional[str] = None) -> List[Dict]:
        try:
            results = self.graph.query_temporal(
                valid_at=start.isoformat(),
                workspace_id=workspace_id,
            )
            return results or []
        except Exception as e:
            logger.warning(f"GraphitiMemoryAdapter time_window search failed: {e}")
            return []

    async def delete(self, episode_name: str) -> bool:
        logger.info(f"GraphitiMemoryAdapter: delete not supported for episode {episode_name}")
        return False

    async def count(self, workspace_id: Optional[str] = None) -> int:
        try:
            entities = self.graph.query_entities(
                {"limit": 1, "offset": 0},
                workspace_id=workspace_id,
            )
            return len(entities) if entities else 0
        except Exception:
            return 0
