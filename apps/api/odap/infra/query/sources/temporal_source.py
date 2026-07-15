from typing import Any, Dict, List, Optional


class TemporalSource:
    def __init__(self):
        from odap.infra.graph import GraphManager
        self._graph_manager = GraphManager()

    def query(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        valid_time = params.get("valid_time")
        transaction_time = params.get("transaction_time")
        entity_type = params.get("type")
        return self._graph_manager.query_temporal(
            valid_time=valid_time,
            transaction_time=transaction_time,
            entity_type=entity_type,
        )

    def query_at_time(self, timestamp: str) -> List[Dict[str, Any]]:
        return self._graph_manager.query_at_valid_time(valid_time=timestamp)

    def query_history(self, entity_id: str) -> List[Dict[str, Any]]:
        return self._graph_manager.get_entity_history(entity_id)

    def query_range(self, start_time: str, end_time: str, entity_type: str = None) -> List[Dict[str, Any]]:
        results = self._graph_manager.query_temporal(
            valid_time=end_time,
            entity_type=entity_type,
        )
        filtered = []
        for r in results:
            vt = r.get("valid_time", "")
            if vt and vt >= start_time:
                filtered.append(r)
        return filtered
