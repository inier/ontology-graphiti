import pytest
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.mcp_adapter.mcp_service_v2 import (
    MCPServerManagerV2,
    MCPServer,
    ServerStatus,
    ServerCapability,
    ToolDefinition,
    ResourceDefinition,
    PromptDefinition,
    ServerHealthInfo,
    ConnectionPool,
    MCPServerDiscovery,
    MCPToolBridge,
)


class TestRegisterServer:
    @pytest.fixture
    def manager(self):
        return MCPServerManagerV2()

    @pytest.mark.asyncio
    async def test_register_server_basic(self, manager):
        server = await manager.register_server(
            name="test_server",
            url="http://localhost:8080",
            description="A test server"
        )
        assert server.name == "test_server"
        assert server.url == "http://localhost:8080"
        assert server.description == "A test server"
        assert server.status == ServerStatus.DISCONNECTED
        assert server.server_id in manager._servers

    @pytest.mark.asyncio
    async def test_register_server_with_capabilities(self, manager):
        server = await manager.register_server(
            name="cap_server",
            url="http://localhost:9090",
            capabilities=["tools", "resources"]
        )
        assert ServerCapability.TOOLS in server.capabilities
        assert ServerCapability.RESOURCES in server.capabilities

    @pytest.mark.asyncio
    async def test_register_server_default_capabilities(self, manager):
        server = await manager.register_server(
            name="default_cap",
            url="http://localhost:9091"
        )
        assert ServerCapability.TOOLS in server.capabilities

    @pytest.mark.asyncio
    async def test_register_server_invalid_capability_ignored(self, manager):
        server = await manager.register_server(
            name="invalid_cap",
            url="http://localhost:9092",
            capabilities=["tools", "nonexistent"]
        )
        assert len(server.capabilities) == 1
        assert ServerCapability.TOOLS in server.capabilities

    @pytest.mark.asyncio
    async def test_register_server_creates_connection_pool(self, manager):
        server = await manager.register_server(
            name="pool_server",
            url="http://localhost:9093"
        )
        assert server.server_id in manager._pools

    @pytest.mark.asyncio
    async def test_register_server_health_initialized(self, manager):
        server = await manager.register_server(
            name="health_server",
            url="http://localhost:9094"
        )
        assert server.health is not None
        assert server.health.status == ServerStatus.DISCONNECTED.value


class TestConnectServer:
    @pytest.fixture
    def manager(self):
        return MCPServerManagerV2()

    @pytest.mark.asyncio
    async def test_connect_nonexistent_server(self, manager):
        result = await manager.connect_server("nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_server_success(self, manager):
        server = await manager.register_server(
            name="connect_test",
            url="http://localhost:8080"
        )
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        with patch.object(manager, '_get_http_session', return_value=mock_session):
            result = await manager.connect_server(server.server_id)

        assert result is True
        assert server.status == ServerStatus.CONNECTED
        assert server.connected_at is not None

    @pytest.mark.asyncio
    async def test_connect_server_failure(self, manager):
        server = await manager.register_server(
            name="fail_connect",
            url="http://localhost:8080"
        )
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=Exception("Connection refused"))
        mock_session.closed = False

        with patch.object(manager, '_get_http_session', return_value=mock_session):
            result = await manager.connect_server(server.server_id)

        assert result is False
        assert server.status == ServerStatus.ERROR
        assert server.health.consecutive_failures == 1


class TestDisconnectServer:
    @pytest.fixture
    def manager(self):
        return MCPServerManagerV2()

    @pytest.mark.asyncio
    async def test_disconnect_existing_server(self, manager):
        server = await manager.register_server(
            name="disconnect_test",
            url="http://localhost:8080"
        )
        server.status = ServerStatus.CONNECTED
        result = await manager.disconnect_server(server.server_id)
        assert result is True
        assert server.status == ServerStatus.DISCONNECTED
        assert server.health.status == ServerStatus.DISCONNECTED.value

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_server(self, manager):
        result = await manager.disconnect_server("nonexistent-id")
        assert result is False


