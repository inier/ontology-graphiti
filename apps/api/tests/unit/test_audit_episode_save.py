"""ADR-074 Iter 1.1: 验证 save_audit_episode 零 LLM 调用。

测试目标：
1. save_audit_episode 使用 EpisodicNode.save（零 LLM），不调用 add_episode
2. DualChannelWriter Channel B 使用 save_audit_episode
3. Channel B 失败不影响 Channel A
"""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.infra.graph.graph_service import GraphManager
from odap.biz.data.hyper_extract.impl.dual_channel_writer import DualChannelWriter


@pytest.fixture(autouse=True)
def reset_graph_manager_singleton():
    GraphManager._test_mode = True
    yield
    GraphManager._instance = None
    GraphManager._initialized = False
    GraphManager._test_mode = False


@pytest.fixture
def connected_graph_manager():
    """模拟已连接 Graphiti 的 GraphManager（不触发真实 LLM）。"""
    with patch.object(GraphManager, '_connect'):
        gm = GraphManager.__new__(GraphManager)
        gm.graph = MagicMock()
        gm.graph.driver = MagicMock()
        gm.neo4j_uri = "bolt://localhost:7687"
        gm.neo4j_user = "neo4j"
        gm.neo4j_password = "test"
        gm.neo4j_driver = None
        gm.fallback_graph = None
        gm.reserved_tasks = []
        gm._connected = True
        gm._use_fallback = False
        gm._mode = "graphiti"
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
        GraphManager._instance = gm
        GraphManager._initialized = True
        return gm


class TestSaveAuditEpisodeZeroLLM:
    """验证 save_audit_episode 零 LLM 调用。"""

    @pytest.mark.asyncio
    @patch('odap.infra.graph.graph_service.GRAPHITI_AVAILABLE', True)
    @patch('odap.infra.graph.graph_service.graph_audit')
    @patch('odap.infra.graph.graph_service.EpisodicNode')
    @patch('odap.infra.graph.graph_service.EpisodeType')
    async def test_uses_episodic_node_save_not_add_episode(
        self, mock_episode_type, mock_episodic_node, mock_graph_audit, connected_graph_manager
    ):
        """save_audit_episode 应调用 EpisodicNode.save，而非 add_episode（零 LLM）。"""
        mock_episode_instance = MagicMock()
        mock_episode_instance.save = AsyncMock()
        mock_episode_instance.name = "audit:extraction_completed"
        mock_episode_instance.content = "{}"
        mock_episodic_node.return_value = mock_episode_instance

        audit_data = {
            "event_type": "extraction_completed",
            "entities_written": 5,
            "relations_written": 3,
            "workspace_id": "ws1",
        }

        result = await connected_graph_manager.save_audit_episode(
            audit_data=audit_data,
            valid_at=datetime.now(timezone.utc),
        )

        assert result is True
        mock_episodic_node.assert_called_once()
        mock_episode_instance.save.assert_called_once()
        # 关键验证：add_episode 未被调用（零 LLM）
        connected_graph_manager.graph.add_episode.assert_not_called()

    @pytest.mark.asyncio
    @patch('odap.infra.graph.graph_service.GRAPHITI_AVAILABLE', False)
    @patch('odap.infra.graph.graph_service.graph_audit')
    async def test_returns_false_when_graphiti_unavailable(
        self, mock_graph_audit, connected_graph_manager
    ):
        """Graphiti 不可用时返回 False，不抛异常。"""
        result = await connected_graph_manager.save_audit_episode(
            audit_data={"event_type": "test"},
        )
        assert result is False

    @pytest.mark.asyncio
    @patch('odap.infra.graph.graph_service.GRAPHITI_AVAILABLE', True)
    @patch('odap.infra.graph.graph_service.graph_audit')
    @patch('odap.infra.graph.graph_service.EpisodicNode')
    @patch('odap.infra.graph.graph_service.EpisodeType')
    async def test_returns_false_when_not_connected(
        self, mock_episode_type, mock_episodic_node, mock_graph_audit, connected_graph_manager
    ):
        """图数据库未连接时返回 False。"""
        connected_graph_manager._connected = False

        result = await connected_graph_manager.save_audit_episode(
            audit_data={"event_type": "test"},
        )
        assert result is False
        mock_episodic_node.assert_not_called()

    @pytest.mark.asyncio
    @patch('odap.infra.graph.graph_service.GRAPHITI_AVAILABLE', True)
    @patch('odap.infra.graph.graph_service.graph_audit')
    @patch('odap.infra.graph.graph_service.EpisodicNode')
    @patch('odap.infra.graph.graph_service.EpisodeType')
    async def test_handles_save_failure_gracefully(
        self, mock_episode_type, mock_episodic_node, mock_graph_audit, connected_graph_manager
    ):
        """EpisodicNode.save 失败时返回 False，不抛异常。"""
        mock_episode_instance = MagicMock()
        mock_episode_instance.save = AsyncMock(side_effect=Exception("DB error"))
        mock_episodic_node.return_value = mock_episode_instance

        result = await connected_graph_manager.save_audit_episode(
            audit_data={"event_type": "test"},
        )
        assert result is False


