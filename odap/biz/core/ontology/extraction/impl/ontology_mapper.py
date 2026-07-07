import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Mapping from node type keywords to ontology type categories
_NODE_TYPE_CATEGORY_MAP = {
    "action": "action_types",
    "event": "action_types",
    "operation": "action_types",
    "rule": "rule_types",
    "constraint": "rule_types",
    "policy": "rule_types",
    "condition": "rule_types",
    "process": "process_types",
    "workflow": "process_types",
    "flow": "process_types",
    "pipeline": "process_types",
    "function": "function_types",
    "logic": "function_types",
    "formula": "function_types",
    "calculation": "function_types",
    "indicator": "indicator_types",
    "metric": "indicator_types",
    "kpi": "indicator_types",
    "measure": "indicator_types",
}


def _classify_node_type(node_type: str) -> str:
    """Classify a node type string into an ontology type category.

    Returns the category key (e.g. 'action_types') or 'object_types' as default.
    """
    normalized = node_type.lower().strip()
    if normalized in _NODE_TYPE_CATEGORY_MAP:
        return _NODE_TYPE_CATEGORY_MAP[normalized]
    # Fallback: check if any keyword is a substring of the type
    for keyword, category in _NODE_TYPE_CATEGORY_MAP.items():
        if keyword in normalized:
            return category
    return "object_types"


def _infer_cardinality(edge: Dict[str, Any]) -> str:
    """Infer link cardinality from edge attributes instead of hardcoding."""
    cardinality = edge.get("cardinality", "")
    if cardinality:
        card_map = {
            "1:1": "ONE_TO_ONE",
            "1:N": "ONE_TO_MANY",
            "N:1": "MANY_TO_ONE",
            "N:N": "MANY_TO_MANY",
            "one_to_one": "ONE_TO_ONE",
            "one_to_many": "ONE_TO_MANY",
            "many_to_one": "MANY_TO_ONE",
            "many_to_many": "MANY_TO_MANY",
        }
        return card_map.get(cardinality, "ONE_TO_MANY")
    return "ONE_TO_MANY"


class OntologyMapper:
    def map_to_schema(self, ka_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        nodes = ka_result.get("nodes", [])
        edges = ka_result.get("edges", [])

        result: Dict[str, List[Dict[str, Any]]] = {
            "object_types": [],
            "link_types": [],
            "action_types": [],
            "rule_types": [],
            "process_types": [],
            "function_types": [],
            "indicator_types": [],
        }

        for node in nodes:
            node_type = node.get("type", "entity")
            category = _classify_node_type(node_type)

            # Build properties from attributes
            props = []
            for k, v in node.get("attributes", {}).items():
                prop_type = "STRING"
                if isinstance(v, bool):
                    prop_type = "BOOLEAN"
                elif isinstance(v, (int, float)):
                    prop_type = "NUMBER"
                props.append({"name": k, "property_type": prop_type})

            type_entry: Dict[str, Any] = {
                "name": node.get("name", node.get("id", "")),
                "display_name": node.get("name", node.get("id", "")),
                "description": node.get("description", ""),
                "properties": props,
            }

            # Add category-specific fields
            if category == "action_types":
                type_entry["parameters"] = node.get("parameters", [])
            elif category == "rule_types":
                type_entry["priority"] = node.get("priority", "medium")
                type_entry["expression"] = node.get("expression", "")
            elif category == "process_types":
                type_entry["related_objects"] = node.get("related_objects", [])
                type_entry["steps"] = node.get("steps", [])
            elif category == "function_types":
                type_entry["parameters"] = node.get("parameters", [])
                type_entry["return_type"] = node.get("return_type", "STRING")
            elif category == "indicator_types":
                type_entry["indicator_type"] = node.get("indicator_type", "metric")
                type_entry["unit"] = node.get("unit", "")

            result[category].append(type_entry)

        for edge in edges:
            result["link_types"].append({
                "name": edge.get("name", edge.get("type", "")),
                "source_type": edge.get("source", ""),
                "target_type": edge.get("target", ""),
                "cardinality": _infer_cardinality(edge),
                "link_type": edge.get("link_type", "ASSOCIATION"),
                "description": edge.get("description", ""),
            })

        return result

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
