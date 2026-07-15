"""Tool Server管理器实现"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..interfaces.server_manager import IToolServerManager
from ..models.tool_server import ToolServer, ServerStatus, ServerCapability

logger = logging.getLogger(__name__)

# ── 审计工具（懒加载 + 容错） ──
def _mcp_sm_audit(action: str, *, result_status: str = "success",
                  result_message: str = "", resource: str = None,
                  details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="integration_mcp",
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


class ToolServerManager(IToolServerManager):
    """Tool Server管理器实现"""
    
    def __init__(self):
        self._servers: Dict[str, ToolServer] = {}
    
    def register_server(self, name: str, url: str, description: str = "") -> ToolServer:
        """注册服务器"""
        server = ToolServer(
            name=name,
            url=url,
            description=description
        )
        self._servers[server.id] = server
        _mcp_sm_audit(
            action="mcp_register_server",
            result_status="success",
            resource=server.id,
            details={
                "mcp_server_id": server.id,
                "server_url": url,
                "name_len": len(name),
            },
        )
        return server

    def get_server(self, server_id: str) -> Optional[ToolServer]:
        """获取服务器"""
        return self._servers.get(server_id)

    def unregister_server(self, server_id: str) -> bool:
        """取消注册服务器"""
        if server_id in self._servers:
            del self._servers[server_id]
            _mcp_sm_audit(
                action="mcp_unregister_server",
                result_status="success",
                resource=server_id,
                details={"mcp_server_id": server_id},
            )
            return True
        _mcp_sm_audit(
            action="mcp_unregister_server",
            result_status="failure",
            result_message="Server not found",
            resource=server_id,
            details={"mcp_server_id": server_id},
        )
        return False

    def connect_server(self, server_id: str) -> bool:
        """连接服务器"""
        server = self._servers.get(server_id)
        if not server:
            _mcp_sm_audit(
                action="mcp_connect_server",
                result_status="failure",
                result_message="Server not found",
                resource=server_id,
                details={"mcp_server_id": server_id, "status": "failed"},
            )
            return False

        server.status = ServerStatus.CONNECTED
        server.connected_at = datetime.now()
        _mcp_sm_audit(
            action="mcp_connect_server",
            result_status="success",
            resource=server_id,
            details={
                "mcp_server_id": server_id,
                "server_url": server.url,
                "status": "connected",
            },
        )
        return True

    def disconnect_server(self, server_id: str) -> bool:
        """断开服务器连接"""
        server = self._servers.get(server_id)
        if not server:
            _mcp_sm_audit(
                action="mcp_disconnect_server",
                result_status="failure",
                result_message="Server not found",
                resource=server_id,
                details={"mcp_server_id": server_id, "status": "failed"},
            )
            return False

        server.status = ServerStatus.DISCONNECTED
        server.connected_at = None
        _mcp_sm_audit(
            action="mcp_disconnect_server",
            result_status="success",
            resource=server_id,
            details={
                "mcp_server_id": server_id,
                "server_url": server.url,
                "status": "disconnected",
            },
        )
        return True
    
    def list_servers(self, filters: Dict[str, Any] = None) -> List[ToolServer]:
        """列出服务器"""
        filters = filters or {}
        servers = list(self._servers.values())
        
        if "status" in filters:
            servers = [s for s in servers if s.status.value == filters["status"]]
        
        return servers
    
    def discover_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """发现工具 - 通过 MCP 协议从服务器获取工具列表"""
        server = self._servers.get(server_id)
        if not server:
            return []

        if server.status != ServerStatus.CONNECTED:
            logger.warning("ToolServerManager: server %s is not connected, cannot discover tools", server_id)
            return []

        # 尝试通过 MCP 协议发现工具
        try:
            import httpx
            tools_url = f"{server.url.rstrip('/')}/tools"
            response = httpx.get(tools_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "tools" in data:
                    return data["tools"]
        except ImportError:
            logger.warning("ToolServerManager: httpx not installed, trying requests for tool discovery")
            try:
                import requests
                tools_url = f"{server.url.rstrip('/')}/tools"
                response = requests.get(tools_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict) and "tools" in data:
                        return data["tools"]
            except Exception as e:
                logger.error("ToolServerManager: failed to discover tools from server %s: %s", server_id, e)
        except Exception as e:
            logger.error("ToolServerManager: failed to discover tools from server %s: %s", server_id, e)

        return []
