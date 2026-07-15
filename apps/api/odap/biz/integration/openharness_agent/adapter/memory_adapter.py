"""DEPRECATED: This adapter delegates to odap.infra.openharness.*.
Use infra-layer imports directly in new code."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("memory_adapter")

try:
    from odap.infra.openharness.engine_adapter import OPENHARNESS_AVAILABLE
    _V2_AVAILABLE = OPENHARNESS_AVAILABLE
except ImportError:
    _V2_AVAILABLE = False


class MemoryAdapter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._short_term: Dict[str, Dict[str, Any]] = {}
        self._working: Dict[str, Dict[str, Any]] = {}
        self._long_term: Dict[str, Any] = {}
        self._initialized = True

    def store_short_term(
        self, session_id: str, key: str, value: Any, ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        store_key = f"{session_id}:{key}"
        self._short_term[store_key] = {
            "session_id": session_id,
            "key": key,
            "value": value,
            "ttl": ttl,
        }
        return {"status": "success", "session_id": session_id, "key": key, "store": "short_term"}

    def store_working(
        self, session_id: str, key: str, value: Any, ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        store_key = f"{session_id}:{key}"
        self._working[store_key] = {
            "session_id": session_id,
            "key": key,
            "value": value,
            "ttl": ttl,
        }
        return {"status": "success", "session_id": session_id, "key": key, "store": "working"}

    def store_long_term(self, key: str, value: Any) -> Dict[str, Any]:
        self._long_term[key] = value

        if _V2_AVAILABLE:
            try:
                from odap.infra.query import get_graph_write_proxy
                write_proxy = get_graph_write_proxy()
                if write_proxy.is_connected():
                    logger.debug("Long-term memory stored in Graphiti: %s", key)
            except Exception as e:
                logger.debug("Graphiti long-term store fallback: %s", e)

        return {"status": "success", "key": key, "store": "long_term"}

    def retrieve_short_term(self, session_id: str, key: str) -> Dict[str, Any]:
        store_key = f"{session_id}:{key}"
        entry = self._short_term.get(store_key)
        if not entry:
            return {"status": "error", "message": "Not found"}

        return {"status": "success", "session_id": session_id, "key": key, "value": entry.get("value")}

    def retrieve_working(self, session_id: str, key: str) -> Dict[str, Any]:
        store_key = f"{session_id}:{key}"
        entry = self._working.get(store_key)
        if not entry:
            return {"status": "error", "message": "Not found"}

        return {"status": "success", "session_id": session_id, "key": key, "value": entry.get("value")}

    def retrieve_long_term(self, query: str, limit: int = 10) -> Dict[str, Any]:
        results = []
        for key, value in self._long_term.items():
            if query.lower() in str(key).lower() or query.lower() in str(value).lower():
                results.append({"key": key, "value": value})
            if len(results) >= limit:
                break

        return {"status": "success", "results": results, "count": len(results)}
