import logging
import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MemoryTier:
    SHORT_TERM = "short_term"
    WORKING = "working"
    LONG_TERM = "long_term"


class MemoryEntry:
    def __init__(self, key: str, value: Any, tier: str, ttl: Optional[int] = None, timestamp: Optional[float] = None):
        self.key = key
        self.value = value
        self.tier = tier
        self.ttl = ttl
        self.timestamp = timestamp or datetime.now(timezone.utc).timestamp()
        self.access_count = 0

    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        elapsed = datetime.now(timezone.utc).timestamp() - self.timestamp
        return elapsed > self.ttl

    def access(self):
        self.access_count += 1


class SessionMemoryManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._short_term: Dict[str, Dict[str, MemoryEntry]] = {}
        self._working: Dict[str, Dict[str, MemoryEntry]] = {}
        self._long_term: Dict[str, MemoryEntry] = {}
        self._SHORT_TERM_TTL = 30 * 60
        self._WORKING_TTL = 2 * 60 * 60
        self._initialized = True

    def _get_adapter(self):
        try:
            from odap.biz.integration.openharness_agent.adapter.memory_adapter import MemoryAdapter
            return MemoryAdapter()
        except Exception:
            return None

    def store_short_term(self, session_id: str, key: str, value: Any) -> Dict[str, Any]:
        if session_id not in self._short_term:
            self._short_term[session_id] = {}
        entry = MemoryEntry(key, value, MemoryTier.SHORT_TERM, ttl=self._SHORT_TERM_TTL)
        self._short_term[session_id][key] = entry
        adapter = self._get_adapter()
        if adapter:
            try:
                adapter.store_short_term(session_id, key, value, ttl=self._SHORT_TERM_TTL)
            except Exception as e:
                logger.debug("Adapter store_short_term fallback: %s", e)
        return {"status": "success", "session_id": session_id, "key": key, "tier": MemoryTier.SHORT_TERM}

    def store_working(self, session_id: str, key: str, value: Any) -> Dict[str, Any]:
        if session_id not in self._working:
            self._working[session_id] = {}
        entry = MemoryEntry(key, value, MemoryTier.WORKING, ttl=self._WORKING_TTL)
        self._working[session_id][key] = entry
        adapter = self._get_adapter()
        if adapter:
            try:
                adapter.store_working(session_id, key, value, ttl=self._WORKING_TTL)
            except Exception as e:
                logger.debug("Adapter store_working fallback: %s", e)
        return {"status": "success", "session_id": session_id, "key": key, "tier": MemoryTier.WORKING}

    def store_long_term(self, key: str, value: Any) -> Dict[str, Any]:
        entry = MemoryEntry(key, value, MemoryTier.LONG_TERM, ttl=None)
        self._long_term[key] = entry
        adapter = self._get_adapter()
        if adapter:
            try:
                adapter.store_long_term(key, value)
            except Exception as e:
                logger.debug("Adapter store_long_term fallback: %s", e)
        return {"status": "success", "key": key, "tier": MemoryTier.LONG_TERM}

    def retrieve_short_term(self, session_id: str, key: str) -> Dict[str, Any]:
        entries = self._short_term.get(session_id, {})
        entry = entries.get(key)
        if not entry or entry.is_expired():
            if entry:
                del entries[key]
            return {"status": "error", "message": "Not found or expired"}
        entry.access()
        return {"status": "success", "key": key, "value": entry.value, "tier": MemoryTier.SHORT_TERM}

    def retrieve_working(self, session_id: str, key: str) -> Dict[str, Any]:
        entries = self._working.get(session_id, {})
        entry = entries.get(key)
        if not entry or entry.is_expired():
            if entry:
                del entries[key]
            return {"status": "error", "message": "Not found or expired"}
        entry.access()
        return {"status": "success", "key": key, "value": entry.value, "tier": MemoryTier.WORKING}

    def retrieve_long_term(self, query: str, limit: int = 10) -> Dict[str, Any]:
        results = []
        query_lower = query.lower()
        for key, entry in self._long_term.items():
            if query_lower in str(key).lower() or query_lower in str(entry.value).lower():
                score = self._compute_relevance(query_lower, key, entry)
                results.append({"key": key, "value": entry.value, "score": score})
        results.sort(key=lambda x: x["score"], reverse=True)
        return {"status": "success", "results": results[:limit], "count": len(results)}

    def get_session_memory(self, session_id: str) -> Dict[str, Any]:
        short_term = {}
        for key, entry in self._short_term.get(session_id, {}).items():
            if not entry.is_expired():
                short_term[key] = entry.value
        working = {}
        for key, entry in self._working.get(session_id, {}).items():
            if not entry.is_expired():
                working[key] = entry.value
        return {
            "session_id": session_id,
            "short_term": short_term,
            "working": working,
            "short_term_count": len(short_term),
            "working_count": len(working),
        }

    def clear_short_term(self, session_id: str) -> Dict[str, Any]:
        count = len(self._short_term.get(session_id, {}))
        self._short_term.pop(session_id, None)
        return {"status": "success", "session_id": session_id, "cleared_count": count}

    def _compute_relevance(self, query: str, key: str, entry: MemoryEntry) -> float:
        score = 0.0
        if query in str(key).lower():
            score += 2.0
        if query in str(entry.value).lower():
            score += 1.0
        elapsed = datetime.now(timezone.utc).timestamp() - entry.timestamp
        time_decay = math.exp(-elapsed / (7 * 24 * 3600))
        score *= time_decay
        score += min(entry.access_count * 0.1, 1.0)
        return score


_session_memory_manager: Optional[SessionMemoryManager] = None


def get_session_memory_manager() -> SessionMemoryManager:
    global _session_memory_manager
    if _session_memory_manager is None:
        _session_memory_manager = SessionMemoryManager()
    return _session_memory_manager
