import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.infra.graph.graph_service import GraphManager


@pytest.fixture(autouse=True)
def reset_graph_manager_singleton():
    GraphManager._test_mode = True
    yield
    GraphManager._instance = None
    GraphManager._initialized = False
    GraphManager._test_mode = False


@pytest.fixture
def graph_manager():
    with patch.object(GraphManager, '_connect'):
        gm = GraphManager.__new__(GraphManager)
        gm.graph = None
        gm.neo4j_uri = "bolt://localhost:7687"
        gm.neo4j_user = "neo4j"
        gm.neo4j_password = "test"
        gm.neo4j_driver = None
        gm.fallback_graph = None
        gm.reserved_tasks = []
        gm._connected = False
        gm._use_fallback = True
        gm._mode = "fallback"
        gm.max_pool_size = 20
        gm.pool_timeout = 30
        gm.idle_timeout = 300
        gm.pool = []
        gm.pool_creation_times = []
        gm.failure_threshold = 5
        gm.recovery_timeout = 60
        gm.failure_count = 0
        gm.circuit_open = False
        gm.last_failure_time = 0
        gm.query_times = []
        gm.cache_hits = 0
        gm.cache_misses = 0
        gm._query_cache = {}
        gm._query_cache_timestamps = {}
        gm._cache_max_size = 256
        gm._cache_ttl = 300
        gm._temporal_index = {}
        gm._temporal_index_built = False
        import networkx as nx
        gm.fallback_graph = nx.DiGraph()
        GraphManager._instance = gm
        GraphManager._initialized = True
        return gm


class TestFallbackModeInitialization:
    def test_fallback_mode_flag(self, graph_manager):
        assert graph_manager._use_fallback is True
        assert graph_manager._mode == "fallback"
        assert graph_manager._connected is False

    def test_fallback_graph_is_networkx(self, graph_manager):
        import networkx as nx
        assert isinstance(graph_manager.fallback_graph, nx.DiGraph)

    def test_fallback_graph_initially_empty(self, graph_manager):
        assert graph_manager.fallback_graph.number_of_nodes() == 0
        assert graph_manager.fallback_graph.number_of_edges() == 0

    def test_no_neo4j_driver(self, graph_manager):
        assert graph_manager.neo4j_driver is None


