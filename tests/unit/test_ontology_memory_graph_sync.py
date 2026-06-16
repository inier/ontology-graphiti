import pytest
import json
from unittest.mock import patch, MagicMock


class TestMemoryGraphSyncStorage:
    def _make_storage(self, tmp_path):
        from odap.biz.platform.ontology_memory.graph_sync.memory_graph_sync import MemoryGraphSyncStorage
        db_path = str(tmp_path / "test_sync.db")
        return MemoryGraphSyncStorage(db_path=db_path)

    def test_init_db(self, tmp_path):
        storage = self._make_storage(tmp_path)
        import sqlite3
        conn = sqlite3.connect(storage.db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_graph_sync_map'")
        assert c.fetchone() is not None
        conn.close()

    def test_save_and_get_sync(self, tmp_path):
        storage = self._make_storage(tmp_path)
        sync_id = storage.save_sync("mem-1", "entity-1", "Episode:mem-1", "memory_to_graph")
        assert sync_id.startswith("sync-")
        record = storage.get_by_memory("mem-1")
        assert record is not None
        assert record["memory_id"] == "mem-1"
        assert record["graph_entity_id"] == "entity-1"
        assert record["sync_type"] == "memory_to_graph"
        assert record["sync_status"] == "synced"

    def test_get_by_memory_not_found(self, tmp_path):
        storage = self._make_storage(tmp_path)
        result = storage.get_by_memory("nonexistent")
        assert result is None

    def test_get_by_graph_entity(self, tmp_path):
        storage = self._make_storage(tmp_path)
        storage.save_sync("mem-2", "entity-2", "Episode:mem-2", "memory_to_graph")
        record = storage.get_by_graph_entity("entity-2")
        assert record is not None
        assert record["memory_id"] == "mem-2"

    def test_get_by_graph_entity_not_found(self, tmp_path):
        storage = self._make_storage(tmp_path)
        result = storage.get_by_graph_entity("nonexistent")
        assert result is None

    def test_update_sync_status(self, tmp_path):
        storage = self._make_storage(tmp_path)
        storage.save_sync("mem-3", "entity-3", "Episode:mem-3", "memory_to_graph")
        result = storage.update_sync_status("mem-3", "decayed")
        assert result is True
        record = storage.get_by_memory("mem-3")
        assert record["sync_status"] == "decayed"

    def test_update_sync_status_not_found(self, tmp_path):
        storage = self._make_storage(tmp_path)
        result = storage.update_sync_status("nonexistent", "decayed")
        assert result is False

    def test_list_unsynced(self, tmp_path):
        storage = self._make_storage(tmp_path)
        storage.save_sync("mem-4", "entity-4", "Episode:mem-4", "memory_to_graph",
                         {"status": "pending"})
        storage.update_sync_status("mem-4", "pending")
        storage.save_sync("mem-5", "entity-5", "Episode:mem-5", "memory_to_graph")
        unsynced = storage.list_unsynced()
        assert len(unsynced) >= 1
        assert any(r["memory_id"] == "mem-4" for r in unsynced)

    def test_save_sync_with_metadata(self, tmp_path):
        storage = self._make_storage(tmp_path)
        storage.save_sync("mem-6", "entity-6", "Episode:mem-6", "memory_to_graph",
                         {"reason": "GraphManager unavailable"})
        record = storage.get_by_memory("mem-6")
        assert record is not None
        metadata = json.loads(record["metadata"])
        assert metadata["reason"] == "GraphManager unavailable"

    def test_save_sync_upsert(self, tmp_path):
        storage = self._make_storage(tmp_path)
        storage.save_sync("mem-7", "entity-7", "Episode:mem-7", "memory_to_graph")
        storage.save_sync("mem-7", "entity-7-new", "Episode:mem-7-v2", "memory_to_graph")
        record = storage.get_by_memory("mem-7")
        assert record["graph_entity_id"] == "entity-7-new"


class TestMemoryGraphSyncService:
    def _make_service(self, tmp_path):
        from odap.biz.platform.ontology_memory.graph_sync.memory_graph_sync import (
            MemoryGraphSyncService, MemoryGraphSyncStorage
        )
        db_path = str(tmp_path / "test_sync.db")
        storage = MemoryGraphSyncStorage(db_path=db_path)
        service = MemoryGraphSyncService.__new__(MemoryGraphSyncService)
        service.storage = storage
        return service

    def test_sync_memory_to_graph_working_memory_skipped(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.sync_memory_to_graph("mem-1", memory_data={
            "memory_type": "working", "content": "temp"
        })
        assert result["status"] == "skipped"

    def test_sync_memory_to_graph_already_synced(self, tmp_path):
        service = self._make_service(tmp_path)
        service.storage.save_sync("mem-2", "entity-2", "Episode:mem-2", "memory_to_graph")
        result = service.sync_memory_to_graph("mem-2")
        assert result["status"] == "success"
        assert result["message"] == "Already synced"

    def test_sync_memory_to_graph_memory_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        with patch("odap.biz.platform.ontology_memory.graph_sync.memory_graph_sync.MemoryGraphSyncService.sync_memory_to_graph") as mock:
            pass
        result = service.sync_memory_to_graph("nonexistent", memory_data={
            "status": "error", "message": "Memory not found"
        })
        assert result["status"] == "error"

    def test_sync_memory_to_graph_no_graph_manager(self, tmp_path):
        service = self._make_service(tmp_path)
        with patch("odap.infra.query.get_graph_write_proxy",
                   side_effect=ImportError("GraphManager unavailable")):
            result = service.sync_memory_to_graph("mem-3", memory_data={
                "memory_type": "episodic", "content": "test content",
                "importance": 0.7, "source_scenario_id": "sc-1"
            })
            assert result["status"] == "pending"

    def test_on_memory_consolidated(self, tmp_path):
        service = self._make_service(tmp_path)
        service.storage.save_sync("src-1", "entity-src1", "Episode:src1", "memory_to_graph")
        service.storage.save_sync("src-2", "entity-src2", "Episode:src2", "memory_to_graph")
        with patch.object(service, "sync_memory_to_graph", return_value={"status": "success"}):
            result = service.on_memory_consolidated(["src-1", "src-2"], "result-1")
        assert result["status"] == "success"
        assert result["source_ids"] == ["src-1", "src-2"]
        assert result["result_id"] == "result-1"
        r1 = service.storage.get_by_memory("src-1")
        assert r1["sync_status"] == "consolidated"

    def test_on_memory_decayed(self, tmp_path):
        service = self._make_service(tmp_path)
        service.storage.save_sync("mem-4", "entity-4", "Episode:mem-4", "memory_to_graph")
        result = service.on_memory_decayed(["mem-4"])
        assert result["status"] == "success"
        assert result["decayed_count"] == 1
        record = service.storage.get_by_memory("mem-4")
        assert record["sync_status"] == "decayed"

    def test_on_memory_forgotten_archived(self, tmp_path):
        service = self._make_service(tmp_path)
        service.storage.save_sync("mem-5", "entity-5", "Episode:mem-5", "memory_to_graph")
        result = service.on_memory_forgotten(["mem-5"], archived=True)
        assert result["status"] == "success"
        assert result["archived"] is True
        record = service.storage.get_by_memory("mem-5")
        assert record["sync_status"] == "archived"

    def test_on_memory_forgotten_not_archived(self, tmp_path):
        service = self._make_service(tmp_path)
        service.storage.save_sync("mem-6", "entity-6", "Episode:mem-6", "memory_to_graph")
        with patch.dict("sys.modules", {"odap.infra.graph": None}):
            result = service.on_memory_forgotten(["mem-6"], archived=False)
        assert result["status"] == "success"
        record = service.storage.get_by_memory("mem-6")
        assert record["sync_status"] == "forgotten"

    def test_on_memory_forgotten_no_sync_record(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.on_memory_forgotten(["nonexistent"], archived=False)
        assert result["status"] == "success"
        assert result["forgotten_count"] == 1

    def test_get_sync_status_not_synced(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.get_sync_status("nonexistent")
        assert result["status"] == "not_synced"

    def test_get_sync_status_synced(self, tmp_path):
        service = self._make_service(tmp_path)
        service.storage.save_sync("mem-7", "entity-7", "Episode:mem-7", "memory_to_graph")
        result = service.get_sync_status("mem-7")
        assert result["status"] == "success"
        assert result["graph_entity_id"] == "entity-7"

    def test_list_unsynced(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.list_unsynced()
        assert result["status"] == "success"

    def test_sync_graph_to_memory_no_graph_manager(self, tmp_path):
        service = self._make_service(tmp_path)
        with patch("odap.infra.query.get_query_service",
                   side_effect=ImportError("GraphManager unavailable")):
            with pytest.raises(ImportError, match="GraphManager unavailable"):
                service.sync_graph_to_memory()


class TestSharedMemoryStorage:
    def _make_storage(self, tmp_path):
        from odap.biz.platform.ontology_memory.shared_workspace.shared_memory_service import SharedMemoryStorage
        db_path = str(tmp_path / "test_shared.db")
        return SharedMemoryStorage(db_path=db_path)

    def test_init_db(self, tmp_path):
        storage = self._make_storage(tmp_path)
        import sqlite3
        conn = sqlite3.connect(storage.db_path)
        c = conn.cursor()
        for table in ["shared_contexts", "agent_states", "shared_events"]:
            c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            assert c.fetchone() is not None
        conn.close()

    def test_save_and_get_context(self, tmp_path):
        storage = self._make_storage(tmp_path)
        ctx = {
            "context_id": "ctx-1", "name": "Test Context",
            "description": "desc", "scenario_id": "sc-1",
            "session_id": "sess-1", "shared_state": {"key": "val"},
            "version": 1, "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        storage.save_context(ctx)
        result = storage.get_context("ctx-1")
        assert result is not None
        assert result["name"] == "Test Context"
        assert result["scenario_id"] == "sc-1"

    def test_get_context_not_found(self, tmp_path):
        storage = self._make_storage(tmp_path)
        result = storage.get_context("nonexistent")
        assert result is None

    def test_list_contexts(self, tmp_path):
        storage = self._make_storage(tmp_path)
        for i in range(3):
            ctx = {
                "context_id": f"ctx-{i}", "name": f"Context {i}",
                "description": "", "shared_state": {},
                "version": 1, "is_active": True,
                "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
            }
            storage.save_context(ctx)
        results = storage.list_contexts()
        assert len(results) == 3

    def test_list_contexts_by_scenario(self, tmp_path):
        storage = self._make_storage(tmp_path)
        ctx1 = {
            "context_id": "ctx-a", "name": "A", "scenario_id": "sc-1",
            "shared_state": {}, "version": 1, "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        ctx2 = {
            "context_id": "ctx-b", "name": "B", "scenario_id": "sc-2",
            "shared_state": {}, "version": 1, "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        storage.save_context(ctx1)
        storage.save_context(ctx2)
        results = storage.list_contexts(scenario_id="sc-1")
        assert len(results) == 1
        assert results[0]["context_id"] == "ctx-a"

    def test_delete_context(self, tmp_path):
        storage = self._make_storage(tmp_path)
        ctx = {
            "context_id": "ctx-del", "name": "Delete Me",
            "shared_state": {}, "version": 1, "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        storage.save_context(ctx)
        result = storage.delete_context("ctx-del")
        assert result is True
        assert storage.get_context("ctx-del") is None

    def test_delete_context_not_found(self, tmp_path):
        storage = self._make_storage(tmp_path)
        result = storage.delete_context("nonexistent")
        assert result is False

    def test_save_and_get_agent_state(self, tmp_path):
        storage = self._make_storage(tmp_path)
        ctx = {
            "context_id": "ctx-1", "name": "Test",
            "shared_state": {}, "version": 1, "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        storage.save_context(ctx)
        state = {
            "state_id": "as-1", "context_id": "ctx-1", "agent_id": "agent-1",
            "agent_role": "analyst", "state_data": {"task": "analyze"},
            "last_heartbeat": "2025-01-01T00:00:00", "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        storage.save_agent_state(state)
        result = storage.get_agent_state("ctx-1", "agent-1")
        assert result is not None
        assert result["agent_id"] == "agent-1"
        assert result["agent_role"] == "analyst"

    def test_get_agent_state_not_found(self, tmp_path):
        storage = self._make_storage(tmp_path)
        result = storage.get_agent_state("nonexistent", "nonexistent")
        assert result is None

    def test_list_agent_states(self, tmp_path):
        storage = self._make_storage(tmp_path)
        ctx = {
            "context_id": "ctx-2", "name": "Test",
            "shared_state": {}, "version": 1, "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        storage.save_context(ctx)
        for i in range(3):
            state = {
                "state_id": f"as-{i}", "context_id": "ctx-2", "agent_id": f"agent-{i}",
                "state_data": {}, "last_heartbeat": "2025-01-01T00:00:00",
                "is_active": True,
                "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
            }
            storage.save_agent_state(state)
        results = storage.list_agent_states("ctx-2")
        assert len(results) == 3

    def test_save_and_get_events(self, tmp_path):
        storage = self._make_storage(tmp_path)
        ctx = {
            "context_id": "ctx-3", "name": "Test",
            "shared_state": {}, "version": 1, "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        storage.save_context(ctx)
        event = {
            "event_id": "evt-1", "context_id": "ctx-3", "agent_id": "agent-1",
            "event_type": "state_update", "event_data": {"action": "joined"},
            "created_at": "2025-01-01T00:00:00"
        }
        storage.save_event(event)
        events = storage.get_pending_events("ctx-3")
        assert len(events) == 1
        assert events[0]["event_type"] == "state_update"

    def test_get_pending_events_for_agent(self, tmp_path):
        storage = self._make_storage(tmp_path)
        ctx = {
            "context_id": "ctx-4", "name": "Test",
            "shared_state": {}, "version": 1, "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        storage.save_context(ctx)
        e1 = {
            "event_id": "evt-2", "context_id": "ctx-4", "agent_id": "agent-1",
            "event_type": "state_update", "event_data": {},
            "target_agent_id": "agent-2", "created_at": "2025-01-01T00:00:00"
        }
        e2 = {
            "event_id": "evt-3", "context_id": "ctx-4", "agent_id": "agent-1",
            "event_type": "state_update", "event_data": {},
            "created_at": "2025-01-01T00:01:00"
        }
        storage.save_event(e1)
        storage.save_event(e2)
        events = storage.get_pending_events("ctx-4", agent_id="agent-2")
        assert len(events) == 2

    def test_consume_event(self, tmp_path):
        storage = self._make_storage(tmp_path)
        ctx = {
            "context_id": "ctx-5", "name": "Test",
            "shared_state": {}, "version": 1, "is_active": True,
            "created_at": "2025-01-01T00:00:00", "updated_at": "2025-01-01T00:00:00"
        }
        storage.save_context(ctx)
        event = {
            "event_id": "evt-4", "context_id": "ctx-5", "agent_id": "agent-1",
            "event_type": "state_update", "event_data": {},
            "created_at": "2025-01-01T00:00:00"
        }
        storage.save_event(event)
        result = storage.consume_event("evt-4")
        assert result is True
        events = storage.get_pending_events("ctx-5")
        assert len(events) == 0

    def test_consume_event_not_found(self, tmp_path):
        storage = self._make_storage(tmp_path)
        result = storage.consume_event("nonexistent")
        assert result is False


class TestSharedMemoryService:
    def _make_service(self, tmp_path):
        from odap.biz.platform.ontology_memory.shared_workspace.shared_memory_service import (
            SharedMemoryService, SharedMemoryStorage
        )
        db_path = str(tmp_path / "test_shared.db")
        storage = SharedMemoryStorage(db_path=db_path)
        service = SharedMemoryService.__new__(SharedMemoryService)
        service.storage = storage
        return service

    def test_create_context(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.create_context("Test Context", description="desc")
        assert result["status"] == "success"
        assert result["name"] == "Test Context"
        assert result["version"] == 1
        assert result["context_id"].startswith("ctx-")

    def test_get_context(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        result = service.get_context(created["context_id"])
        assert result["status"] == "success"
        assert result["name"] == "Test"

    def test_get_context_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.get_context("nonexistent")
        assert result["status"] == "error"

    def test_list_contexts(self, tmp_path):
        service = self._make_service(tmp_path)
        service.create_context("Ctx1")
        service.create_context("Ctx2")
        result = service.list_contexts()
        assert result["status"] == "success"
        assert result["count"] == 2

    def test_delete_context(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("ToDelete")
        result = service.delete_context(created["context_id"])
        assert result["status"] == "success"

    def test_delete_context_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.delete_context("nonexistent")
        assert result["status"] == "error"

    def test_join_context(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        result = service.join_context(created["context_id"], "agent-1", "analyst")
        assert result["status"] == "success"
        assert result["agent_id"] == "agent-1"

    def test_join_context_already_joined(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        service.join_context(created["context_id"], "agent-1")
        result = service.join_context(created["context_id"], "agent-1")
        assert result["status"] == "success"
        assert result["message"] == "Already joined"

    def test_join_context_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.join_context("nonexistent", "agent-1")
        assert result["status"] == "error"

    def test_leave_context(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        service.join_context(created["context_id"], "agent-1")
        result = service.leave_context(created["context_id"], "agent-1")
        assert result["status"] == "success"

    def test_leave_context_not_joined(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        result = service.leave_context(created["context_id"], "agent-1")
        assert result["status"] == "error"

    def test_heartbeat(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        service.join_context(created["context_id"], "agent-1")
        result = service.heartbeat(created["context_id"], "agent-1", {"progress": 50})
        assert result["status"] == "success"
        assert "heartbeat_at" in result

    def test_heartbeat_not_joined(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        result = service.heartbeat(created["context_id"], "agent-1")
        assert result["status"] == "error"

    def test_update_shared_state(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        result = service.update_shared_state(created["context_id"], "agent-1",
                                             {"task_status": "in_progress"})
        assert result["status"] == "success"
        assert result["version"] == 2
        assert result["conflicts"] == []

    def test_update_shared_state_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.update_shared_state("nonexistent", "agent-1", {"key": "val"})
        assert result["status"] == "error"

    def test_read_shared_state(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        service.update_shared_state(created["context_id"], "agent-1",
                                    {"key1": "val1", "key2": "val2"})
        result = service.read_shared_state(created["context_id"], keys=["key1"])
        assert result["status"] == "success"
        assert "key1" in result["shared_state"]
        assert "key2" not in result["shared_state"]

    def test_read_shared_state_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.read_shared_state("nonexistent")
        assert result["status"] == "error"

    def test_get_agent_states(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        service.join_context(created["context_id"], "agent-1", "analyst")
        service.join_context(created["context_id"], "agent-2", "planner")
        result = service.get_agent_states(created["context_id"])
        assert result["status"] == "success"
        assert len(result["agents"]) == 2

    def test_get_pending_events(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        service.join_context(created["context_id"], "agent-1")
        service.update_shared_state(created["context_id"], "agent-1", {"key": "val"})
        result = service.get_pending_events(created["context_id"])
        assert result["status"] == "success"
        assert result["count"] >= 1

    def test_consume_event(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        service.join_context(created["context_id"], "agent-1")
        service.update_shared_state(created["context_id"], "agent-1", {"key": "val"})
        events = service.get_pending_events(created["context_id"])
        event_id = events["events"][0]["event_id"]
        result = service.consume_event(event_id)
        assert result["status"] == "success"

    def test_consume_event_not_found(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.consume_event("nonexistent")
        assert result["status"] == "error"

    def test_request_consensus(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        service.join_context(created["context_id"], "agent-1")
        result = service.request_consensus(created["context_id"], "agent-1",
                                           "topic-1", "proposal text")
        assert result["status"] == "success"

    def test_vote_consensus(self, tmp_path):
        service = self._make_service(tmp_path)
        created = service.create_context("Test")
        service.join_context(created["context_id"], "agent-1")
        result = service.vote_consensus(created["context_id"], "agent-1",
                                        "topic-1", "agree", "looks good")
        assert result["status"] == "success"

    def test_service_returns_dict(self, tmp_path):
        service = self._make_service(tmp_path)
        result = service.create_context("Test")
        assert isinstance(result, dict)
        result2 = service.get_context(result["context_id"])
        assert isinstance(result2, dict)

    def test_shared_event_type_enum(self):
        from odap.biz.platform.ontology_memory.shared_workspace.shared_memory_service import SharedEventType
        assert SharedEventType.STATE_UPDATE.value == "state_update"
        assert SharedEventType.CONSENSUS_REQUEST.value == "consensus_request"
        assert issubclass(SharedEventType, str)
