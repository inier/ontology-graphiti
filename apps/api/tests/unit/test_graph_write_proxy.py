"""
GraphWriteProxy 单元测试

覆盖:
- 单例模式
- get_graph_write_proxy() 返回同一实例
- 方法返回 Dict[str, Any] 格式
- GraphManager 不可用时的错误处理
- 审计日志行为
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_proxy_singleton():
    """每个测试前重置 GraphWriteProxy 单例"""
    try:
        from odap.infra.query.graph_write_proxy import GraphWriteProxy
        GraphWriteProxy._instance = None
    except Exception:
        pass
    # 重置模块级单例
    try:
        import odap.infra.query.graph_write_proxy as gwp_mod
        gwp_mod._write_proxy_instance = None
    except Exception:
        pass
    yield
    try:
        from odap.infra.query.graph_write_proxy import GraphWriteProxy
        GraphWriteProxy._instance = None
    except Exception:
        pass
    try:
        import odap.infra.query.graph_write_proxy as gwp_mod
        gwp_mod._write_proxy_instance = None
    except Exception:
        pass


@pytest.fixture
def proxy():
    """创建 GraphWriteProxy 实例"""
    from odap.infra.query.graph_write_proxy import GraphWriteProxy
    return GraphWriteProxy()


@pytest.fixture
def proxy_with_mock_gm(proxy):
    """创建带 mock GraphManager 的 GraphWriteProxy"""
    mock_gm = MagicMock()
    mock_gm.add_entity.return_value = True
    mock_gm.update_entity.return_value = True
    mock_gm.delete_entity.return_value = True
    mock_gm.add_relationship.return_value = True
    mock_gm.add_episode = AsyncMock(return_value=True)
    mock_gm.add_episodes_batch.return_value = {"success": 3, "failed": 0}
    mock_gm.initialize_graph.return_value = None
    mock_gm.clear_graph.return_value = {"cleared": True}
    proxy._graph_manager = mock_gm
    return proxy, mock_gm


# ---------------------------------------------------------------------------
# TestSingleton — 单例模式
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_same_instance(self):
        """多次创建应返回同一实例"""
        from odap.infra.query.graph_write_proxy import GraphWriteProxy
        a = GraphWriteProxy()
        b = GraphWriteProxy()
        assert a is b

    def test_get_graph_write_proxy_returns_same(self):
        """get_graph_write_proxy() 应返回同一实例"""
        from odap.infra.query.graph_write_proxy import get_graph_write_proxy
        a = get_graph_write_proxy()
        b = get_graph_write_proxy()
        assert a is b

    def test_get_graph_write_proxy_returns_proxy_type(self):
        """get_graph_write_proxy() 应返回 GraphWriteProxy 类型"""
        from odap.infra.query.graph_write_proxy import get_graph_write_proxy, GraphWriteProxy
        instance = get_graph_write_proxy()
        assert isinstance(instance, GraphWriteProxy)


# ---------------------------------------------------------------------------
# TestAddEntity — 添加实体
# ---------------------------------------------------------------------------

class TestAddEntity:
    def test_success(self, proxy_with_mock_gm):
        """成功添加实体"""
        proxy, mock_gm = proxy_with_mock_gm
        result = proxy.add_entity(
            entity_id="e1",
            entity_type="Agent",
            properties={"name": "test"},
            workspace_id="ws1",
        )
        assert result["status"] == "success"
        assert result["entity_id"] == "e1"
        assert result["entity_type"] == "Agent"

    def test_graph_manager_returns_false(self, proxy_with_mock_gm):
        """GraphManager.add_entity 返回 False 时应返回 error"""
        proxy, mock_gm = proxy_with_mock_gm
        mock_gm.add_entity.return_value = False
        result = proxy.add_entity("e1", "Agent", {})
        assert result["status"] == "error"
        assert "False" in result["message"]

    def test_graph_manager_unavailable(self, proxy):
        """GraphManager 不可用时应返回 error"""
        proxy._graph_manager = None
        with patch.object(proxy, "_get_graph_manager", return_value=None):
            result = proxy.add_entity("e1", "Agent", {})
            assert result["status"] == "error"
            assert "unavailable" in result["message"]

    def test_graph_manager_exception(self, proxy_with_mock_gm):
        """GraphManager 抛异常时应返回 error"""
        proxy, mock_gm = proxy_with_mock_gm
        mock_gm.add_entity.side_effect = RuntimeError("DB error")
        result = proxy.add_entity("e1", "Agent", {})
        assert result["status"] == "error"
        assert "DB error" in result["message"]


# ---------------------------------------------------------------------------
# TestUpdateEntity — 更新实体
# ---------------------------------------------------------------------------

class TestUpdateEntity:
    def test_success(self, proxy_with_mock_gm):
        """成功更新实体"""
        proxy, mock_gm = proxy_with_mock_gm
        result = proxy.update_entity("e1", {"name": "updated"}, workspace_id="ws1")
        assert result["status"] == "success"
        assert result["entity_id"] == "e1"
        assert "name" in result["updated_keys"]

    def test_unavailable(self, proxy):
        """GraphManager 不可用"""
        proxy._graph_manager = None
        with patch.object(proxy, "_get_graph_manager", return_value=None):
            result = proxy.update_entity("e1", {"name": "x"})
            assert result["status"] == "error"


# ---------------------------------------------------------------------------
# TestDeleteEntity — 删除实体
# ---------------------------------------------------------------------------

class TestDeleteEntity:
    def test_success(self, proxy_with_mock_gm):
        """成功删除实体"""
        proxy, mock_gm = proxy_with_mock_gm
        result = proxy.delete_entity("e1", workspace_id="ws1")
        assert result["status"] == "success"
        assert result["entity_id"] == "e1"

    def test_unavailable(self, proxy):
        """GraphManager 不可用"""
        proxy._graph_manager = None
        with patch.object(proxy, "_get_graph_manager", return_value=None):
            result = proxy.delete_entity("e1")
            assert result["status"] == "error"


# ---------------------------------------------------------------------------
# TestAddRelationship — 添加关系
# ---------------------------------------------------------------------------

class TestAddRelationship:
    def test_success(self, proxy_with_mock_gm):
        """成功添加关系"""
        proxy, mock_gm = proxy_with_mock_gm
        result = proxy.add_relationship(
            source_id="e1",
            target_id="e2",
            relationship="depends_on",
            workspace_id="ws1",
        )
        assert result["status"] == "success"
        assert result["source_id"] == "e1"
        assert result["target_id"] == "e2"
        assert result["relationship"] == "depends_on"

    def test_unavailable(self, proxy):
        """GraphManager 不可用"""
        proxy._graph_manager = None
        with patch.object(proxy, "_get_graph_manager", return_value=None):
            result = proxy.add_relationship("e1", "e2", "rel")
            assert result["status"] == "error"


# ---------------------------------------------------------------------------
# TestAddEpisode — 添加 Episode
# ---------------------------------------------------------------------------

class TestAddEpisode:
    @pytest.mark.asyncio
    async def test_success(self, proxy_with_mock_gm):
        """成功添加 Episode"""
        proxy, mock_gm = proxy_with_mock_gm
        result = await proxy.add_episode(
            name="episode1",
            content="test content",
            source_description="test",
            workspace_id="ws1",
        )
        assert result["status"] == "success"
        assert result["name"] == "episode1"

    @pytest.mark.asyncio
    async def test_unavailable(self, proxy):
        """GraphManager 不可用"""
        proxy._graph_manager = None
        with patch.object(proxy, "_get_graph_manager", return_value=None):
            result = await proxy.add_episode("ep1", "content")
            assert result["status"] == "error"


# ---------------------------------------------------------------------------
# TestBatchAndInit — 批量操作与初始化
# ---------------------------------------------------------------------------

class TestBatchAndInit:
    def test_add_episodes_batch(self, proxy_with_mock_gm):
        """批量添加 Episode"""
        proxy, mock_gm = proxy_with_mock_gm
        result = proxy.add_episodes_batch(
            episodes=[{"name": "ep1", "content": "c1"}],
            workspace_id="ws1",
        )
        assert result["status"] == "success"

    def test_initialize_graph(self, proxy_with_mock_gm):
        """初始化图谱"""
        proxy, mock_gm = proxy_with_mock_gm
        result = proxy.initialize_graph(workspace_id="ws1")
        assert result["status"] == "success"

    def test_clear_graph(self, proxy_with_mock_gm):
        """清空图谱"""
        proxy, mock_gm = proxy_with_mock_gm
        result = proxy.clear_graph(workspace_id="ws1")
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# TestAuditLogging — 审计日志
# ---------------------------------------------------------------------------

class TestAuditLogging:
    def test_log_write_called_on_add_entity(self, proxy_with_mock_gm):
        """add_entity 应调用 _log_write"""
        proxy, mock_gm = proxy_with_mock_gm
        with patch.object(proxy, "_log_write") as mock_log:
            proxy.add_entity("e1", "Agent", {"name": "test"}, workspace_id="ws1")
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[0][0] == "add_entity"

    def test_log_write_includes_workspace_id(self, proxy_with_mock_gm):
        """审计日志应包含 workspace_id"""
        proxy, mock_gm = proxy_with_mock_gm
        with patch.object(proxy, "_log_write") as mock_log:
            proxy.add_entity("e1", "Agent", {}, workspace_id="ws_abc")
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args
            assert call_kwargs[1].get("workspace_id") == "ws_abc" or "ws_abc" in str(call_kwargs)


# ---------------------------------------------------------------------------
# TestIsConnected — 连接状态
# ---------------------------------------------------------------------------

class TestIsConnected:
    def test_not_connected_when_no_gm(self, proxy):
        """无 GraphManager 时 is_connected 返回 False"""
        proxy._graph_manager = None
        with patch.object(proxy, "_get_graph_manager", return_value=None):
            assert proxy.is_connected() is False

    def test_connected_when_gm_connected(self, proxy):
        """GraphManager 已连接时 is_connected 返回 True"""
        mock_gm = MagicMock()
        mock_gm._connected = True
        mock_gm._use_fallback = False
        proxy._graph_manager = mock_gm
        assert proxy.is_connected() is True

    def test_not_connected_when_using_fallback(self, proxy):
        """GraphManager 使用回退模式时 is_connected 返回 False"""
        mock_gm = MagicMock()
        mock_gm._connected = True
        mock_gm._use_fallback = True
        proxy._graph_manager = mock_gm
        assert proxy.is_connected() is False


# ---------------------------------------------------------------------------
# TestGetRawGraphManager — 获取原始 GraphManager (已移除)
# ---------------------------------------------------------------------------

class TestGetRawGraphManager:
    def test_raises_not_implemented_error(self, proxy_with_mock_gm):
        """get_raw_graph_manager 应抛出 NotImplementedError"""
        proxy, mock_gm = proxy_with_mock_gm
        with pytest.raises(NotImplementedError, match="has been removed"):
            proxy.get_raw_graph_manager()

    def test_raises_not_implemented_when_unavailable(self, proxy):
        """GraphManager 不可用时也应抛出 NotImplementedError"""
        proxy._graph_manager = None
        with pytest.raises(NotImplementedError, match="has been removed"):
            proxy.get_raw_graph_manager()
