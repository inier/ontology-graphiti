import logging
import asyncio
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HookAdapter:

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {
            "pre_execute": [],
            "post_execute": [],
            "on_error": [],
            "on_complete": [],
        }
        self._openharness_hooks = None
        self._available = False
        self._init_hooks()

    def _init_hooks(self):
        try:
            from openharness.hooks import HookManager
            self._openharness_hooks = HookManager()
            self._available = True
            logger.info("HookAdapter: OpenHarness HookManager available")
        except ImportError:
            logger.debug("HookAdapter: OpenHarness HookManager not available, using local hooks")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def register_hook(self, event: str, handler: Callable) -> Dict[str, Any]:
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
        if self._available and self._openharness_hooks:
            try:
                self._openharness_hooks.register(event, handler)
            except Exception as e:
                logger.debug("HookAdapter: failed to register with OpenHarness: %s", e)
        return {"status": "success", "event": event, "handler": handler.__name__ if hasattr(handler, '__name__') else str(handler)}

    async def trigger_hook(self, event: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        handlers = self._hooks.get(event, [])
        results = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(context or {})
                else:
                    result = handler(context or {})
                results.append({"handler": handler.__name__ if hasattr(handler, '__name__') else str(handler), "result": result})
            except Exception as e:
                logger.warning("HookAdapter: handler error for %s: %s", event, e)
                results.append({"handler": handler.__name__ if hasattr(handler, '__name__') else str(handler), "error": str(e)})
        return {"status": "success", "event": event, "results": results, "count": len(results)}

    def unregister_hook(self, event: str, handler: Callable) -> Dict[str, Any]:
        handlers = self._hooks.get(event, [])
        if handler in handlers:
            handlers.remove(handler)
            return {"status": "success", "event": event, "removed": True}
        return {"status": "error", "message": f"Handler not found for event: {event}"}

    def list_hooks(self, event: str = None) -> Dict[str, Any]:
        if event:
            handlers = self._hooks.get(event, [])
            return {"status": "success", "event": event, "handlers": [h.__name__ if hasattr(h, '__name__') else str(h) for h in handlers]}
        return {"status": "success", "hooks": {k: [h.__name__ if hasattr(h, '__name__') else str(h) for h in v] for k, v in self._hooks.items()}}


_hook_adapter: Optional[HookAdapter] = None


def get_hook_adapter() -> HookAdapter:
    global _hook_adapter
    if _hook_adapter is None:
        _hook_adapter = HookAdapter()
    return _hook_adapter
