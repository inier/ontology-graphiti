"""MCP服务"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
from ..impl.server_manager import ToolServerManager
from ..impl.connection_pool import ConnectionPoolManager
from ..models.tool_server import ServerStatus

logger = logging.getLogger(__name__)


class MCPService:
    # Circuit breaker & retry configuration
    CIRCUIT_BREAKER_THRESHOLD = 5   # open after 5 consecutive failures
    CIRCUIT_BREAKER_RESET_SECONDS = 60  # try again after 60s
    MAX_RETRIES = 2
    RETRY_DELAY_BASE = 0.5  # seconds, doubles each retry

    def __init__(self):
        self.server_manager = ToolServerManager()
        self.pool_manager = ConnectionPoolManager()
        self._v2_manager = None
        # Circuit breaker state
        self._v2_failure_count = 0
        self._v2_circuit_open = False
        self._v2_circuit_open_until = 0  # timestamp

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

    def _is_circuit_open(self) -> bool:
        """Check if the circuit breaker is open (v2 calls should be skipped)."""
        if not self._v2_circuit_open:
            return False
        # Half-open: if the reset period has elapsed, allow one attempt
        if time.time() >= self._v2_circuit_open_until:
            logger.info("MCPService: circuit breaker half-open, allowing v2 attempt")
            self._v2_circuit_open = False
            return False
        return True

    def _record_v2_failure(self):
        """Record a v2 failure and potentially open the circuit breaker."""
        self._v2_failure_count += 1
        if self._v2_failure_count >= self.CIRCUIT_BREAKER_THRESHOLD:
            self._v2_circuit_open = True
            self._v2_circuit_open_until = time.time() + self.CIRCUIT_BREAKER_RESET_SECONDS
            logger.warning(
                "MCPService: circuit breaker OPENED after %d consecutive v2 failures, "
                "will retry after %ds",
                self._v2_failure_count,
                self.CIRCUIT_BREAKER_RESET_SECONDS,
            )

    def _record_v2_success(self):
        """Record a v2 success, resetting the failure counter."""
        if self._v2_failure_count > 0:
            logger.info("MCPService: v2 call succeeded, resetting failure count from %d", self._v2_failure_count)
        self._v2_failure_count = 0
        self._v2_circuit_open = False

    async def call_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        v2 = self._get_v2_manager()
        if v2 and not self._is_circuit_open():
            try:
                # Retry loop for transient errors (TimeoutError, ConnectionError)
                for attempt in range(self.MAX_RETRIES + 1):
                    try:
                        result = await v2.execute_tool(server_id, tool_name, arguments or {})
                        self._record_v2_success()
                        return result
                    except (TimeoutError, ConnectionError) as e:
                        if attempt < self.MAX_RETRIES:
                            delay = self.RETRY_DELAY_BASE * (2 ** attempt)
                            logger.info(
                                "MCPService call_tool v2 retry %d/%d after %s, waiting %.1fs",
                                attempt + 1, self.MAX_RETRIES, type(e).__name__, delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        raise
                    except Exception:
                        # Non-transient error: don't retry, just break out
                        break

                # If we get here, v2 failed with a non-transient error
                self._record_v2_failure()
            except (TimeoutError, ConnectionError) as e:
                # Exhausted retries for transient errors
                logger.warning("MCPService call_tool v2 failed after %d retries: %s", self.MAX_RETRIES, e)
                self._record_v2_failure()
            except Exception as e:
                logger.warning(f"MCPService call_tool via v2 failed: {e}")
                self._record_v2_failure()

        # v2 manager 不可用时，尝试通过 ToolRegistry 查找并执行
        try:
            from odap.biz.platform.tool_registry.registry import get_tool_registry
            registry = get_tool_registry()
            tool_id = registry._resolve_tool_id(tool_name)
            if tool_id:
                result = registry.execute(tool_name, arguments or {})
                return {
                    "status": "success" if result.success else "error",
                    "server_id": server_id,
                    "tool_name": tool_name,
                    "result": result.data,
                    "error": result.error,
                    "execution_time_ms": result.execution_time_ms,
                }
        except Exception as e:
            logger.warning(f"MCPService call_tool via ToolRegistry failed: {e}")

        # ToolRegistry 也无法执行，检查服务器状态并返回明确错误
        server = self.server_manager.get_server(server_id)
        if not server:
            return {"status": "error", "message": f"Server {server_id} not found"}
        if server.status != ServerStatus.CONNECTED:
            return {"status": "error", "message": f"Server {server_id} not connected"}

        return {
            "status": "error",
            "message": f"MCP tool '{tool_name}' execution unavailable: no v2 manager and tool not found in registry",
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

    def register_builtin_servers(self) -> List[Dict[str, Any]]:
        """注册内置 MCP 服务器（如 browser-use）

        仅在对应容器运行时注册，不会因容器不可用而阻塞启动。
        """
        from odap.infra.config_composer import get_config

        registered = []

        # Browser-Use MCP Server
        browser_url = get_config("mcp.browser_mcp_url", "http://graphiti-browser-use:8030")
        try:
            result = self.register_server(
                name="browser-use",
                url=browser_url,
                description="AI 驱动浏览器自动化采集（browse_task, browser_screenshot, browser_extract）",
            )
            registered.append(result)
            logger.info(f"Registered builtin MCP server: browser-use at {browser_url}")
        except Exception as e:
            logger.warning(f"Failed to register browser-use MCP server: {e}")

        return registered
