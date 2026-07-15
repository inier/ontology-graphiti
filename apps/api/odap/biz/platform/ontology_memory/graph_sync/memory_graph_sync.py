from typing import Dict, Any, List, Optional
from .storage import MemoryGraphSyncStorage


class MemoryGraphSyncService:
    _instance = None

    @classmethod
    def get_instance(cls, storage=None):
        if cls._instance is None:
            cls._instance = cls(storage)
        return cls._instance

    def __init__(self, storage=None):
        self.storage = storage or MemoryGraphSyncStorage()

    def sync_memory_to_graph(self, memory_id, memory_data=None):
        existing = self.storage.get_by_memory(memory_id)
        if existing and existing.get("sync_status") == "synced":
            return {"status": "success", "message": "Already synced", "sync_id": existing["sync_id"]}
        if memory_data is None:
            from odap.biz.platform.ontology_memory.services.memory_service import OntologyMemoryService
            mem_service = OntologyMemoryService.get_instance()
            memory_data = mem_service.get_memory(memory_id)
        if memory_data.get("status") == "error":
            return {"status": "error", "message": "Memory not found"}
        memory_type = memory_data.get("memory_type", "episodic")
        content = memory_data.get("content", "")
        if memory_type == "working":
            return {"status": "skipped", "message": "Working memory is not synced to graph"}
        try:
            from odap.infra.query import get_graph_write_proxy
            write_proxy = get_graph_write_proxy()
        except Exception:
            write_proxy = None
        if write_proxy is None:
            sync_id = self.storage.save_sync(memory_id, "", "", "memory_to_graph",
                                             {"status": "pending", "reason": "GraphManager unavailable"})
            return {"status": "pending", "sync_id": sync_id, "message": "Queued for sync when GraphManager available"}
        entity_id = f"mem-{memory_id}"
        entity_type = "MemoryEpisode" if memory_type == "episodic" else "MemoryKnowledge"
        properties = {
            "memory_type": memory_type,
            "content": content[:500],
            "importance": memory_data.get("importance", 0.5),
            "scenario_id": memory_data.get("source_scenario_id", ""),
            "keywords": memory_data.get("keywords", []),
        }
        try:
            write_proxy.add_entity(entity_id=entity_id, entity_type=entity_type, properties=properties)
            episode_name = f"Memory:{memory_id}"
            sync_id = self.storage.save_sync(memory_id, entity_id, episode_name, "memory_to_graph")
            return {"status": "success", "sync_id": sync_id, "entity_id": entity_id}
        except Exception as e:
            sync_id = self.storage.save_sync(memory_id, "", "", "memory_to_graph",
                                             {"status": "failed", "error": str(e)})
            return {"status": "error", "message": str(e), "sync_id": sync_id}

    def sync_graph_to_memory(self, scenario_id=None, limit=50):
        # Use QueryService for read operations instead of direct GraphManager
        from odap.infra.query import get_query_service
        query_service = get_query_service()
        result = query_service.execute(
            workspace_id=scenario_id or "default",
            query=f".entity with(type='MemoryEpisode') list()",
            limit=limit,
        )
        entities = result.rows
        synced = 0
        for entity in entities[:limit]:
            entity_id = entity.get("entity_id", "")
            existing = self.storage.get_by_graph_entity(entity_id)
            if existing:
                continue
            from odap.biz.platform.ontology_memory.services.memory_service import OntologyMemoryService
            mem_service = OntologyMemoryService.get_instance()
            props = entity.get("properties", {})
            result = mem_service.store_memory(
                memory_type=props.get("memory_type", "episodic"),
                content=props.get("content", ""),
                keywords=props.get("keywords", []),
                source_scenario_id=props.get("scenario_id"),
                importance=props.get("importance", 0.5)
            )
            if result.get("status") == "success":
                memory_id = result.get("memory_id", "")
                self.storage.save_sync(memory_id, entity_id, "", "graph_to_memory")
                synced += 1
        return {"status": "success", "synced_count": synced}

    def on_memory_consolidated(self, source_ids, result_id):
        for source_id in source_ids:
            self.storage.update_sync_status(source_id, "consolidated",
                                           {"consolidated_into": result_id})
        self.sync_memory_to_graph(result_id)
        return {"status": "success", "source_ids": source_ids, "result_id": result_id}

    def on_memory_decayed(self, decayed_ids):
        for memory_id in decayed_ids:
            self.storage.update_sync_status(memory_id, "decayed")
        return {"status": "success", "decayed_count": len(decayed_ids)}

    def on_memory_forgotten(self, forgotten_ids, archived=False):
        for memory_id in forgotten_ids:
            sync_record = self.storage.get_by_memory(memory_id)
            if not sync_record:
                continue
            entity_id = sync_record.get("graph_entity_id", "")
            if archived:
                self.storage.update_sync_status(memory_id, "archived")
            else:
                try:
                    from odap.infra.query import get_graph_write_proxy
                    write_proxy = get_graph_write_proxy()
                    if entity_id and write_proxy:
                        write_proxy.update_entity(entity_id, {"status": "forgotten"})
                except Exception:
                    pass
                self.storage.update_sync_status(memory_id, "forgotten")
        return {"status": "success", "forgotten_count": len(forgotten_ids), "archived": archived}

    def get_sync_status(self, memory_id):
        record = self.storage.get_by_memory(memory_id)
        if not record:
            return {"status": "not_synced", "memory_id": memory_id}
        return {"status": "success", "memory_id": memory_id,
                "graph_entity_id": record.get("graph_entity_id", ""),
                "sync_type": record.get("sync_type", ""),
                "sync_status": record.get("sync_status", ""),
                "last_synced_at": record.get("last_synced_at", "")}

    def list_unsynced(self, limit=100):
        records = self.storage.list_unsynced(limit)
        return {"status": "success", "count": len(records), "records": records}


get_memory_graph_sync = MemoryGraphSyncService.get_instance