class TestAddAndQueryEntities:
    def test_add_entity(self, graph_manager):
        result = graph_manager.add_entity("entity-1", "Radar", {"name": "雷达站A", "status": "active"})
        assert result is True
        assert "entity-1" in graph_manager.fallback_graph

    def test_add_entity_properties(self, graph_manager):
        graph_manager.add_entity("entity-1", "Radar", {"name": "雷达站A", "status": "active"})
        data = graph_manager.fallback_graph.nodes["entity-1"]
        assert data["entity_type"] == "Radar"
        assert data["name"] == "雷达站A"
        assert data["status"] == "active"

    def test_add_entity_update_existing(self, graph_manager):
        graph_manager.add_entity("entity-1", "Radar", {"name": "雷达站A"})
        graph_manager.add_entity("entity-1", "Radar", {"name": "雷达站B", "status": "online"})
        data = graph_manager.fallback_graph.nodes["entity-1"]
        assert data["name"] == "雷达站B"
        assert data["status"] == "online"

    def test_query_entities_no_filter(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        result = graph_manager.query_entities()
        assert len(result) == 2

    def test_query_entities_by_type(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        result = graph_manager.query_entities(entity_type="Radar")
        assert len(result) == 1
        assert result[0]["type"] == "Radar"

    def test_query_entities_by_area(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1", "area": "north"})
        graph_manager.add_entity("e2", "Radar", {"name": "雷达2", "area": "south"})
        result = graph_manager.query_entities(area="north")
        assert len(result) == 1
        assert result[0]["id"] == "e1"

    def test_query_entities_result_format(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        result = graph_manager.query_entities()
        assert "id" in result[0]
        assert "type" in result[0]
        assert "properties" in result[0]
        assert result[0]["id"] == "e1"
        assert result[0]["type"] == "Radar"


class TestUpdateEntity:
    def test_update_entity_existing(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1", "status": "offline"})
        result = graph_manager.update_entity("e1", {"status": "online"})
        assert result is True
        data = graph_manager.fallback_graph.nodes["e1"]
        assert data["status"] == "online"
        assert data["name"] == "雷达1"

    def test_update_entity_nonexistent(self, graph_manager):
        result = graph_manager.update_entity("nonexistent", {"status": "online"})
        assert result is False

    def test_update_entity_adds_new_property(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.update_entity("e1", {"priority": "high"})
        data = graph_manager.fallback_graph.nodes["e1"]
        assert data["priority"] == "high"


class TestSearch:
    def test_search_by_id(self, graph_manager):
        graph_manager.add_entity("radar-alpha", "Radar", {"name": "雷达Alpha"})
        results = graph_manager.search("radar")
        assert len(results) >= 1
        assert results[0]["id"] == "radar-alpha"

    def test_search_by_name(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达Alpha"})
        results = graph_manager.search("alpha")
        assert len(results) >= 1

    def test_search_by_entity_type(self, graph_manager):
        graph_manager.add_entity("e1", "RadarStation", {"name": "站1"})
        results = graph_manager.search("radarstation")
        assert len(results) >= 1

    def test_search_case_insensitive(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达Alpha"})
        results = graph_manager.search("ALPHA")
        assert len(results) >= 1

    def test_search_no_match(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        results = graph_manager.search("nonexistent")
        assert len(results) == 0

    def test_search_limit(self, graph_manager):
        for i in range(10):
            graph_manager.add_entity(f"radar-{i}", "Radar", {"name": f"雷达{i}"})
        results = graph_manager.search("radar", limit=3)
        assert len(results) <= 3

    def test_search_empty_graph(self, graph_manager):
        results = graph_manager.search("anything")
        assert results == []


class TestRelationships:
    def test_add_relationship(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        result = graph_manager.add_relationship("e1", "e2", "TRACKS", {"confidence": 0.9})
        assert result is True

    def test_add_relationship_nonexistent_source(self, graph_manager):
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        result = graph_manager.add_relationship("nonexistent", "e2", "TRACKS")
        assert result is False

    def test_add_relationship_nonexistent_target(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        result = graph_manager.add_relationship("e1", "nonexistent", "TRACKS")
        assert result is False

    def test_get_all_relations(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        graph_manager.add_relationship("e1", "e2", "TRACKS", {"confidence": 0.9})
        relations = graph_manager.get_all_relations()
        assert len(relations) == 1
        assert relations[0]["source"] == "e1"
        assert relations[0]["target"] == "e2"
        assert relations[0]["type"] == "TRACKS"

    def test_get_all_relations_empty(self, graph_manager):
        relations = graph_manager.get_all_relations()
        assert relations == []

    def test_get_all_relations_with_properties(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        graph_manager.add_relationship("e1", "e2", "TRACKS", {"confidence": 0.9})
        relations = graph_manager.get_all_relations()
        assert "confidence" in relations[0]["properties"]


class TestGetEntity:
    def test_get_entity_existing(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1", "status": "active"})
        entity = graph_manager.get_entity("e1")
        assert entity is not None
        assert entity["id"] == "e1"
        assert entity["type"] == "Radar"
        assert entity["properties"]["name"] == "雷达1"

    def test_get_entity_nonexistent(self, graph_manager):
        entity = graph_manager.get_entity("nonexistent")
        assert entity is None

    def test_get_entity_excludes_entity_type_from_properties(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        entity = graph_manager.get_entity("e1")
        assert "entity_type" not in entity["properties"]


class TestGetEntityRelations:
    def test_get_entity_relations_outgoing(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        graph_manager.add_relationship("e1", "e2", "TRACKS")
        relations = graph_manager.get_entity_relations("e1")
        assert len(relations) >= 1
        assert any(r["target"] == "e2" and r["direction"] == "out" for r in relations)

    def test_get_entity_relations_incoming(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        graph_manager.add_relationship("e1", "e2", "TRACKS")
        relations = graph_manager.get_entity_relations("e2")
        assert len(relations) >= 1
        assert any(r["target"] == "e1" and r["direction"] == "in" for r in relations)

    def test_get_entity_relations_no_relations(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        relations = graph_manager.get_entity_relations("e1")
        assert relations == []

    def test_get_entity_relations_bidirectional(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        graph_manager.add_entity("e3", "Unit", {"name": "单位1"})
        graph_manager.add_relationship("e1", "e2", "TRACKS")
        graph_manager.add_relationship("e3", "e1", "DEPLOYS")
        relations = graph_manager.get_entity_relations("e1")
        assert len(relations) == 2
        directions = {r["direction"] for r in relations}
        assert "in" in directions
        assert "out" in directions


class TestGetStatistics:
    def test_get_statistics_empty(self, graph_manager):
        stats = graph_manager.get_statistics()
        assert stats["total_entities"] == 0
        assert stats["total_relationships"] == 0
        assert stats["mode"] == "fallback"

    def test_get_statistics_with_data(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1"})
        graph_manager.add_relationship("e1", "e2", "TRACKS")
        stats = graph_manager.get_statistics()
        assert stats["total_entities"] == 2
        assert stats["total_relationships"] == 1
        assert "entity_types" in stats

    def test_get_statistics_entity_types(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1"})
        graph_manager.add_entity("e2", "Radar", {"name": "雷达2"})
        graph_manager.add_entity("e3", "Target", {"name": "目标1"})
        stats = graph_manager.get_statistics()
        assert stats["entity_types"]["Radar"] == 2
        assert stats["entity_types"]["Target"] == 1

    def test_get_graph_statistics_alias(self, graph_manager):
        stats1 = graph_manager.get_statistics()
        stats2 = graph_manager.get_graph_statistics()
        assert stats1 == stats2


class TestWorkspaceFiltering:
    def test_query_entities_by_workspace(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1", "workspace_id": "ws1"})
        graph_manager.add_entity("e2", "Radar", {"name": "雷达2", "workspace_id": "ws2"})
        result = graph_manager.query_entities(workspace_id="ws1")
        assert len(result) == 1
        assert result[0]["id"] == "e1"

    def test_query_entities_no_workspace_filter(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1", "workspace_id": "ws1"})
        graph_manager.add_entity("e2", "Radar", {"name": "雷达2", "workspace_id": "ws2"})
        result = graph_manager.query_entities()
        assert len(result) == 2

    def test_get_all_entities_by_workspace(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1", "workspace_id": "ws1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1", "workspace_id": "ws2"})
        result = graph_manager.get_all_entities(workspace_id="ws1")
        assert len(result) == 1

    def test_get_all_relations_by_workspace(self, graph_manager):
        graph_manager.add_entity("e1", "Radar", {"name": "雷达1", "workspace_id": "ws1"})
        graph_manager.add_entity("e2", "Target", {"name": "目标1", "workspace_id": "ws1"})
        graph_manager.add_entity("e3", "Unit", {"name": "单位1", "workspace_id": "ws2"})
        graph_manager.add_relationship("e1", "e2", "TRACKS")
        graph_manager.add_relationship("e3", "e2", "SUPPORTS")
        relations = graph_manager.get_all_relations(workspace_id="ws1")
        assert len(relations) == 1
        assert relations[0]["source"] == "e1"
        assert relations[0]["target"] == "e2"


class TestReservedTasks:
    def test_reserve_task(self, graph_manager):
        task_id = graph_manager.reserve_task({"action": "deploy", "target": "unit-1"})
        assert task_id.startswith("TASK-")
        assert len(graph_manager.reserved_tasks) == 1

    def test_reserve_task_sets_status(self, graph_manager):
        task_id = graph_manager.reserve_task({"action": "deploy"})
        task = graph_manager.reserved_tasks[0]
        assert task["status"] == "reserved"
        assert task["id"] == task_id
        assert "created_at" in task

    def test_reserve_multiple_tasks(self, graph_manager):
        graph_manager.reserve_task({"action": "deploy"})
        graph_manager.reserve_task({"action": "retreat"})
        assert len(graph_manager.reserved_tasks) == 2

    def test_get_reserved_tasks(self, graph_manager):
        graph_manager.reserve_task({"action": "deploy"})
        graph_manager.reserve_task({"action": "retreat"})
        tasks = graph_manager.get_reserved_tasks()
        assert len(tasks) == 2
        assert isinstance(tasks, list)

    def test_get_reserved_tasks_returns_copy(self, graph_manager):
        graph_manager.reserve_task({"action": "deploy"})
        tasks = graph_manager.get_reserved_tasks()
        tasks.clear()
        assert len(graph_manager.reserved_tasks) == 1

    def test_clear_reserved_tasks(self, graph_manager):
        graph_manager.reserve_task({"action": "deploy"})
        graph_manager.reserve_task({"action": "retreat"})
        graph_manager.clear_reserved_tasks()
        assert len(graph_manager.reserved_tasks) == 0

    def test_clear_reserved_tasks_empty(self, graph_manager):
        graph_manager.clear_reserved_tasks()
        assert len(graph_manager.reserved_tasks) == 0


class TestSanitizeNeo4jProperties:
    def test_primitives_preserved(self):
        props = {"name": "test", "count": 5, "score": 0.9, "active": True}
        result = GraphManager._sanitize_neo4j_properties(props)
        assert result == props

    def test_none_values_removed(self):
        props = {"name": "test", "value": None}
        result = GraphManager._sanitize_neo4j_properties(props)
        assert "name" in result
        assert "value" not in result

    def test_list_values_preserved(self):
        props = {"tags": ["radar", "signal"]}
        result = GraphManager._sanitize_neo4j_properties(props)
        assert result["tags"] == ["radar", "signal"]

    def test_list_with_non_primitives(self):
        props = {"items": ["valid", 42, {"nested": True}]}
        result = GraphManager._sanitize_neo4j_properties(props)
        assert "valid" in result["items"]
        assert 42 in result["items"]
        assert any(isinstance(v, str) and "nested" in v for v in result["items"])

    def test_dict_values_flattened(self):
        props = {"location": {"lat": 30.0, "lng": 120.0}}
        result = GraphManager._sanitize_neo4j_properties(props)
        assert "location_lat" in result
        assert "location_lng" in result
        assert result["location_lat"] == 30.0
        assert result["location_lng"] == 120.0

    def test_dict_with_none_subvalue(self):
        props = {"config": {"enabled": True, "disabled": None}}
        result = GraphManager._sanitize_neo4j_properties(props)
        assert "config_enabled" in result
        assert "config_disabled" not in result

    def test_other_types_converted_to_string(self):
        props = {"data": object()}
        result = GraphManager._sanitize_neo4j_properties(props)
        assert isinstance(result["data"], str)

    def test_empty_dict(self):
        result = GraphManager._sanitize_neo4j_properties({})
        assert result == {}

    def test_empty_list_preserved(self):
        props = {"empty_list": []}
        result = GraphManager._sanitize_neo4j_properties(props)
        assert "empty_list" not in result

    def test_tuple_converted_to_list(self):
        props = {"coords": (1, 2, 3)}
        result = GraphManager._sanitize_neo4j_properties(props)
        assert result["coords"] == [1, 2, 3]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
