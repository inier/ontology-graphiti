import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("tool_adapter_v2")

try:
    from odap.infra.openharness.tool_adapter import OPENHARNESS_AVAILABLE, OpenHarnessToolAdapter
    _OH_AVAILABLE = OPENHARNESS_AVAILABLE
except ImportError:
    _OH_AVAILABLE = False


class ToolAdapterV2:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

    def register_tool(self, tool_def: Dict[str, Any]) -> Dict[str, Any]:
        tool_id = tool_def.get("tool_id", str(uuid.uuid4()))
        name = tool_def.get("name", "unnamed_tool")
        description = tool_def.get("description", "")
        handler = tool_def.get("handler")
        category = tool_def.get("category", "general")
        permissions = tool_def.get("permissions", [])

        self._tools[tool_id] = {
            "tool_id": tool_id,
            "name": name,
            "description": description,
            "handler": handler,
            "category": category,
            "permissions": permissions,
            "status": "active",
        }

        if _OH_AVAILABLE and handler:
            try:
                oh_adapter = OpenHarnessToolAdapter(
                    name=name,
                    description=description,
                    handler=handler,
                    category=category,
                )
                self._tools[tool_id]["oh_adapter"] = oh_adapter
                return {
                    "status": "success",
                    "tool_id": tool_id,
                    "registered_in_openharness": True,
                }
            except Exception as e:
                logger.warning("Register tool in OpenHarness failed: %s", e)

        return {"status": "success", "tool_id": tool_id, "registered_in_openharness": False}

    def unregister_tool(self, tool_id: str) -> Dict[str, Any]:
        if tool_id not in self._tools:
            return {"status": "error", "message": f"Tool {tool_id} not found"}

        del self._tools[tool_id]
        return {"status": "success", "tool_id": tool_id}

    def invoke_tool(self, tool_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tool = self._tools.get(tool_id)
        if not tool:
            return {"status": "error", "message": f"Tool {tool_id} not found"}

        handler = tool.get("handler")
        if not handler:
            return {"status": "error", "message": f"Tool {tool_id} has no handler"}

        try:
            result = handler(**(params or {}))
            return {"status": "success", "tool_id": tool_id, "result": result}
        except Exception as e:
            return {"status": "error", "tool_id": tool_id, "message": str(e)}

    def list_tools(self, category: Optional[str] = None) -> Dict[str, Any]:
        results = []
        for tool_id, tool in self._tools.items():
            if category and tool.get("category") != category:
                continue
            results.append(
                {
                    "tool_id": tool_id,
                    "name": tool.get("name"),
                    "description": tool.get("description"),
                    "category": tool.get("category"),
                    "status": tool.get("status"),
                    "permissions": tool.get("permissions", []),
                }
            )

        return {"status": "success", "tools": results, "count": len(results)}
