import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

from ..interfaces import IStatePropagationEngine
from ..storage import SQLiteRuntimeStorage
from ..models import StatePropagationGraph, PropagationEdge, MutationRecord

logger = logging.getLogger("state_propagation_engine")


class StatePropagationEngine(IStatePropagationEngine):
    def __init__(self, storage: SQLiteRuntimeStorage = None):
        self.storage = storage or SQLiteRuntimeStorage()

    def build_propagation_graph(self, contracts: List[Dict[str, Any]]) -> Dict[str, Any]:
        edges = []
        object_types = set()
        for contract in contracts:
            action_name = contract.get("action_name", contract.get("action_type_id", ""))
            for ws in contract.get("write_set", []):
                src = ws.get("object_type", "")
                object_types.add(src)
                edges.append({
                    "source_type": src,
                    "source_property": ws.get("property_name"),
                    "action_name": action_name,
                    "target_type": src,
                    "target_property": ws.get("property_name"),
                    "propagation_type": "direct",
                    "probability": 1.0,
                    "latency_ms": 0,
                    "condition": "",
                })
            for se in contract.get("side_effect_set", []):
                src_type = ""
                for ws2 in contract.get("write_set", []):
                    src_type = ws2.get("object_type", "")
                    break
                tgt = se.get("object_type", "")
                object_types.add(tgt)
                if src_type:
                    object_types.add(src_type)
                edges.append({
                    "source_type": src_type,
                    "source_property": None,
                    "action_name": action_name,
                    "target_type": tgt,
                    "target_property": se.get("property_name"),
                    "propagation_type": "side_effect",
                    "probability": 0.8,
                    "latency_ms": 100,
                    "condition": "",
                })
        graph = StatePropagationGraph(
            edges=[PropagationEdge(**e) for e in edges],
            object_types=list(object_types),
        )
        now = datetime.now().isoformat()
        graph_d = graph.model_dump()
        graph_d["created_at"] = now
        graph_d["updated_at"] = now
        return self.storage.save_propagation_graph(graph_d)

    def get_propagation_graph(self, graph_id: str) -> Optional[Dict[str, Any]]:
        return self.storage.get_propagation_graph(graph_id)

    def compute_impact(self, graph_id: str, action_type_id: str, target_object_type: str) -> Dict[str, Any]:
        graph_data = self.storage.get_propagation_graph(graph_id)
        if not graph_data:
            return {"status": "error", "message": f"Propagation graph {graph_id} not found"}
        edges = graph_data.get("edges", [])
        visited = set()
        impact_chain = []
        queue = [target_object_type]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in edges:
                if edge.get("source_type") == current and edge.get("action_name", "").startswith(action_type_id.split("-")[0] if "-" in action_type_id else action_type_id):
                    target = edge.get("target_type", "")
                    impact_chain.append({
                        "from": current,
                        "to": target,
                        "via_action": edge.get("action_name", ""),
                        "propagation_type": edge.get("propagation_type", "direct"),
                        "probability": edge.get("probability", 1.0),
                        "property": edge.get("target_property"),
                    })
                    if target not in visited:
                        queue.append(target)
        return {
            "status": "success",
            "graph_id": graph_id,
            "action_type_id": action_type_id,
            "source_type": target_object_type,
            "impacted_types": list(visited),
            "impact_chain": impact_chain,
            "total_depth": len(impact_chain),
        }

    def record_mutation(self, mutation_data: Dict[str, Any]) -> Dict[str, Any]:
        mutation = MutationRecord(**mutation_data)
        mutation.timestamp = datetime.now().isoformat()
        return self.storage.save_mutation(mutation.model_dump())

    def query_mutations(self, target_object_id: Optional[str] = None, action_type_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        return self.storage.query_mutations(target_object_id=target_object_id, action_type_id=action_type_id, limit=limit)
