import os
import json
import math
import sqlite3
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from .api.schemas import BlueprintNodeType, BlueprintEdgeType


class BlueprintDesignerService:
    _instance = None

    @classmethod
    def get_instance(cls, storage=None):
        if cls._instance is None:
            cls._instance = cls(storage)
        return cls._instance

    def __init__(self, storage=None, version_storage=None):
        from odap.biz.core.ontology.application.harness.blueprint.storage import BlueprintStorage, BlueprintVersionStorage
        self.storage = storage or BlueprintStorage()
        self.version_storage = version_storage or BlueprintVersionStorage()

    def create_blueprint(self, name: str, description: str = "", scenario_id: str = None,
                         nodes: list = None, edges: list = None, layout: dict = None,
                         metadata: dict = None) -> Dict[str, Any]:
        blueprint_id = f"bp-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        bp_data = {
            "blueprint_id": blueprint_id, "name": name, "description": description,
            "scenario_id": scenario_id, "version": 1,
            "nodes": nodes or [], "edges": edges or [], "layout": layout or {},
            "is_published": False, "parent_version_id": None,
            "created_at": now, "updated_at": now, "metadata": metadata or {},
        }
        self.storage.save(bp_data)
        return {"status": "success", "blueprint_id": blueprint_id, "name": name, "version": 1}

    def get_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        return {"status": "success", **data}

    def list_blueprints(self, scenario_id: str = None, is_published: bool = None,
                        limit: int = 100) -> Dict[str, Any]:
        blueprints = self.storage.list_blueprints(scenario_id, is_published, limit)
        return {"status": "success", "count": len(blueprints),
                "blueprints": [{"blueprint_id": b["blueprint_id"], "name": b["name"],
                                "version": b.get("version", 1),
                                "is_published": bool(b.get("is_published", False)),
                                "updated_at": b.get("updated_at", "")}
                               for b in blueprints]}

    def update_blueprint(self, blueprint_id: str, **updates) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        snapshot = {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "nodes": data.get("nodes", []),
            "edges": data.get("edges", []),
        }
        self.version_storage.save_snapshot(blueprint_id, snapshot, description="before update")
        for key, value in updates.items():
            if key in data:
                data[key] = value
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "blueprint_id": blueprint_id}

    def delete_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        result = self.storage.delete(blueprint_id)
        if not result:
            return {"status": "error", "message": "Blueprint not found"}
        return {"status": "success", "blueprint_id": blueprint_id}

    def add_node(self, blueprint_id: str, node_type: str, name: str,
                 position: dict = None, config: dict = None) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        nodes = data.get("nodes", [])
        node_id = f"node-{uuid.uuid4().hex[:8]}"
        node = {
            "node_id": node_id, "node_type": node_type, "name": name,
            "position": position or {"x": 0, "y": 0}, "config": config or {},
        }
        nodes.append(node)
        data["nodes"] = nodes
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "node_id": node_id, "blueprint_id": blueprint_id}

    def update_node(self, blueprint_id: str, node_id: str, **updates) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        nodes = data.get("nodes", [])
        node = next((n for n in nodes if n.get("node_id") == node_id), None)
        if not node:
            return {"status": "error", "message": "Node not found"}
        node.update(updates)
        data["nodes"] = nodes
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "node_id": node_id}

    def remove_node(self, blueprint_id: str, node_id: str) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        nodes = [n for n in nodes if n.get("node_id") != node_id]
        edges = [e for e in edges
                 if e.get("source") != node_id and e.get("target") != node_id]
        data["nodes"] = nodes
        data["edges"] = edges
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "node_id": node_id}

    def add_edge(self, blueprint_id: str, source: str, target: str,
                 edge_type: str = "data_flow", label: str = "") -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        nodes = data.get("nodes", [])
        node_ids = [n.get("node_id") for n in nodes]
        if source not in node_ids or target not in node_ids:
            return {"status": "error", "message": "Source or target node not found"}
        edges = data.get("edges", [])
        edge_id = f"edge-{uuid.uuid4().hex[:8]}"
        edge = {"edge_id": edge_id, "source": source, "target": target,
                "edge_type": edge_type, "label": label}
        edges.append(edge)
        data["edges"] = edges
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "edge_id": edge_id, "blueprint_id": blueprint_id}

    def remove_edge(self, blueprint_id: str, edge_id: str) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        edges = data.get("edges", [])
        edges = [e for e in edges if e.get("edge_id") != edge_id]
        data["edges"] = edges
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "edge_id": edge_id}

    def validate_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        errors = []
        warnings = []
        if not nodes:
            errors.append("Blueprint has no nodes")
        node_ids = {n.get("node_id") for n in nodes}
        for edge in edges:
            if edge.get("source") not in node_ids:
                errors.append(f"Edge references missing source: {edge.get('source')}")
            if edge.get("target") not in node_ids:
                errors.append(f"Edge references missing target: {edge.get('target')}")
        source_nodes = {e.get("source") for e in edges}
        target_nodes = {e.get("target") for e in edges}
        disconnected = node_ids - source_nodes - target_nodes
        if len(disconnected) > 0 and len(nodes) > 1:
            warnings.append(f"Disconnected nodes: {disconnected}")
        is_valid = len(errors) == 0
        return {"status": "success", "blueprint_id": blueprint_id,
                "is_valid": is_valid, "errors": errors, "warnings": warnings}

    def publish_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        validation = self.validate_blueprint(blueprint_id)
        if not validation.get("is_valid"):
            return {"status": "error", "message": "Cannot publish invalid blueprint",
                    "errors": validation.get("errors", [])}
        data["is_published"] = 1
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "blueprint_id": blueprint_id, "is_published": True}

    def fork_blueprint(self, blueprint_id: str, new_name: str = None) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        new_id = f"bp-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        new_data = {
            "blueprint_id": new_id,
            "name": new_name or f"{data['name']} (copy)",
            "description": data.get("description", ""),
            "scenario_id": data.get("scenario_id"),
            "version": 1,
            "nodes": data.get("nodes", []),
            "edges": data.get("edges", []),
            "layout": data.get("layout", {}),
            "is_published": False, "parent_version_id": blueprint_id,
            "created_at": now, "updated_at": now,
            "metadata": data.get("metadata", {}),
        }
        self.storage.save(new_data)
        return {"status": "success", "blueprint_id": new_id,
                "parent_version_id": blueprint_id}

    def export_blueprint(self, blueprint_id: str, format: str = "json") -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        if format == "json":
            return {"status": "success", "format": "json", "blueprint": data}
        elif format == "code":
            code = self._generate_code(data)
            return {"status": "success", "format": "code", "code": code}
        return {"status": "error", "message": f"Unsupported format: {format}"}

    def _generate_code(self, blueprint: Dict[str, Any]) -> str:
        lines = []
        lines.append(f'"""Blueprint: {blueprint.get("name", "")}"""')
        lines.append("from ..services.pipeline_service import PipelineService")
        lines.append("")
        lines.append("pipeline = PipelineService.get_instance()")
        nodes = blueprint.get("nodes", [])
        edges = blueprint.get("edges", [])
        for node in nodes:
            node_type = node.get("node_type", "")
            name = node.get("name", "")
            config = node.get("config", {})
            if node_type == "data_source":
                lines.append(f"# Data source: {name}")
                lines.append(f"source_{node['node_id']} = {{'type': '{config.get('source_type', 'api')}'}}")
            elif node_type == "transform":
                lines.append(f"# Transform: {name}")
                lines.append(f"transform_{node['node_id']} = pipeline.create_transform({config})")
            elif node_type == "ontology":
                lines.append(f"# Ontology: {name}")
                lines.append(f"ontology_{node['node_id']} = pipeline.build_ontology({config})")
        lines.append("")
        lines.append("# Pipeline connections")
        for edge in edges:
            lines.append(f"# {edge.get('source')} -> {edge.get('target')}: {edge.get('edge_type', '')}")
        return "\n".join(lines)

    def batch_add_nodes(self, blueprint_id: str, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        existing_nodes = data.get("nodes", [])
        node_ids = []
        for node_spec in nodes:
            node_id = f"node-{uuid.uuid4().hex[:8]}"
            node = {
                "node_id": node_id,
                "node_type": node_spec.get("node_type", ""),
                "name": node_spec.get("name", ""),
                "position": node_spec.get("position", {"x": 0, "y": 0}),
                "config": node_spec.get("config", {}),
            }
            existing_nodes.append(node)
            node_ids.append(node_id)
        data["nodes"] = existing_nodes
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "added_count": len(node_ids), "node_ids": node_ids}

    def batch_add_edges(self, blueprint_id: str, edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        existing_nodes = data.get("nodes", [])
        node_ids = {n.get("node_id") for n in existing_nodes}
        existing_edges = data.get("edges", [])
        edge_ids = []
        for edge_spec in edges:
            source = edge_spec.get("source", "")
            target = edge_spec.get("target", "")
            if source not in node_ids or target not in node_ids:
                continue
            edge_id = f"edge-{uuid.uuid4().hex[:8]}"
            edge = {
                "edge_id": edge_id,
                "source": source,
                "target": target,
                "edge_type": edge_spec.get("edge_type", "data_flow"),
                "label": edge_spec.get("label", ""),
            }
            existing_edges.append(edge)
            edge_ids.append(edge_id)
        data["edges"] = existing_edges
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "added_count": len(edge_ids), "edge_ids": edge_ids}

    def batch_update_positions(self, blueprint_id: str,
                               positions: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        nodes = data.get("nodes", [])
        node_map = {n.get("node_id"): n for n in nodes}
        updated_count = 0
        skipped_count = 0
        for node_id, pos in positions.items():
            if node_id in node_map:
                node_map[node_id]["position"] = pos
                updated_count += 1
            else:
                skipped_count += 1
        data["nodes"] = list(node_map.values())
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "updated_count": updated_count,
                "skipped_count": skipped_count}

    def auto_layout(self, blueprint_id: str, direction: str = "TB",
                    spacing_x: int = 250, spacing_y: int = 100) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        nodes = data.get("nodes", [])
        if not nodes:
            return {"status": "success", "layout_count": 0}
        cols = math.ceil(math.sqrt(len(nodes)))
        layout_count = 0
        for idx, node in enumerate(nodes):
            if node.get("position") and node["position"].get("x", 0) != 0 and node["position"].get("y", 0) != 0:
                continue
            row = idx // cols
            col = idx % cols
            node["position"] = {"x": col * spacing_x, "y": row * spacing_y}
            layout_count += 1
        data["nodes"] = nodes
        data["updated_at"] = datetime.now().isoformat()
        self.storage.save(dict(data))
        return {"status": "success", "layout_count": layout_count}

    def import_blueprint(self, name: str, data: Dict[str, Any],
                         scenario_id: str = None) -> Dict[str, Any]:
        if not name:
            return {"status": "error", "message": "Name is required"}
        if not data:
            return {"status": "error", "message": "Import data is required"}
        blueprint_id = f"bp-{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()
        raw_nodes = data.get("nodes", [])
        raw_edges = data.get("edges", [])
        node_id_map = {}
        nodes = []
        for idx, raw_node in enumerate(raw_nodes):
            node_id = f"node-{uuid.uuid4().hex[:8]}"
            node_id_map[idx] = node_id
            nodes.append({
                "node_id": node_id,
                "node_type": raw_node.get("node_type", ""),
                "name": raw_node.get("name", ""),
                "position": raw_node.get("position", {"x": 0, "y": 0}),
                "config": raw_node.get("config", {}),
            })
        edges = []
        for raw_edge in raw_edges:
            source_key = raw_edge.get("source")
            target_key = raw_edge.get("target")
            source_id = node_id_map.get(source_key) if isinstance(source_key, int) else source_key
            target_id = node_id_map.get(target_key) if isinstance(target_key, int) else target_key
            if source_id and target_id:
                edge_id = f"edge-{uuid.uuid4().hex[:8]}"
                edges.append({
                    "edge_id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "edge_type": raw_edge.get("edge_type", "data_flow"),
                    "label": raw_edge.get("label", ""),
                })
        bp_data = {
            "blueprint_id": blueprint_id, "name": name,
            "description": data.get("description", ""),
            "scenario_id": scenario_id, "version": 1,
            "nodes": nodes, "edges": edges,
            "layout": data.get("layout", {}),
            "is_published": False, "parent_version_id": None,
            "created_at": now, "updated_at": now,
            "metadata": data.get("metadata", {}),
        }
        self.storage.save(bp_data)
        return {"status": "success", "blueprint_id": blueprint_id, "name": name, "version": 1}

    def export_to_pipeline_config(self, blueprint_id: str) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        stages = []
        for node in nodes:
            stages.append({
                "id": node.get("node_id", ""),
                "type": node.get("node_type", ""),
                "name": node.get("name", ""),
                "config": node.get("config", {}),
            })
        connections = []
        for edge in edges:
            connections.append({
                "source": edge.get("source", ""),
                "target": edge.get("target", ""),
                "type": edge.get("edge_type", "data_flow"),
                "label": edge.get("label", ""),
            })
        pipeline = {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "stages": stages,
            "connections": connections,
            "metadata": data.get("metadata", {}),
        }
        return {"status": "success", "pipeline": pipeline}

    def get_version_history(self, blueprint_id: str) -> Dict[str, Any]:
        data = self.storage.get(blueprint_id)
        if not data:
            return {"status": "error", "message": "Blueprint not found"}
        snapshots = self.version_storage.list_snapshots(blueprint_id)
        history = []
        for snap in snapshots:
            history.append({
                "snapshot_id": snap["snapshot_id"],
                "created_at": snap["created_at"],
                "description": snap["description"],
                "name": snap["snapshot"].get("name", ""),
                "node_count": len(snap["snapshot"].get("nodes", [])),
                "edge_count": len(snap["snapshot"].get("edges", [])),
            })
        return {"status": "success", "blueprint_id": blueprint_id, "history": history}

    def compare_versions(self, blueprint_id: str,
                         version_a: Dict[str, Any],
                         version_b: Dict[str, Any]) -> Dict[str, Any]:
        diff = {
            "name_changed": version_a.get("name") != version_b.get("name"),
            "description_changed": version_a.get("description") != version_b.get("description"),
            "nodes_added": [],
            "nodes_removed": [],
            "edges_added": [],
            "edges_removed": [],
        }
        nodes_a = {n.get("node_id"): n for n in version_a.get("nodes", [])}
        nodes_b = {n.get("node_id"): n for n in version_b.get("nodes", [])}
        for nid in set(nodes_b.keys()) - set(nodes_a.keys()):
            diff["nodes_added"].append(nid)
        for nid in set(nodes_a.keys()) - set(nodes_b.keys()):
            diff["nodes_removed"].append(nid)
        edges_a = {e.get("edge_id"): e for e in version_a.get("edges", [])}
        edges_b = {e.get("edge_id"): e for e in version_b.get("edges", [])}
        for eid in set(edges_b.keys()) - set(edges_a.keys()):
            diff["edges_added"].append(eid)
        for eid in set(edges_a.keys()) - set(edges_b.keys()):
            diff["edges_removed"].append(eid)
        return {"status": "success", "blueprint_id": blueprint_id, "diff": diff}


get_blueprint_designer = BlueprintDesignerService.get_instance
