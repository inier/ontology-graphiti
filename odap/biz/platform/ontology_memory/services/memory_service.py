from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models import (
    MemoryEntry, MemoryType, MemoryStatus, DecayConfig
)
from ..impl.memory_engine import OntologyMemoryEngine


class OntologyMemoryService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.engine = OntologyMemoryEngine()

    def store_memory(self, memory_type: str, content: str,
                     summary: str = None, keywords: List[str] = None,
                     entities: List[str] = None,
                     source_scenario_id: str = None,
                     source_session_id: str = None,
                     importance: float = 0.5,
                     metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            entry = MemoryEntry(
                memory_type=MemoryType(memory_type),
                content=content,
                summary=summary,
                keywords=keywords or [],
                entities=entities or [],
                source_scenario_id=source_scenario_id,
                source_session_id=source_session_id,
                importance=importance,
                metadata=metadata or {}
            )
            result = self.engine.store(entry)
            return {
                "memory_id": result.memory_id,
                "memory_type": result.memory_type.value,
                "content": result.content,
                "summary": result.summary,
                "keywords": result.keywords,
                "entities": result.entities,
                "importance": result.importance,
                "status": result.status.value,
                "created_at": result.created_at.isoformat()
            }
        except ValueError as e:
            return {"status": "error", "message": str(e)}

    def get_memory(self, memory_id: str) -> Dict[str, Any]:
        entry = self.engine.storage.get_memory(memory_id)
        if not entry:
            return {"status": "error", "message": "Memory not found"}
        return {
            "memory_id": entry.memory_id,
            "memory_type": entry.memory_type.value,
            "content": entry.content,
            "summary": entry.summary,
            "keywords": entry.keywords,
            "entities": entry.entities,
            "source_scenario_id": entry.source_scenario_id,
            "source_session_id": entry.source_session_id,
            "importance": entry.importance,
            "access_count": entry.access_count,
            "decay_factor": entry.decay_factor,
            "status": entry.status.value,
            "created_at": entry.created_at.isoformat(),
            "last_accessed_at": entry.last_accessed_at.isoformat(),
            "expires_at": entry.expires_at,
            "metadata": entry.metadata
        }

    def list_memories(self, memory_type: str = None, status: str = None,
                      source_scenario_id: str = None,
                      page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        filters = {}
        if memory_type:
            filters["memory_type"] = memory_type
        if status:
            filters["status"] = status
        if source_scenario_id:
            filters["source_scenario_id"] = source_scenario_id
        entries = self.engine.storage.list_memories(
            filters=filters if filters else None,
            page=page, page_size=page_size
        )
        memory_list = []
        for entry in entries:
            memory_list.append({
                "memory_id": entry.memory_id,
                "memory_type": entry.memory_type.value,
                "content": entry.content[:200] if entry.content else "",
                "summary": entry.summary,
                "importance": entry.importance,
                "decay_factor": entry.decay_factor,
                "status": entry.status.value,
                "created_at": entry.created_at.isoformat()
            })
        return {
            "memories": memory_list,
            "page": page,
            "page_size": page_size,
            "total": len(memory_list)
        }

    def delete_memory(self, memory_id: str) -> Dict[str, Any]:
        success = self.engine.storage.delete_memory(memory_id)
        return {
            "status": "success" if success else "error",
            "message": "Memory deleted" if success else "Memory not found"
        }

    def retrieve_memories(self, query: str, memory_type: str = None,
                          top_k: int = 10, scenario_id: str = None,
                          method_weights: Dict[str, float] = None) -> Dict[str, Any]:
        mt = MemoryType(memory_type) if memory_type else None
        results = self.engine.retrieve(
            query=query,
            memory_type=mt,
            top_k=top_k,
            scenario_id=scenario_id,
            method_weights=method_weights
        )
        return {
            "results": results,
            "query": query,
            "total": len(results)
        }

    def consolidate_memories(self, memory_ids: List[str],
                             strategy: str = "merge") -> Dict[str, Any]:
        if not memory_ids or len(memory_ids) < 2:
            return {"status": "error", "message": "At least 2 memory IDs required"}
        return self.engine.consolidate(memory_ids, strategy=strategy)

    def decay_update(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        decay_config = None
        if config:
            decay_config = DecayConfig(**config)
        return self.engine.decay_update(config=decay_config)

    def forget_memories(self, threshold: float = 0.1,
                        archive: bool = False) -> Dict[str, Any]:
        return self.engine.forget(threshold=threshold, archive=archive)

    def get_statistics(self, scenario_id: str = None) -> Dict[str, Any]:
        return self.engine.get_statistics(scenario_id=scenario_id)