class TestListServers:
    @pytest.fixture
    def manager(self):
        return MCPServerManagerV2()

    @pytest.mark.asyncio
    async def test_list_all_servers(self, manager):
        await manager.register_server(name="s1", url="http://localhost:8081")
        await manager.register_server(name="s2", url="http://localhost:8082")
        servers = manager.list_servers()
        assert len(servers) == 2

    @pytest.mark.asyncio
    async def test_list_servers_filter_by_status(self, manager):
        s1 = await manager.register_server(name="s1", url="http://localhost:8081")
        s2 = await manager.register_server(name="s2", url="http://localhost:8082")
        s1.status = ServerStatus.CONNECTED
        s2.status = ServerStatus.DISCONNECTED
        connected = manager.list_servers(status="connected")
        assert len(connected) == 1
        assert connected[0].name == "s1"

    @pytest.mark.asyncio
    async def test_list_servers_empty(self, manager):
        servers = manager.list_servers()
        assert servers == []


class TestDiscoverTools:
    @pytest.fixture
    def manager(self):
        return MCPServerManagerV2()

    @pytest.mark.asyncio
    async def test_discover_capabilities_nonexistent(self, manager):
        result = await manager.discover_capabilities("nonexistent-id")
        assert result == {}

    @pytest.mark.asyncio
    async def test_discover_capabilities_success(self, manager):
        server = await manager.register_server(
            name="discover_test",
            url="http://localhost:8080",
            capabilities=["tools", "resources"]
        )
        cap_data = {
            "tools": [
                {"name": "tool1", "description": "Tool 1", "inputSchema": {}, "tags": ["tag1"]},
                {"name": "tool2", "description": "Tool 2", "inputSchema": {}}
            ],
            "resources": [
                {"uri": "res://1", "name": "Resource 1", "description": "Res desc", "mimeType": "text/plain"}
            ],
            "prompts": [
                {"name": "prompt1", "description": "Prompt 1", "arguments": []}
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=cap_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.closed = False

        with patch.object(manager, '_get_http_session', return_value=mock_session):
            result = await manager.discover_capabilities(server.server_id)

        assert result["tools"] == 2
        assert result["resources"] == 1
        assert result["prompts"] == 1
        assert len(server.tools) == 2
        assert len(server.resources) == 1
        assert len(server.prompts) == 1

    @pytest.mark.asyncio
    async def test_discover_capabilities_error(self, manager):
        server = await manager.register_server(
            name="discover_err",
            url="http://localhost:8080"
        )
        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=Exception("Network error"))
        mock_session.closed = False

        with patch.object(manager, '_get_http_session', return_value=mock_session):
            result = await manager.discover_capabilities(server.server_id)

        assert "error" in result


class TestConnectionPoolStatus:
    @pytest.fixture
    def manager(self):
        return MCPServerManagerV2()

    @pytest.mark.asyncio
    async def test_get_pool_status_existing(self, manager):
        server = await manager.register_server(
            name="pool_status",
            url="http://localhost:8080"
        )
        status = manager.get_pool_status(server.server_id)
        assert status is not None
        assert "available" in status
        assert "in_use" in status
        assert "total" in status
        assert "max_size" in status
        assert status["available"] >= 1

    def test_get_pool_status_nonexistent(self, manager):
        status = manager.get_pool_status("nonexistent-id")
        assert status is None


class TestConnectionPool:
    def test_acquire_and_release(self):
        pool = ConnectionPool("test-server", min_size=2, max_size=5)
        conn = pool.acquire(timeout_ms=100)
        assert conn is not None
        status = pool.get_status()
        assert status["in_use"] == 1
        assert status["available"] == 1
        released = pool.release(conn)
        assert released is True

    def test_acquire_timeout(self):
        pool = ConnectionPool("test-server", min_size=1, max_size=1)
        conn1 = pool.acquire(timeout_ms=50)
        conn2 = pool.acquire(timeout_ms=50)
        assert conn1 is not None
        assert conn2 is None

    def test_release_unknown_connection(self):
        pool = ConnectionPool("test-server", min_size=1, max_size=1)
        result = pool.release("unknown-conn")
        assert result is False


class TestHealthReport:
    @pytest.fixture
    def manager(self):
        return MCPServerManagerV2()

    @pytest.mark.asyncio
    async def test_health_report(self, manager):
        await manager.register_server(name="s1", url="http://localhost:8081")
        await manager.register_server(name="s2", url="http://localhost:8082")
        manager._servers[list(manager._servers.keys())[0]].status = ServerStatus.CONNECTED
        report = manager.get_health_report()
        assert report["total_servers"] == 2
        assert report["connected_servers"] == 1
        assert len(report["servers"]) == 2
