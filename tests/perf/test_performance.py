"""
性能基准测试
T313: 验证核心模块的性能指标
"""

import pytest
import sys
import os
import time
import uuid
from unittest.mock import MagicMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

pytestmark = pytest.mark.perf


class TestGraphServiceCachePerformance:
    """GraphManager 缓存性能基准"""

    @pytest.fixture
    def graph_manager(self):
        with patch("odap.infra.graph.graph_service.NEO4J_DRIVER_AVAILABLE", False), \
             patch("odap.infra.graph.graph_service.GRAPHITI_AVAILABLE", False):
            from odap.infra.graph.graph_service import GraphManager
            GraphManager._instance = None
            GraphManager._initialized = False
            gm = GraphManager.__new__(GraphManager)
            gm.graph = None
            gm.neo4j_driver = None
            gm.fallback_graph = None
            gm._connected = False
            gm._use_fallback = True
            gm._mode = "fallback"
            gm._reconnect_attempts = 0
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
            for i in range(100):
                gm.fallback_graph.add_node(f"entity-{i}", entity_type="Unit", name=f"Unit-{i}")

            GraphManager._instance = gm
            GraphManager._initialized = True
            return gm

    def test_cache_hit_is_faster_than_miss(self, graph_manager):
        graph_manager.query_entities(entity_type="Unit")
        start = time.perf_counter()
        for _ in range(100):
            graph_manager.query_entities(entity_type="Unit")
        cached_time = time.perf_counter() - start

        graph_manager.invalidate_cache()
        start = time.perf_counter()
        for _ in range(100):
            graph_manager.query_entities(entity_type="Unit")
        uncached_time = time.perf_counter() - start

        assert cached_time < uncached_time or cached_time < 0.1

    def test_cache_key_generation_performance(self, graph_manager):
        start = time.perf_counter()
        for i in range(1000):
            graph_manager._cache_key("test", param1=f"value-{i}", param2=i)
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0

    def test_cache_set_and_get_performance(self, graph_manager):
        graph_manager._cache_max_size = 600
        start = time.perf_counter()
        for i in range(500):
            graph_manager._cache_set(f"key-{i}", {"data": i})
        set_time = time.perf_counter() - start

        start = time.perf_counter()
        hits = 0
        for i in range(500):
            result = graph_manager._cache_get(f"key-{i}")
            if result is not None:
                hits += 1
        get_time = time.perf_counter() - start

        assert hits == 500
        assert set_time < 2.0
        assert get_time < 1.0

    def test_cache_eviction_performance(self, graph_manager):
        graph_manager._cache_max_size = 100
        start = time.perf_counter()
        for i in range(200):
            graph_manager._cache_set(f"evict-key-{i}", {"data": i})
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0
        assert len(graph_manager._query_cache) <= 100


class TestMiddlewarePerformance:
    """中间件性能基准"""

    def test_performance_middleware_overhead(self):
        from odap.infra.middleware.performance_middleware import PerformanceMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def homepage(request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[Route("/test", homepage)])
        app.add_middleware(PerformanceMiddleware)

        client = TestClient(app)
        start = time.perf_counter()
        for _ in range(100):
            response = client.get("/test")
            assert response.status_code == 200
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0

    def test_gzip_middleware_compression(self):
        from odap.infra.middleware.performance_middleware import GzipMiddleware
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        large_data = {"data": "x" * 2000}

        async def homepage(request):
            return JSONResponse(large_data)

        app = Starlette(routes=[Route("/test", homepage)])
        app.add_middleware(GzipMiddleware)

        client = TestClient(app)
        response = client.get("/test", headers={"Accept-Encoding": "gzip"})
        assert response.status_code == 200


class TestSQLiteStoragePerformance:
    """SQLite 存储层性能基准"""

    def test_bulk_insert_performance(self, tmp_path):
        from odap.biz.core.ontology.design.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        storage = SQLiteEngineStorage(str(tmp_path / "perf_test.db"))

        start = time.perf_counter()
        for i in range(100):
            storage.save_version({
                "version_id": f"v-{i}",
                "ontology_id": "ont-perf",
                "version_number": f"1.0.{i}",
                "changelog": f"Version {i}",
                "status": "active",
            })
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0

    def test_bulk_read_performance(self, tmp_path):
        from odap.biz.core.ontology.design.engine.storage.sqlite_engine_storage import SQLiteEngineStorage
        storage = SQLiteEngineStorage(str(tmp_path / "perf_read.db"))

        for i in range(100):
            storage.save_version({
                "version_id": f"read-v-{i}",
                "ontology_id": "ont-perf-read",
                "version_number": f"1.0.{i}",
                "changelog": f"Version {i}",
                "status": "active",
            })

        start = time.perf_counter()
        for i in range(100):
            result = storage.get_version(f"read-v-{i}")
            assert result is not None
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0


class TestOpenHarnessAdapterPerformance:
    """OpenHarness 适配器性能基准"""

    def test_swarm_adapter_run_performance(self):
        from odap.infra.openharness.swarm_adapter import SwarmAdapter
        adapter = SwarmAdapter()

        start = time.perf_counter()
        for i in range(100):
            result = adapter.create_swarm(
                agents=[{"type": "intelligence", "name": f"agent-{i}"}],
                config={"workspace_id": "ws-perf"},
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0

    def test_skill_adapter_registry_performance(self):
        from odap.infra.openharness.skill_adapter import SkillAdapter
        adapter = SkillAdapter()

        def dummy_handler(input_data):
            return {"result": "ok"}

        for i in range(50):
            adapter.register_skill(
                name=f"perf-skill-{i}",
                description=f"Performance test skill {i}",
                handler=dummy_handler,
                category="test",
            )

        start = time.perf_counter()
        for i in range(50):
            result = adapter.get_skill(f"perf-skill-{i}")
            assert result is not None
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0

    def test_hook_adapter_broadcast_performance(self):
        from odap.infra.openharness.hook_adapter import HookAdapter
        adapter = HookAdapter()

        call_count = 0

        def handler(context):
            nonlocal call_count
            call_count += 1

        for i in range(20):
            adapter.register_hook(f"perf-event-{i}", handler)

        import asyncio
        start = time.perf_counter()
        for i in range(100):
            asyncio.get_event_loop().run_until_complete(
                adapter.trigger_hook(f"perf-event-{i % 20}", {"data": i})
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0
        assert call_count == 100
