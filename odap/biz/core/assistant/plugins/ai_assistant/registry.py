"""Bridge layer: adapt OpenHarness BaseTool plugins to the chat service interface.

Provides backward-compatible functions (TOOL_REGISTRY, get_tools_for_llm,
execute_tool) backed by the new BaseTool subclasses in the ai_assistant plugin.

This is a transitional adapter — once the full OHMO Gateway migration is complete,
chat_service.py will be replaced by the OpenHarness QueryEngine and this bridge
will be removed.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolRegistry

from odap.biz.core.assistant.plugins.ai_assistant.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

# ── Build ToolRegistry ────────────────────────────────────────────────────────

_registry: ToolRegistry = ToolRegistry()
for _tool in ALL_TOOLS:
    _registry.register(_tool)


# ── Backward-compatible TOOL_REGISTRY dict ────────────────────────────────────
# Old format: { name: {"name", "description", "handler", "parameters", "category"} }
# New format: we synthesize the dict from BaseTool metadata.

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}
for _t in ALL_TOOLS:
    schema = _t.input_model.model_json_schema()
    properties = schema.get("properties", {})
    # Extract parameter types in the old flat format: {param_name: type_str}
    param_types: Dict[str, str] = {}
    for pname, pinfo in properties.items():
        json_type = pinfo.get("type", "string")
        if isinstance(json_type, list):
            json_type = json_type[0] if json_type else "string"
        param_types[pname] = json_type

    TOOL_REGISTRY[_t.name] = {
        "name": _t.name,
        "description": _t.description,
        "handler": None,  # Not used — execution goes through BaseTool.execute()
        "parameters": param_types,
        "category": "query" if _t.is_read_only(None) else "write",
    }


# ── get_tools_for_llm: OpenAI function-calling format ─────────────────────────

def get_tools_for_llm() -> List[Dict[str, Any]]:
    """Return tool definitions in OpenAI function-calling format for the LLM."""
    tools = []
    for t in ALL_TOOLS:
        schema = t.input_model.model_json_schema()
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        tools.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        k: {
                            "type": v.get("type", "string"),
                            "description": v.get("description", f"{k} parameter"),
                            **({"default": v["default"]} if "default" in v else {}),
                        }
                        for k, v in properties.items()
                    },
                    "required": required,
                },
            },
        })
    return tools


# ── Async tool execution ──────────────────────────────────────────────────────

async def execute_tool_async(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a registered BaseTool by name (async).

    Returns a dict with 'status', 'message', and tool-specific fields.
    This matches the return format expected by chat_service.py.
    """
    tool = _registry.get(name)
    if tool is None:
        return {"status": "error", "message": f"unknown tool: {name}"}

    try:
        # Validate arguments through Pydantic input model
        input_model = tool.input_model
        try:
            validated = input_model(**arguments)
        except Exception as ve:
            logger.warning("Tool %s argument validation failed: %s", name, ve)
            return {"status": "error", "message": f"parameter validation failed: {ve}"}

        # Create execution context
        context = ToolExecutionContext(cwd=Path("."))

        # Execute
        result = await tool.execute(validated, context)

        # Convert ToolResult to dict format
        if result.is_error:
            return {"status": "error", "message": result.output}

        # Try to parse output as JSON for structured data
        try:
            data = json.loads(result.output)
            if isinstance(data, dict):
                return data
            return {"status": "success", "data": data}
        except (json.JSONDecodeError, TypeError):
            return {"status": "success", "message": result.output}

    except Exception as e:
        logger.exception("Tool %s execution failed", name)
        return {"status": "error", "message": f"tool execution failed: {e}"}


# ── Sync wrapper (for non-async callers) ──────────────────────────────────────

def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a registered BaseTool by name (sync wrapper).

    WARNING: This creates a new event loop via asyncio.run().
    Do NOT call this from within an async context — use execute_tool_async() instead.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # We're inside a running event loop — can't use asyncio.run()
        # Create a task and wait for it
        logger.warning(
            "execute_tool() called from within a running event loop. "
            "Use 'await execute_tool_async()' instead. Falling back to "
            "loop.run_until_complete with a new loop in a thread."
        )
        import threading
        result_box: list = []
        def _run():
            new_loop = asyncio.new_event_loop()
            try:
                result_box.append(new_loop.run_until_complete(execute_tool_async(name, arguments)))
            finally:
                new_loop.close()
        t = threading.Thread(target=_run)
        t.start()
        t.join()
        return result_box[0] if result_box else {"status": "error", "message": "thread failed"}

    return asyncio.run(execute_tool_async(name, arguments))


# ── Ontology context helper (replaces _get_ontology_context) ──────────────────

def get_ontology_context(ontology_id: str) -> Dict[str, Any]:
    """Get current ontology design state for LLM context injection.

    Replaces the old _get_ontology_context from tools.py.
    Returns {"status": "success", "context": {...}} or {"status": "error", "message": ...}.
    """
    try:
        from odap.biz.core.ontology.ontology_api.services.ontology_service import OntologyService

        svc = OntologyService()
        types_resp = svc.list_object_types(ontology_id)
        links_resp = svc.list_link_types(ontology_id)
        actions_resp = svc.list_action_types(ontology_id)

        obj_types = types_resp.get("object_types", []) if isinstance(types_resp, dict) else []
        link_types = links_resp.get("link_types", []) if isinstance(links_resp, dict) else []
        action_types = actions_resp.get("action_types", []) if isinstance(actions_resp, dict) else []

        summary = {
            "ontology_id": ontology_id,
            "object_type_count": len(obj_types),
            "link_type_count": len(link_types),
            "action_type_count": len(action_types),
            "object_types": [
                {
                    "name": t.get("name", ""),
                    "property_count": len(t.get("properties", [])),
                    "properties": [p.get("name", "") for p in t.get("properties", [])],
                }
                for t in obj_types
            ],
            "link_types": [
                {
                    "name": l.get("name", ""),
                    "source": l.get("source_type", ""),
                    "target": l.get("target_type", ""),
                    "cardinality": l.get("cardinality", "SINGLE"),
                }
                for l in link_types
            ],
            "action_types": [
                {
                    "name": a.get("name", ""),
                    "target": a.get("target_object_type", ""),
                    "parameters": a.get("parameters", []),
                }
                for a in action_types
            ],
        }
        return {"status": "success", "context": summary}
    except Exception as e:
        logger.warning("get_ontology_context failed: %s", e)
        return {"status": "error", "message": f"failed to get ontology context: {e}"}


# ── Convenience: get the raw ToolRegistry ─────────────────────────────────────

def get_tool_registry() -> ToolRegistry:
    """Return the OpenHarness ToolRegistry with all AI assistant tools registered."""
    return _registry
