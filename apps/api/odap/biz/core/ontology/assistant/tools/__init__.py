"""T062 AG-UI tool_call handlers for ontology assistant.

Each handler returns a structured result that the AssistantService
can use to create AISuggestion records and HITL confirm prompts.
"""
import logging
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.assistant.rules.type_inference import TypeInferenceEngine
from odap.biz.core.ontology.assistant.rules.constraint_suggester import (
    ConstraintSuggester,
)
from odap.biz.core.ontology.assistant.services.suggestion_service import (
    SuggestionService,
)
from odap.biz.core.ontology.assistant.tools.completeness_check import (
    completeness_check,
)
from odap.biz.core.ontology.assistant.tools.pattern_discovery import (
    pattern_discovery,
)

logger = logging.getLogger(__name__)

_type_engine = TypeInferenceEngine()
_constraint_engine = ConstraintSuggester()


def add_property(
    suggestion_service: SuggestionService,
    ontology_id: str,
    object_type_id: str,
    name: str,
    data_type: str = None,
    required: bool = False,
    default_value: Any = None,
    constraints: Dict = None,
    session_id: str = None,
) -> Dict[str, Any]:
    """Write tool_call: add a property to an object type. Requires HITL."""
    validation = suggestion_service.validate_property_name(name)
    if not validation["valid"]:
        return {"status": "error", "message": f"invalid property name: {validation['reason']}"}
    if data_type is None:
        inferred = _type_engine.infer_type(name)
        data_type = inferred["inferred_type"]
        if constraints is None and inferred.get("suggested_constraints"):
            constraints = inferred["suggested_constraints"]
    content = {
        "name": name,
        "data_type": data_type,
        "required": required,
        "default_value": default_value,
        "constraints": constraints or {},
    }
    suggestion = suggestion_service.create_suggestion({
        "ontology_id": ontology_id,
        "target_type": "object_type",
        "target_id": object_type_id,
        "suggestion_category": "add_property",
        "content": content,
        "source": "llm",
        "confidence": 0.85,
        "session_id": session_id,
    })
    return {
        "status": "ok",
        "tool": "add_property",
        "suggestion_id": suggestion.get("suggestion_id"),
        "hitl_required": True,
        "hitl_prompt": f"确认添加属性 `{name}` ({data_type}{', 必填' if required else ''}) 到对象类型？",
        "content": content,
    }


def add_link_type(
    suggestion_service: SuggestionService,
    ontology_id: str,
    name: str,
    source_type: str,
    target_type: str,
    cardinality: str = "ONE_TO_MANY",
    link_type: str = "ASSOCIATION",
    description: str = None,
    session_id: str = None,
) -> Dict[str, Any]:
    """Write tool_call: create a relationship between two object types. Requires HITL."""
    validation = suggestion_service.validate_property_name(name)
    if not validation["valid"]:
        return {"status": "error", "message": f"invalid link name: {validation['reason']}"}
    content = {
        "name": name,
        "source_type": source_type,
        "target_type": target_type,
        "cardinality": cardinality,
        "link_type": link_type,
        "description": description,
    }
    suggestion = suggestion_service.create_suggestion({
        "ontology_id": ontology_id,
        "target_type": "link_type",
        "suggestion_category": "add_link_type",
        "content": content,
        "source": "llm",
        "confidence": 0.8,
        "session_id": session_id,
    })
    cardinality_label = {
        "ONE_TO_ONE": "1:1",
        "ONE_TO_MANY": "1:N",
        "MANY_TO_ONE": "N:1",
        "MANY_TO_MANY": "N:M",
    }.get(cardinality, cardinality)
    return {
        "status": "ok",
        "tool": "add_link_type",
        "suggestion_id": suggestion.get("suggestion_id"),
        "hitl_required": True,
        "hitl_prompt": f"确认创建关系 `{name}`: {source_type} → {target_type} ({cardinality_label})？",
        "content": content,
    }


def add_action_type(
    suggestion_service: SuggestionService,
    ontology_id: str,
    name: str,
    target_object_type: str,
    parameters_list: List[Dict] = None,
    description: str = None,
    session_id: str = None,
) -> Dict[str, Any]:
    """Write tool_call: add an action type to an object type. Requires HITL."""
    validation = suggestion_service.validate_property_name(name)
    if not validation["valid"]:
        return {"status": "error", "message": f"invalid action name: {validation['reason']}"}
    content = {
        "name": name,
        "target_object_type": target_object_type,
        "parameters": parameters_list or [],
        "description": description,
    }
    suggestion = suggestion_service.create_suggestion({
        "ontology_id": ontology_id,
        "target_type": "action_type",
        "target_id": target_object_type,
        "suggestion_category": "add_action_type",
        "content": content,
        "source": "llm",
        "confidence": 0.8,
        "session_id": session_id,
    })
    return {
        "status": "ok",
        "tool": "add_action_type",
        "suggestion_id": suggestion.get("suggestion_id"),
        "hitl_required": True,
        "hitl_prompt": f"确认添加动作 `{name}` 到 {target_object_type}？",
        "content": content,
    }


def suggest_properties(
    suggestion_service: SuggestionService,
    ontology_id: str,
    object_type_id: str,
    object_type_name: str,
    existing_properties: List[str] = None,
    session_id: str = None,
) -> Dict[str, Any]:
    """Read tool_call: suggest missing common properties. No HITL required."""
    common_by_type = {
        "user": ["email", "phone", "password", "is_active", "created_at", "updated_at"],
        "order": ["status", "total_amount", "created_at", "updated_at", "user_id"],
        "product": ["name", "price", "stock", "description", "category", "created_at"],
        "customer": ["name", "email", "phone", "address", "created_at"],
        "article": ["title", "content", "author", "published_at", "status"],
        "task": ["title", "description", "status", "priority", "assignee_id", "due_date"],
    }
    type_key = object_type_name.lower()
    candidates = common_by_type.get(type_key, ["name", "description", "created_at", "updated_at"])
    existing_set = set(existing_properties or [])
    missing = [p for p in candidates if p not in existing_set]
    suggestions = []
    for prop_name in missing:
        inferred = _type_engine.infer_type(prop_name)
        suggestions.append({
            "name": prop_name,
            "data_type": inferred["inferred_type"],
            "constraints": inferred.get("suggested_constraints") or {},
        })
    return {
        "status": "ok",
        "tool": "suggest_properties",
        "hitl_required": False,
        "suggestions": suggestions,
        "count": len(suggestions),
    }


def validate_constraint(
    property_name: str,
    data_type: str,
) -> Dict[str, Any]:
    """Read tool_call: suggest validation constraints. No HITL required."""
    result = _constraint_engine.suggest(property_name, data_type)
    return {
        "status": "ok",
        "tool": "validate_constraint",
        "hitl_required": False,
        "property_name": property_name,
        "data_type": data_type,
        "constraints": result["constraints"],
        "source": "rule_engine",
    }


TOOL_REGISTRY = {
    "add_property": add_property,
    "add_link_type": add_link_type,
    "add_action_type": add_action_type,
    "suggest_properties": suggest_properties,
    "validate_constraint": validate_constraint,
    "pattern_discovery": pattern_discovery,
    "completeness_check": completeness_check,
}
