"""T083 [US8] Pattern discovery tool_call handler.

Analyzes ontology structure to discover:
- Common attributes across multiple object types → suggest base type abstraction
- Foreign key patterns (properties ending with `_id` matching a type name) → suggest relationship

Read-only tool: no HITL required, returns analysis results.
"""
import logging
from collections import Counter
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def pattern_discovery(
    ontology_id: str,
    object_types: List[Dict[str, Any]],
    link_types: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Discover patterns in ontology structure.

    Args:
        ontology_id: The ontology being analyzed.
        object_types: List of object type dicts with type_id, name, properties.
            Each property is a dict with at least "name".
        link_types: List of existing link type dicts with source_type, target_type.

    Returns:
        Dict with common_attributes, foreign_key_patterns, and summary.
    """
    link_types = link_types or []

    common_attributes = _detect_common_attributes(object_types)
    foreign_key_patterns = _detect_foreign_key_patterns(object_types, link_types)

    return {
        "status": "ok",
        "tool": "pattern_discovery",
        "hitl_required": False,
        "ontology_id": ontology_id,
        "common_attributes": common_attributes,
        "foreign_key_patterns": foreign_key_patterns,
        "summary": {
            "total_object_types": len(object_types),
            "common_attribute_count": len(common_attributes),
            "foreign_key_pattern_count": len(foreign_key_patterns),
        },
    }


def _detect_common_attributes(
    object_types: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find attributes that appear in 2+ object types."""
    attr_counter: Counter = Counter()
    attr_types: Dict[str, List[str]] = {}

    for ot in object_types:
        type_id = ot.get("type_id", ot.get("id", ""))
        for prop in ot.get("properties", []):
            prop_name = prop.get("name", "")
            if not prop_name:
                continue
            attr_counter[prop_name] += 1
            attr_types.setdefault(prop_name, []).append(type_id)

    common = []
    for attr_name, count in attr_counter.most_common():
        if count < 2:
            continue
        common.append({
            "name": attr_name,
            "count": count,
            "types": list(dict.fromkeys(attr_types[attr_name])),
            "suggestion": "suggest_base_type",
            "suggestion_detail": (
                f"属性 `{attr_name}` 出现在 {count} 个对象类型中，"
                f"建议抽象为基类属性"
            ),
        })
    return common


def _detect_foreign_key_patterns(
    object_types: List[Dict[str, Any]],
    link_types: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find properties ending with `_id` that match another object type name."""
    type_name_map: Dict[str, Dict[str, str]] = {}
    for ot in object_types:
        type_id = ot.get("type_id", ot.get("id", ""))
        type_name = ot.get("name", "").lower()
        if type_name:
            type_name_map[type_name] = {"type_id": type_id, "name": ot.get("name", "")}

    existing_links = set()
    for link in link_types:
        src = link.get("source_type", "")
        tgt = link.get("target_type", "")
        existing_links.add((src, tgt))
        existing_links.add((tgt, src))

    patterns = []
    for ot in object_types:
        source_type_id = ot.get("type_id", ot.get("id", ""))
        for prop in ot.get("properties", []):
            prop_name = prop.get("name", "")
            if not prop_name.endswith("_id") or prop_name == "id":
                continue
            base_name = prop_name[:-3].lower()
            if base_name in type_name_map:
                target_info = type_name_map[base_name]
                target_type_id = target_info["type_id"]
                has_link = (source_type_id, target_type_id) in existing_links
                patterns.append({
                    "property_name": prop_name,
                    "source_type": source_type_id,
                    "source_type_name": ot.get("name", ""),
                    "target_type": target_type_id,
                    "target_type_name": target_info["name"],
                    "existing_link": has_link,
                    "suggestion": "suggest_relationship" if not has_link else "existing_relationship",
                    "suggestion_detail": (
                        f"属性 `{prop_name}` 暗示 {ot.get('name', '')} → {target_info['name']} 关系"
                        if not has_link
                        else f"属性 `{prop_name}` 对应的关系已存在"
                    ),
                })
    return patterns