class TestDualChannelWriterChannelB:
    """验证 DualChannelWriter Channel B 使用 save_audit_episode。"""

    @pytest.mark.asyncio
    async def test_channel_b_uses_save_audit_episode_not_add_episode(self):
        """Channel B 应调用 save_audit_episode，不调用 add_episode。"""
        writer = DualChannelWriter()

        mock_proxy = MagicMock()
        mock_proxy.add_entity.return_value = {"status": "success"}
        mock_proxy.add_relationship.return_value = {"status": "success"}
        writer._write_proxy = mock_proxy

        mock_gm = MagicMock()
        mock_gm.save_audit_episode = AsyncMock(return_value=True)
        mock_gm.add_episode = AsyncMock(return_value=True)
        writer._graph_manager = mock_gm

        doc = {
            "entities": [{"entity_id": "e1", "entity_type": "Person", "name": "Alice"}],
            "relations": [{"source": "e1", "target": "e2", "relation_type": "knows"}],
        }

        result = await writer.write(doc, workspace_id="ws1")

        assert result["status"] == "ok"
        assert result["entities_written"] == 1
        assert result["relations_written"] == 1
        mock_gm.save_audit_episode.assert_called_once()
        # 关键验证：add_episode 未被调用（零 LLM）
        mock_gm.add_episode.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_b_failure_does_not_affect_channel_a(self):
        """Channel B 失败不影响 Channel A 结果。"""
        writer = DualChannelWriter()

        mock_proxy = MagicMock()
        mock_proxy.add_entity.return_value = {"status": "success"}
        mock_proxy.add_relationship.return_value = {"status": "success"}
        writer._write_proxy = mock_proxy

        mock_gm = MagicMock()
        mock_gm.save_audit_episode = AsyncMock(side_effect=Exception("Connection failed"))
        writer._graph_manager = mock_gm

        doc = {
            "entities": [{"entity_id": "e1", "entity_type": "Person", "name": "Alice"}],
            "relations": [],
        }

        result = await writer.write(doc, workspace_id="ws1")

        assert result["status"] == "ok"
        assert result["entities_written"] == 1

    @pytest.mark.asyncio
    async def test_build_audit_event_structure(self):
        """_build_audit_event 产出正确的审计事件结构。"""
        writer = DualChannelWriter()
        doc = {"entities": [{"e": 1}, {"e": 2}], "relations": [{"r": 1}]}
        valid_time = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)

        event = writer._build_audit_event(doc, 2, 1, valid_time, "ws1")

        assert event["event_type"] == "extraction_completed"
        assert event["workspace_id"] == "ws1"
        assert event["entities_total"] == 2
        assert event["relations_total"] == 1
        assert event["entities_written"] == 2
        assert event["relations_written"] == 1
        assert event["valid_time"] == "2026-08-04T12:00:00+00:00"
        assert "recorded_at" in event
