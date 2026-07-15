import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..interfaces import IWorldStateManager
from ..storage import SQLiteRuntimeStorage
from ..models import WorldStateSnapshot

logger = logging.getLogger("world_state_manager")


class WorldStateManager(IWorldStateManager):
    def __init__(self, storage: SQLiteRuntimeStorage = None):
        self.storage = storage or SQLiteRuntimeStorage()

    def capture_snapshot(self, name: str, scenario_id: Optional[str] = None, is_baseline: bool = False) -> Dict[str, Any]:
        snapshot = WorldStateSnapshot(
            name=name,
            scenario_id=scenario_id,
            is_baseline=is_baseline,
        )
        try:
            # Use QueryService for read operations instead of direct GraphManager
            from odap.infra.query import get_query_service
            qs = get_query_service()
            entity_result = qs.execute(
                workspace_id=scenario_id or "default",
                query=".entity list()",
                limit=1,
            )
            # Build stats from QueryService result
            stats = {
                "total_entities": entity_result.total,
                "source": "query_service",
            }
            snapshot.object_states = stats
        except Exception as e:
            logger.warning(f"Failed to capture graph state: {e}")
            snapshot.object_states = {}
        snapshot.created_at = datetime.now().isoformat()
        return self.storage.save_snapshot(snapshot.model_dump())

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_snapshot(snapshot_id)

    def list_snapshots(self, scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.storage.list_snapshots(scenario_id=scenario_id)

    def compare_snapshots(self, snapshot_id_a: str, snapshot_id_b: str) -> Dict[str, Any]:
        snap_a = self.storage.get_snapshot(snapshot_id_a)
        snap_b = self.storage.get_snapshot(snapshot_id_b)
        if not snap_a:
            return {"status": "error", "message": f"Snapshot {snapshot_id_a} not found"}
        if not snap_b:
            return {"status": "error", "message": f"Snapshot {snapshot_id_b} not found"}
        states_a = snap_a.get("object_states", {})
        states_b = snap_b.get("object_states", {})
        all_keys = set(list(states_a.keys()) + list(states_b.keys()))
        differences = []
        for key in all_keys:
            val_a = states_a.get(key)
            val_b = states_b.get(key)
            if val_a != val_b:
                differences.append({
                    "key": key,
                    "snapshot_a_value": val_a,
                    "snapshot_b_value": val_b,
                })
        return {
            "status": "success",
            "snapshot_a": snapshot_id_a,
            "snapshot_b": snapshot_id_b,
            "total_keys": len(all_keys),
            "differences": differences,
            "difference_count": len(differences),
        }

    def delete_snapshot(self, snapshot_id: str) -> bool:
        return self.storage.delete_snapshot(snapshot_id)
