"""
MCP Adapter 集成测试
T293: 验证 MCP 服务器注册/连接/工具发现/工具调用/连接池/状态查询的完整集成流程
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

pytestmark = pytest.mark.integration


@pytest.fixture
def mcp_service():
    from odap.biz.integration.mcp_adapter.services.mcp_service import MCPService
    return MCPService()


@pytest.fixture
def server_manager():
    from odap.biz.integration.mcp_adapter.impl.server_manager import ToolServerManager
    return ToolServerManager()


@pytest.fixture
def pool_manager():
    from odap.biz.integration.mcp_adapter.impl.connection_pool import ConnectionPoolManager
    return ConnectionPoolManager()


class TestMCPServerRegistrationIntegration:
    """MCP 服务器注册集成测试"""

    def test_register_and_list_servers(self, mcp_service):
        result = mcp_service.register_server(
            name="test-mcp-server",
            url="http://localhost:9001",
            description="Integration test server"
        )
        assert "server_id" in result
        assert result["name"] == "test-mcp-server"
        assert result["url"] == "http://localhost:9001"

        servers = mcp_service.list_servers()
        assert len(servers) >= 1
        found = [s for s in servers if s["name"] == "test-mcp-server"]
        assert len(found) == 1

    def test_register_duplicate_server(self, mcp_service):
        r1 = mcp_service.register_server("dup-server", "http://localhost:9002")
        assert "server_id" in r1
        r2 = mcp_service.register_server("dup-server", "http://localhost:9003")
        assert "server_id" in r2
        assert r1["server_id"] != r2["server_id"]

    def test_unregister_server(self, mcp_service):
        reg = mcp_service.register_server("temp-server", "http://localhost:9004")
        server_id = reg["server_id"]

        result = mcp_service.unregister_server(server_id)
        assert result["status"] == "success"

        result2 = mcp_service.unregister_server("nonexistent-id")
        assert result2["status"] == "error"

    def test_list_servers_by_status(self, mcp_service):
        mcp_service.register_server("status-server-a", "http://localhost:9005")
        mcp_service.register_server("status-server-b", "http://localhost:9006")

        disconnected = mcp_service.list_servers(status="disconnected")
        assert all(s["status"] == "disconnected" for s in disconnected)


class TestMCPServerConnectionIntegration:
    """MCP 服务器连接集成测试"""

    def test_connect_server(self, mcp_service):
        reg = mcp_service.register_server("conn-server", "http://localhost:9010")
        server_id = reg["server_id"]

        result = mcp_service.connect_server(server_id)
        assert result["status"] == "success"

        status = mcp_service.get_server_status(server_id)
        assert status["status"] == "connected"

    def test_disconnect_server(self, mcp_service):
        reg = mcp_service.register_server("disconn-server", "http://localhost:9011")
        server_id = reg["server_id"]

        mcp_service.connect_server(server_id)
        result = mcp_service.disconnect_server(server_id)
        assert result["status"] == "success"

        status = mcp_service.get_server_status(server_id)
        assert status["status"] == "disconnected"

    def test_connect_nonexistent_server(self, mcp_service):
        result = mcp_service.connect_server("nonexistent-id")
        assert result["status"] == "error"

    def test_server_status_lifecycle(self, mcp_service):
        reg = mcp_service.register_server("lifecycle-server", "http://localhost:9012")
        server_id = reg["server_id"]

        status1 = mcp_service.get_server_status(server_id)
        assert status1["status"] == "disconnected"

        mcp_service.connect_server(server_id)
        status2 = mcp_service.get_server_status(server_id)
        assert status2["status"] == "connected"

        mcp_service.disconnect_server(server_id)
        status3 = mcp_service.get_server_status(server_id)
        assert status3["status"] == "disconnected"


class TestMCPToolDiscoveryIntegration:
    """MCP 工具发现集成测试"""

    def test_discover_tools(self, mcp_service):
        reg = mcp_service.register_server("tool-server", "http://localhost:9020")
        server_id = reg["server_id"]

        tools = mcp_service.discover_tools(server_id)
        assert isinstance(tools, list)
        assert len(tools) > 0
        for tool in tools:
            assert "name" in tool
            assert "description" in tool

    def test_discover_tools_nonexistent_server(self, mcp_service):
        tools = mcp_service.discover_tools("nonexistent-id")
        assert tools == []


class TestMCPToolCallIntegration:
    """MCP 工具调用集成测试（V1 降级路径）"""

    @pytest.mark.asyncio
    async def test_call_tool_v1_fallback(self, mcp_service):
        reg = mcp_service.register_server("call-server", "http://localhost:9030")
        server_id = reg["server_id"]
        mcp_service.connect_server(server_id)

        with patch.object(mcp_service, "_get_v2_manager", return_value=None):
            result = await mcp_service.call_tool(
                server_id=server_id,
                tool_name="test_tool",
                arguments={"key": "value"}
            )
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_call_tool_disconnected_server(self, mcp_service):
        reg = mcp_service.register_server("disconn-call-server", "http://localhost:9031")
        server_id = reg["server_id"]

        result = await mcp_service.call_tool(
            server_id=server_id,
            tool_name="test_tool",
            arguments={}
        )
        assert result.get("status") == "error" or result.get("success") is False


class TestMCPConnectionPoolIntegration:
    """MCP 连接池集成测试"""

    def test_create_pool_on_register(self, mcp_service):
        reg = mcp_service.register_server("pool-server", "http://localhost:9040")
        server_id = reg["server_id"]

        pool_status = mcp_service.get_pool_status(server_id)
        assert pool_status is not None
        assert "max_connections" in pool_status
        assert "current_connections" in pool_status

    def test_acquire_and_release_connection(self, mcp_service):
        reg = mcp_service.register_server("acquire-server", "http://localhost:9041")
        server_id = reg["server_id"]

        conn = mcp_service.acquire_connection(server_id)
        assert conn["status"] == "acquired"
        connection_id = conn["connection_id"]

        release = mcp_service.release_connection(connection_id)
        assert release["status"] == "success"

    def test_pool_status_nonexistent_server(self, mcp_service):
        result = mcp_service.get_pool_status("nonexistent-id")
        assert result.get("status") in ("error", "not_found")


class TestMCPServerManagerIntegration:
    """ToolServerManager 实现层集成测试"""

    def test_register_and_get_server(self, server_manager):
        server = server_manager.register_server(
            name="impl-server",
            url="http://localhost:9050",
            description="Impl test"
        )
        assert server is not None
        assert server.name == "impl-server"

        fetched = server_manager.get_server(server.id)
        assert fetched is not None
        assert fetched.id == server.id

    def test_connect_and_disconnect(self, server_manager):
        server = server_manager.register_server("impl-conn", "http://localhost:9051")
        server_manager.connect_server(server.id)
        assert server.status.value == "connected"

        server_manager.disconnect_server(server.id)
        assert server.status.value == "disconnected"

    def test_list_servers_with_filter(self, server_manager):
        server_manager.register_server("filter-a", "http://localhost:9052")
        s2 = server_manager.register_server("filter-b", "http://localhost:9053")
        server_manager.connect_server(s2.id)

        all_servers = server_manager.list_servers()
        assert len(all_servers) >= 2

        connected = server_manager.list_servers(filters={"status": "connected"})
        assert all(s.status.value == "connected" for s in connected)

    def test_discover_tools_returns_list(self, server_manager):
        server = server_manager.register_server("tool-impl", "http://localhost:9054")
        tools = server_manager.discover_tools(server.id)
        assert isinstance(tools, list)
        assert len(tools) > 0


class TestMCPConnectionPoolManagerIntegration:
    """ConnectionPoolManager 实现层集成测试"""

    def test_create_pool(self, pool_manager):
        pool = pool_manager.create_pool("server-1", max_connections=5, min_connections=1)
        assert pool is not None
        assert pool.max_connections == 5

    def test_acquire_and_release(self, pool_manager):
        pool_manager.create_pool("server-2", max_connections=3, min_connections=1)

        conn_id = pool_manager.acquire("server-2")
        assert conn_id is not None

        pool_manager.release(conn_id)
        status = pool_manager.get_pool_status("server-2")
        assert status["acquired_connections"] == 0

    def test_pool_max_connections_limit(self, pool_manager):
        pool_manager.create_pool("server-3", max_connections=2, min_connections=1)

        c1 = pool_manager.acquire("server-3")
        c2 = pool_manager.acquire("server-3")
        c3 = pool_manager.acquire("server-3")
        assert c1 is not None
        assert c2 is not None
        assert c3 is None


class TestMCPEndToEndWorkflow:
    """MCP 端到端工作流集成测试"""

    def test_full_server_lifecycle(self, mcp_service):
        reg = mcp_service.register_server("e2e-server", "http://localhost:9060", "E2E test")
        server_id = reg["server_id"]

        mcp_service.connect_server(server_id)
        status = mcp_service.get_server_status(server_id)
        assert status["status"] == "connected"

        tools = mcp_service.discover_tools(server_id)
        assert len(tools) > 0

        pool = mcp_service.get_pool_status(server_id)
        assert pool is not None

        mcp_service.disconnect_server(server_id)
        status2 = mcp_service.get_server_status(server_id)
        assert status2["status"] == "disconnected"

        mcp_service.unregister_server(server_id)
        status3 = mcp_service.get_server_status(server_id)
        assert status3["status"] == "error"

    @pytest.mark.asyncio
    async def test_register_connect_call_disconnect(self, mcp_service):
        reg = mcp_service.register_server("workflow-server", "http://localhost:9070")
        server_id = reg["server_id"]

        mcp_service.connect_server(server_id)

        with patch.object(mcp_service, "_get_v2_manager", return_value=None):
            result = await mcp_service.call_tool(
                server_id=server_id,
                tool_name="query",
                arguments={"q": "test"}
            )
            assert result["status"] == "success"

        mcp_service.disconnect_server(server_id)
        final_status = mcp_service.get_server_status(server_id)
        assert final_status["status"] == "disconnected"
