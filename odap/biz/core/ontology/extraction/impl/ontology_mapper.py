import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OntologyMapper:
    def map_to_schema(self, ka_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        nodes = ka_result.get("nodes", [])
        edges = ka_result.get("edges", [])
        object_types = []
        link_types = []
        for node in nodes:
            node_type = node.get("type", "entity")
            if node_type in ("entity", "object"):
                props = []
                for k, v in node.get("attributes", {}).items():
                    prop_type = "STRING"
                    if isinstance(v, bool):
                        prop_type = "BOOLEAN"
                    elif isinstance(v, (int, float)):
                        prop_type = "NUMBER"
                    props.append({"name": k, "property_type": prop_type})
                object_types.append({
                    "name": node.get("name", node.get("id", "")),
                    "display_name": node.get("name", node.get("id", "")),
                    "description": node.get("description", ""),
                    "properties": props,
                })
        for edge in edges:
            link_types.append({
                "name": edge.get("name", edge.get("type", "")),
                "source_type": edge.get("source", ""),
                "target_type": edge.get("target", ""),
                "cardinality": "ONE_TO_MANY",
                "link_type": edge.get("link_type", "ASSOCIATION"),
                "description": edge.get("description", ""),
            })
        return {
            "object_types": object_types,
            "link_types": link_types,
            "action_types": [],
            "rule_types": [],
            "process_types": [],
            "function_types": [],
            "indicator_types": [],
        }

    def map_to_instances(self, ka_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        nodes = ka_result.get("nodes", [])
        edges = ka_result.get("edges", [])
        entities = []
        relations = []
        for node in nodes:
            entities.append({
                "name": node.get("name", node.get("id", "")),
                "type": node.get("type", "entity"),
                "attributes": node.get("attributes", {}),
                "id": node.get("id", ""),
            })
        for edge in edges:
            relations.append({
                "name": edge.get("name", edge.get("type", "")),
                "source_id": edge.get("source", ""),
                "target_id": edge.get("target", ""),
                "attributes": edge.get("attributes", {}),
                "id": edge.get("id", ""),
            })
        return {"entities": entities, "relations": relations}
