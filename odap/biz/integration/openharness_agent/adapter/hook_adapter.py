import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("hook_adapter")

try:
    from odap.biz.integration.hook_system.impl.hook_manager import HookManager
    _HOOK_SYSTEM_AVAILABLE = True
except ImportError:
    _HOOK_SYSTEM_AVAILABLE = False


class HookAdapter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._pre_hooks: Dict[str, List[Dict[str, Any]]] = {}
        self._post_hooks: Dict[str, List[Dict[str, Any]]] = {}
        self._initialized = True

    def register_pre_hook(
        self, event_type: str, handler: Callable, priority: int = 100
    ) -> Dict[str, Any]:
        hook_id = str(uuid.uuid4())

        if event_type not in self._pre_hooks:
            self._pre_hooks[event_type] = []

        self._pre_hooks[event_type].append(
            {
                "hook_id": hook_id,
                "event_type": event_type,
                "handler": handler,
                "priority": priority,
                "phase": "pre",
            }
        )
        self._pre_hooks[event_type].sort(key=lambda x: x["priority"])

        if _HOOK_SYSTEM_AVAILABLE:
            try:
                manager = HookManager()
                manager.register_hook(
                    hook_id=hook_id,
                    event_type=event_type,
                    handler=handler,
                    phase="pre",
                    priority=priority,
                )
            except Exception as e:
                logger.debug("Hook system registration fallback: %s", e)

        return {"status": "success", "hook_id": hook_id, "phase": "pre", "event_type": event_type}

    def register_post_hook(
        self, event_type: str, handler: Callable, priority: int = 100
    ) -> Dict[str, Any]:
        hook_id = str(uuid.uuid4())

        if event_type not in self._post_hooks:
            self._post_hooks[event_type] = []

        self._post_hooks[event_type].append(
            {
                "hook_id": hook_id,
                "event_type": event_type,
                "handler": handler,
                "priority": priority,
                "phase": "post",
            }
        )
        self._post_hooks[event_type].sort(key=lambda x: x["priority"])

        if _HOOK_SYSTEM_AVAILABLE:
            try:
                manager = HookManager()
                manager.register_hook(
                    hook_id=hook_id,
                    event_type=event_type,
                    handler=handler,
                    phase="post",
                    priority=priority,
                )
            except Exception as e:
                logger.debug("Hook system registration fallback: %s", e)

        return {"status": "success", "hook_id": hook_id, "phase": "post", "event_type": event_type}

    def unregister_hook(self, hook_id: str) -> Dict[str, Any]:
        for event_type, hooks in self._pre_hooks.items():
            for i, hook in enumerate(hooks):
                if hook["hook_id"] == hook_id:
                    hooks.pop(i)
                    return {"status": "success", "hook_id": hook_id}

        for event_type, hooks in self._post_hooks.items():
            for i, hook in enumerate(hooks):
                if hook["hook_id"] == hook_id:
                    hooks.pop(i)
                    return {"status": "success", "hook_id": hook_id}

        return {"status": "error", "message": f"Hook {hook_id} not found"}

    def emit_event(self, event_type: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        results = []

        pre_hooks = self._pre_hooks.get(event_type, [])
        for hook in pre_hooks:
            try:
                result = hook["handler"](context or {})
                results.append({"hook_id": hook["hook_id"], "phase": "pre", "result": result})
            except Exception as e:
                results.append({"hook_id": hook["hook_id"], "phase": "pre", "error": str(e)})

        post_hooks = self._post_hooks.get(event_type, [])
        for hook in post_hooks:
            try:
                result = hook["handler"](context or {})
                results.append({"hook_id": hook["hook_id"], "phase": "post", "result": result})
            except Exception as e:
                results.append({"hook_id": hook["hook_id"], "phase": "post", "error": str(e)})

        return {"status": "success", "event_type": event_type, "hook_results": results}
