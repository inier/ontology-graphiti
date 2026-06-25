"""T084 [US8] Completeness check tool_call handler.

Analyzes ontology structure for completeness issues:
- Orphan types: object types with no relationships
- Missing audit fields: types missing created_at/updated_at
- Missing status: types that should have a status field (order, task, article, etc.)
- Missing description: types with empty or missing description

Read-only tool: no HITL required, returns analysis results.
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

AUDIT_FIELDS = {"created_at", "updated_at"}

# Object type names that typically need a status field
STATUS_REQUIRED_TYPES = {"order", "task", "article", "ticket", "request", "payment", "subscription"}


def completeness_check(
    ontology_id: str,
    object_types: List[Dict[str, Any]],
    link_types: List[Dict[str, Any]] = None,
    action_types: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Check ontology completeness.

    Args:
        ontology_id: The ontology being analyzed.
        object_types: List of object type dicts with type_id, name, display_name,
            description, properties.
        link_types: List of link type dicts with source_type, target_type.
        action_types: List of action type dicts (unused for now, reserved for future).

    Returns:
        Dict with orphan_types, missing_audit_fields, missing_status,
        missing_description, and summary.
    """
    link_types = link_types or []
    action_types = action_types or []

    orphan_types = _detect_orphan_types(object_types, link_types)
    missing_audit = _detect_missing_audit_fields(object_types)
    missing_status = _detect_missing_status(object_types)
    missing_desc = _detect_missing_description(object_types)

    return {
        "status": "ok",
        "tool": "completeness_check",
        "hitl_required": False,
        "ontology_id": ontology_id,
        "orphan_types": orphan_types,
        "missing_audit_fields": missing_audit,
        "missing_status": missing_status,
        "missing_description": missing_desc,
        "summary": {
            "total_object_types": len(object_types),
            "orphan_count": len(orphan_types),
            "missing_audit_count": len(missing_audit),
            "missing_status_count": len(missing_status),
            "missing_description_count": len(missing_desc),
        },
    }


def _detect_orphan_types(
    object_types: List[Dict[str, Any]],
    link_types: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find object types that have no relationships."""
    connected_ids = set()
    for link in link_types:
        src = link.get("source_type", "")
        tgt = link.get("target_type", "")
        if src:
            connected_ids.add(src)
        if tgt:
            connected_ids.add(tgt)

    orphans = []
    for ot in object_types:
        type_id = ot.get("type_id", ot.get("id", ""))
        if type_id not in connected_ids:
            orphans.append({
                "type_id": type_id,
                "type_name": ot.get("name", ""),
                "display_name": ot.get("display_name", ""),
                "suggestion": "add_relationship",
                "suggestion_detail": (
                    f"对象类型 `{ot.get('name', '')}` 没有任何关系，"
                    f"考虑添加与其他类型的关系"
                ),
            })
    return orphans


def _detect_missing_audit_fields(
    object_types: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find object types missing created_at or updated_at."""
    results = []
    for ot in object_types:
        type_id = ot.get("type_id", ot.get("id", ""))
        prop_names = {p.get("name", "") for p in ot.get("properties", [])}
        missing = AUDIT_FIELDS - prop_names
        if missing:
            results.append({
                "type_id": type_id,
                "type_name": ot.get("name", ""),
                "missing": sorted(missing),
                "suggestion": "add_audit_fields",
                "suggestion_detail": (
                    f"对象类型 `{ot.get('name', '')}` 缺少审计字段: {', '.join(sorted(missing))}"
                ),
            })
    return results


def _detect_missing_status(
    object_types: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find object types that should have a status field but don't."""
    results = []
    for ot in object_types:
        type_name = ot.get("name", "").lower()
        if type_name not in STATUS_REQUIRED_TYPES:
            continue
        type_id = ot.get("type_id", ot.get("id", ""))
        prop_names = {p.get("name", "") for p in ot.get("properties", [])}
        if "status" not in prop_names:
            results.append({
                "type_id": type_id,
                "type_name": ot.get("name", ""),
                "suggested_field": "status",
                "suggested_type": "STRING",
                "suggestion": "add_status_field",
                "suggestion_detail": (
                    f"对象类型 `{ot.get('name', '')}` 通常需要 status 字段来跟踪状态"
                ),
            })
    return results


def _detect_missing_description(
    object_types: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Find object types with empty or missing description."""
    results = []
    for ot in object_types:
        desc = ot.get("description", "")
        if not desc or not desc.strip():
            type_id = ot.get("type_id", ot.get("id", ""))
            results.append({
                "type_id": type_id,
                "type_name": ot.get("name", ""),
                "suggestion": "add_description",
                "suggestion_detail": (
                    f"对象类型 `{ot.get('name', '')}` 缺少描述，建议补充"
                ),
            })
    return results
