"""MCP服务"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from ..impl.server_manager import ToolServerManager
from ..impl.connection_pool import ConnectionPoolManager
from ..models.tool_server import ServerStatus

logger = logging.getLogger(__name__)


class MCPService:
    def __init__(self):
        self.server_manager = ToolServerManager()
        self.pool_manager = ConnectionPoolManager()
        self._v2_manager = None

    def _get_v2_manager(self):
        if self._v2_manager is None:
            try:
                from odap.biz.integration.mcp_adapter.mcp_server_manager import get_mcp_manager
                self._v2_manager = get_mcp_manager()
            except Exception as e:
                logger.warning(f"MCPService: v2 manager init failed: {e}")
        return self._v2_manager

    def register_server(self, name: str, url: str, description: str = "") -> Dict[str, Any]:
        server = self.server_manager.register_server(name, url, description)
        self.pool_manager.create_pool(server.id)
        return {
            "server_id": server.id,
            "name": server.name,
            "url": server.url,
            "status": server.status.value,
        }

    def unregister_server(self, server_id: str) -> Dict[str, Any]:
        success = self.server_manager.unregister_server(server_id)
        if not success:
            return {"status": "error", "message": f"Server {server_id} not found"}
        return {"status": "success", "server_id": server_id}

    def connect_server(self, server_id: str) -> Dict[str, Any]:
        success = self.server_manager.connect_server(server_id)
        return {"status": "success" if success else "error"}

    def disconnect_server(self, server_id: str) -> Dict[str, Any]:
        success = self.server_manager.disconnect_server(server_id)
        return {"status": "success" if success else "error"}

    def list_servers(self, status: str = None) -> List[Dict[str, Any]]:
        filters = {"status": status} if status else None
        servers = self.server_manager.list_servers(filters)
        return [
            {
                "server_id": s.id,
                "name": s.name,
                "url": s.url,
                "status": s.status.value,
                "description": s.description,
            }
            for s in servers
        ]

    def discover_tools(self, server_id: str) -> List[Dict[str, Any]]:
        return self.server_manager.discover_tools(server_id)

    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        v2 = self._get_v2_manager()
        if v2:
            try:
                result = await v2.execute_tool(server_id, tool_name, arguments or {})
                return result
            except Exception as e:
                logger.warning(f"MCPService call_tool via v2 failed: {e}")

        server = self.server_manager.get_server(server_id)
        if not server:
            return {"status": "error", "message": f"Server {server_id} not found"}
        if server.status != ServerStatus.CONNECTED:
            return {"status": "error", "message": f"Server {server_id} not connected"}

        return {
            "status": "success",
            "server_id": server_id,
            "tool_name": tool_name,
            "result": arguments or {},
        }

    def get_server_status(self, server_id: str) -> Dict[str, Any]:
        server = self.server_manager.get_server(server_id)
        if not server:
            return {"status": "error", "message": f"Server {server_id} not found"}
        pool_status = self.pool_manager.get_pool_status(server_id)
        return {
            "server_id": server.id,
            "name": server.name,
            "url": server.url,
            "status": server.status.value,
            "connected_at": server.connected_at.isoformat() if server.connected_at else None,
            "pool": pool_status,
        }

    def acquire_connection(self, server_id: str) -> Dict[str, Any]:
        conn_id = self.pool_manager.acquire(server_id)
        if conn_id:
            return {"connection_id": conn_id, "status": "acquired"}
        return {"status": "error", "message": "No connection available"}

    def release_connection(self, connection_id: str) -> Dict[str, Any]:
        success = self.pool_manager.release(connection_id)
        return {"status": "success" if success else "error"}

    def get_pool_status(self, server_id: str) -> Dict[str, Any]:
        return self.pool_manager.get_pool_status(server_id)
