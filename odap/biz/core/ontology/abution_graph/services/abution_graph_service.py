import uuid
from typing import Dict, Any, List, Optional
from ..models.types import (
    AbutionGraphSnapshot, TemporalNode, PatternNode, ForceNode, ActionNode,
    TemporalDimension, PatternType, ForceType, ActionDimension,
)
from ..storage import SQLiteAbutionStorage


class AbutionGraphService:
    _instance: Optional["AbutionGraphService"] = None

    @classmethod
    def get_instance(cls, storage=None) -> "AbutionGraphService":
        if cls._instance is None:
            cls._instance = cls(storage)
        return cls._instance

    def __init__(self, storage=None):
        self.storage = storage or SQLiteAbutionStorage()

    def create_snapshot(self, name: str, temporal_nodes: List[Dict] = None,
                        pattern_nodes: List[Dict] = None, force_nodes: List[Dict] = None,
                        action_nodes: List[Dict] = None,
                        cross_dimension_links: List[Dict[str, str]] = None) -> Dict[str, Any]:
        snapshot_id = str(uuid.uuid4())
        t_nodes = []
        for n in (temporal_nodes or []):
            t_nodes.append(TemporalNode(
                node_id=n.get("node_id", str(uuid.uuid4())),
                dimension=TemporalDimension(n["dimension"]),
                timestamp=n["timestamp"], description=n["description"],
                confidence=n.get("confidence", 1.0), metadata=n.get("metadata", {}),
            ))
        p_nodes = []
        for n in (pattern_nodes or []):
            p_nodes.append(PatternNode(
                pattern_id=n.get("pattern_id", str(uuid.uuid4())),
                pattern_type=PatternType(n["pattern_type"]),
                name=n["name"], description=n["description"],
                evidence=n.get("evidence", []), strength=n.get("strength", 0.0),
                metadata=n.get("metadata", {}),
            ))
        f_nodes = []
        for n in (force_nodes or []):
            f_nodes.append(ForceNode(
                force_id=n.get("force_id", str(uuid.uuid4())),
                force_type=ForceType(n["force_type"]),
                name=n["name"], magnitude=n.get("magnitude", 0.0),
                direction=n.get("direction", 0.0), description=n.get("description", ""),
                metadata=n.get("metadata", {}),
            ))
        a_nodes = []
        for n in (action_nodes or []):
            a_nodes.append(ActionNode(
                action_id=n.get("action_id", str(uuid.uuid4())),
                dimension=ActionDimension(n["dimension"]),
                name=n["name"], trigger_condition=n.get("trigger_condition", ""),
                effect=n.get("effect", ""), priority=n.get("priority", 0),
                metadata=n.get("metadata", {}),
            ))

        snapshot = AbutionGraphSnapshot(
            snapshot_id=snapshot_id, name=name,
            temporal_nodes=t_nodes, pattern_nodes=p_nodes,
            force_nodes=f_nodes, action_nodes=a_nodes,
            cross_dimension_links=cross_dimension_links or [],
        )
        self.storage.save(snapshot)
        return {
            "status": "success", "snapshot_id": snapshot_id, "name": name,
            "temporal_count": len(t_nodes), "pattern_count": len(p_nodes),
            "force_count": len(f_nodes), "action_count": len(a_nodes),
        }

    def get_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        snapshot = self.storage.get(snapshot_id)
        if not snapshot:
            return {"status": "error", "message": f"Snapshot {snapshot_id} not found"}
        return self._snapshot_to_dict(snapshot)

    def list_snapshots(self, limit: int = 100) -> Dict[str, Any]:
        snapshots = self.storage.list(limit=limit)
        return {
            "status": "success", "count": len(snapshots),
            "snapshots": [
                {"snapshot_id": s.snapshot_id, "name": s.name,
                 "temporal_count": len(s.temporal_nodes),
                 "pattern_count": len(s.pattern_nodes),
                 "force_count": len(s.force_nodes),
                 "action_count": len(s.action_nodes),
                 "created_at": s.created_at}
                for s in snapshots
            ],
        }

    def delete_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        result = self.storage.delete(snapshot_id)
        if not result:
            return {"status": "error", "message": f"Snapshot {snapshot_id} not found"}
        return {"status": "success", "snapshot_id": snapshot_id}

    def add_dimension_node(self, snapshot_id: str, dimension: str,
                            node_data: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = self.storage.get(snapshot_id)
        if not snapshot:
            return {"status": "error", "message": f"Snapshot {snapshot_id} not found"}
        if dimension == "temporal":
            node = TemporalNode(
                node_id=node_data.get("node_id", str(uuid.uuid4())),
                dimension=TemporalDimension(node_data["dimension"]),
                timestamp=node_data["timestamp"], description=node_data["description"],
                confidence=node_data.get("confidence", 1.0),
                metadata=node_data.get("metadata", {}),
            )
            snapshot.temporal_nodes.append(node)
        elif dimension == "pattern":
            node = PatternNode(
                pattern_id=node_data.get("pattern_id", str(uuid.uuid4())),
                pattern_type=PatternType(node_data["pattern_type"]),
                name=node_data["name"], description=node_data["description"],
                evidence=node_data.get("evidence", []),
                strength=node_data.get("strength", 0.0),
                metadata=node_data.get("metadata", {}),
            )
            snapshot.pattern_nodes.append(node)
        elif dimension == "force":
            node = ForceNode(
                force_id=node_data.get("force_id", str(uuid.uuid4())),
                force_type=ForceType(node_data["force_type"]),
                name=node_data["name"], magnitude=node_data.get("magnitude", 0.0),
                direction=node_data.get("direction", 0.0),
                description=node_data.get("description", ""),
                metadata=node_data.get("metadata", {}),
            )
            snapshot.force_nodes.append(node)
        elif dimension == "action":
            node = ActionNode(
                action_id=node_data.get("action_id", str(uuid.uuid4())),
                dimension=ActionDimension(node_data["dimension"]),
                name=node_data["name"],
                trigger_condition=node_data.get("trigger_condition", ""),
                effect=node_data.get("effect", ""),
                priority=node_data.get("priority", 0),
                metadata=node_data.get("metadata", {}),
            )
            snapshot.action_nodes.append(node)
        else:
            return {"status": "error", "message": f"Unknown dimension: {dimension}"}
        self.storage.save(snapshot)
        return {"status": "success", "snapshot_id": snapshot_id, "dimension": dimension}

    def link_dimensions(self, snapshot_id: str, source_dim: str, source_id: str,
                         target_dim: str, target_id: str,
                         link_type: str = "correlation") -> Dict[str, Any]:
        snapshot = self.storage.get(snapshot_id)
        if not snapshot:
            return {"status": "error", "message": f"Snapshot {snapshot_id} not found"}
        link = {
            "source_dim": source_dim, "source_id": source_id,
            "target_dim": target_dim, "target_id": target_id,
            "link_type": link_type,
        }
        snapshot.cross_dimension_links.append(link)
        self.storage.save(snapshot)
        return {"status": "success", "snapshot_id": snapshot_id, "link": link}

    def analyze_cross_dimension_patterns(self, snapshot_id: str) -> Dict[str, Any]:
        snapshot = self.storage.get(snapshot_id)
        if not snapshot:
            return {"status": "error", "message": f"Snapshot {snapshot_id} not found"}
        links = snapshot.cross_dimension_links
        dim_pairs: Dict[str, int] = {}
        link_types: Dict[str, int] = {}
        for link in links:
            pair_key = f"{link.get('source_dim', '')}->{link.get('target_dim', '')}"
            dim_pairs[pair_key] = dim_pairs.get(pair_key, 0) + 1
            lt = link.get("link_type", "unknown")
            link_types[lt] = link_types.get(lt, 0) + 1

        temporal_by_dim: Dict[str, int] = {}
        for n in snapshot.temporal_nodes:
            key = n.dimension.value
            temporal_by_dim[key] = temporal_by_dim.get(key, 0) + 1

        pattern_by_type: Dict[str, int] = {}
        for n in snapshot.pattern_nodes:
            key = n.pattern_type.value
            pattern_by_type[key] = pattern_by_type.get(key, 0) + 1

        force_by_type: Dict[str, int] = {}
        for n in snapshot.force_nodes:
            key = n.force_type.value
            force_by_type[key] = force_by_type.get(key, 0) + 1

        action_by_dim: Dict[str, int] = {}
        for n in snapshot.action_nodes:
            key = n.dimension.value
            action_by_dim[key] = action_by_dim.get(key, 0) + 1

        dominant_force = None
        if snapshot.force_nodes:
            dominant_force = max(snapshot.force_nodes, key=lambda f: f.magnitude)
            dominant_force = {"force_id": dominant_force.force_id, "name": dominant_force.name,
                              "magnitude": dominant_force.magnitude}

        high_priority_actions = [
            {"action_id": a.action_id, "name": a.name, "priority": a.priority}
            for a in sorted(snapshot.action_nodes, key=lambda x: x.priority, reverse=True)[:5]
        ]

        return {
            "status": "success", "snapshot_id": snapshot_id,
            "total_links": len(links), "dimension_pairs": dim_pairs,
            "link_types": link_types,
            "temporal_distribution": temporal_by_dim,
            "pattern_distribution": pattern_by_type,
            "force_distribution": force_by_type,
            "action_distribution": action_by_dim,
            "dominant_force": dominant_force,
            "high_priority_actions": high_priority_actions,
        }

    def _snapshot_to_dict(self, snapshot: AbutionGraphSnapshot) -> Dict[str, Any]:
        return {
            "status": "success",
            "snapshot_id": snapshot.snapshot_id, "name": snapshot.name,
            "temporal_nodes": [
                {"node_id": n.node_id, "dimension": n.dimension.value,
                 "timestamp": n.timestamp, "description": n.description,
                 "confidence": n.confidence, "metadata": n.metadata}
                for n in snapshot.temporal_nodes
            ],
            "pattern_nodes": [
                {"pattern_id": n.pattern_id, "pattern_type": n.pattern_type.value,
                 "name": n.name, "description": n.description,
                 "evidence": n.evidence, "strength": n.strength, "metadata": n.metadata}
                for n in snapshot.pattern_nodes
            ],
            "force_nodes": [
                {"force_id": n.force_id, "force_type": n.force_type.value,
                 "name": n.name, "magnitude": n.magnitude,
                 "direction": n.direction, "description": n.description, "metadata": n.metadata}
                for n in snapshot.force_nodes
            ],
            "action_nodes": [
                {"action_id": n.action_id, "dimension": n.dimension.value,
                 "name": n.name, "trigger_condition": n.trigger_condition,
                 "effect": n.effect, "priority": n.priority, "metadata": n.metadata}
                for n in snapshot.action_nodes
            ],
            "cross_dimension_links": snapshot.cross_dimension_links,
            "created_at": snapshot.created_at,
        }


get_abution_graph_service = AbutionGraphService.get_instance
