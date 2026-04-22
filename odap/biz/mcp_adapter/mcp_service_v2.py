"""
MCP 协议适配器 v2 - MCP Protocol Adapter
WR-07: MCP 协议适配 (Tool Server + 能力发现)

功能：
- Tool Server 注册与管理
- 能力发现机制
- 连接池管理
- 健康检查
- 与工具注册表集成
"""

import sys
import os
import json
import time
import asyncio
import threading
import hashlib
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
import aiohttp

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class ServerStatus(Enum):
    """服务器状态"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


class ServerCapability(Enum):
    """服务器能力"""
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    OBSERVATION = "observation"


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    annotations: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class ResourceDefinition:
    """资源定义"""
    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


@dataclass
class PromptDefinition:
    """提示定义"""
    name: str
    description: str
    arguments: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ServerHealthInfo:
    """服务器健康信息"""
    server_id: str
    status: str
    latency_ms: float = 0
    last_successful_call: Optional[str] = None
    consecutive_failures: int = 0
    total_calls: int = 0
    success_calls: int = 0
    last_error: Optional[str] = None


@dataclass
class MCPServer:
    """MCP Tool Server"""
    server_id: str
    name: str
    description: str
    url: str
    status: ServerStatus
    capabilities: List[ServerCapability] = field(default_factory=list)
    tools: List[ToolDefinition] = field(default_factory=list)
    resources: List[ResourceDefinition] = field(default_factory=list)
    prompts: List[PromptDefinition] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    health: Optional[ServerHealthInfo] = None
    connected_at: Optional[str] = None
    last_pinged_at: Optional[str] = None
    created_at: str = ""
    version: str = "1.0.0"

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.health:
            self.health = ServerHealthInfo(
                server_id=self.server_id,
                status=ServerStatus.DISCONNECTED.value
            )


class ConnectionPool:
    """连接池"""

    def __init__(self, server_id: str, min_size: int = 2, max_size: int = 10):
        self.server_id = server_id
        self.min_size = min_size
        self.max_size = max_size
        self._available: List[str] = []
        self._in_use: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._connection_counter = 0

        for _ in range(min_size):
            conn_id = self._generate_conn_id()
            self._available.append(conn_id)

    def _generate_conn_id(self) -> str:
        self._connection_counter += 1
        return f"conn-{self.server_id[:8]}-{self._connection_counter}"

    def acquire(self, timeout_ms: int = 5000) -> Optional[str]:
        """获取连接"""
        start = time.perf_counter()
        while time.perf_counter() - start < timeout_ms / 1000:
            with self._lock:
                if self._available:
                    conn_id = self._available.pop()
                    self._in_use[conn_id] = conn_id
                    return conn_id
            time.sleep(0.01)
        return None

    def release(self, conn_id: str) -> bool:
        """释放连接"""
        with self._lock:
            if conn_id in self._in_use:
                del self._in_use[conn_id]
                if len(self._available) < self.max_size:
                    self._available.append(conn_id)
                    return True
                return False
        return False

    def get_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        with self._lock:
            return {
                "server_id": self.server_id,
                "available": len(self._available),
                "in_use": len(self._in_use),
                "total": len(self._available) + len(self._in_use),
                "max_size": self.max_size
            }


class MCPServerDiscovery:
    """MCP Server 发现引擎"""

    def __init__(self):
        self._discovery_cache: Dict[str, Dict] = {}
        self._capability_index: Dict[str, List[str]] = {}
        self._lock = threading.RLock()

    def index_server(self, server: MCPServer):
        """索引服务器"""
        with self._lock:
            self._discovery_cache[server.server_id] = {
                "server_id": server.server_id,
                "name": server.name,
                "description": server.description,
                "capabilities": [c.value for c in server.capabilities],
                "tool_count": len(server.tools),
                "version": server.version
            }

            for cap in server.capabilities:
                if cap.value not in self._capability_index:
                    self._capability_index[cap.value] = []
                self._capability_index[cap.value].append(server.server_id)

            for tool in server.tools:
                for tag in tool.tags:
                    if tag not in self._capability_index:
                        self._capability_index[tag] = []
                    self._capability_index[tag].append(f"{server.server_id}:{tool.name}")

    def discover_by_capability(self, capability: str) -> List[str]:
        """按能力发现服务器"""
        with self._lock:
            return self._capability_index.get(capability, [])

    def discover_by_tool(self, tool_name: str) -> List[str]:
        """按工具名称发现服务器"""
        with self._lock:
            return [k for k, v in self._discovery_cache.items()
                   if tool_name.lower() in k.lower()]

    def discover_all(self) -> List[Dict]:
        """发现所有服务器"""
        with self._lock:
            return list(self._discovery_cache.values())


class MCPToolBridge:
    """MCP 工具桥接器"""

    def __init__(self):
        self._bridge_registry: Dict[str, Dict] = {}
        self._tool_mappings: Dict[str, str] = {}

    def register_tool_from_server(self, server_id: str, tool: ToolDefinition) -> str:
        """从服务器注册工具到桥接器"""
        bridge_key = f"mcp:{server_id}:{tool.name}"
        self._bridge_registry[bridge_key] = {
            "bridge_key": bridge_key,
            "server_id": server_id,
            "tool_name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
            "tags": tool.tags
        }
        self._tool_mappings[tool.name] = bridge_key
        return bridge_key

    def get_bridged_tools(self) -> List[Dict]:
        """获取所有桥接的工具"""
        return list(self._bridge_registry.values())

    def get_bridge_key(self, tool_name: str) -> Optional[str]:
        """获取桥接键"""
        return self._tool_mappings.get(tool_name)


class MCPServerManagerV2:
    """
    MCP Server 管理器 v2
    完整的 MCP Tool Server 管理实现
    """

    def __init__(self):
        self._servers: Dict[str, MCPServer] = {}
        self._pools: Dict[str, ConnectionPool] = {}
        self._discovery = MCPServerDiscovery()
        self._bridge = MCPToolBridge()
        self._health_monitors: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self._health_check_interval_ms = 30000
        self._http_session: Optional[aiohttp.ClientSession] = None

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """获取 HTTP 会话"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def register_server(self, name: str, url: str, description: str = "",
                             version: str = "1.0.0",
                             capabilities: List[str] = None) -> MCPServer:
        """
        注册 MCP Server

        Args:
            name: 服务器名称
            url: 服务器 URL
            description: 描述
            version: 版本
            capabilities: 支持的能力列表

        Returns:
            MCPServer
        """
        with self._lock:
            server_id = str(uuid.uuid4())

            capability_enums = []
            for cap in (capabilities or [ServerCapability.TOOLS.value]):
                try:
                    capability_enums.append(ServerCapability(cap))
                except ValueError:
                    pass

            server = MCPServer(
                server_id=server_id,
                name=name,
                description=description,
                url=url,
                status=ServerStatus.DISCONNECTED,
                capabilities=capability_enums,
                version=version
            )

            self._servers[server_id] = server
            self._pools[server_id] = ConnectionPool(server_id)

            return server

    async def connect_server(self, server_id: str) -> bool:
        """
        连接 MCP Server

        Args:
            server_id: 服务器 ID

        Returns:
            是否连接成功
        """
        server = self._servers.get(server_id)
        if not server:
            return False

        try:
            session = await self._get_http_session()
            async with session.get(
                f"{server.url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    server.status = ServerStatus.CONNECTED
                    server.connected_at = datetime.now(timezone.utc).isoformat()
                    server.health.status = ServerStatus.CONNECTED.value
                    return True

        except Exception as e:
            server.status = ServerStatus.ERROR
            server.health.consecutive_failures += 1
            server.health.last_error = str(e)

        return False

    async def disconnect_server(self, server_id: str) -> bool:
        """断开 MCP Server 连接"""
        server = self._servers.get(server_id)
        if not server:
            return False

        server.status = ServerStatus.DISCONNECTED
        server.health.status = ServerStatus.DISCONNECTED.value
        return True

    async def discover_capabilities(self, server_id: str) -> Dict[str, Any]:
        """
        发现服务器能力

        Args:
            server_id: 服务器 ID

        Returns:
            能力信息
        """
        server = self._servers.get(server_id)
        if not server:
            return {}

        try:
            session = await self._get_http_session()

            async with session.get(
                f"{server.url}/capabilities",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    tools = []
                    for tool_data in data.get("tools", []):
                        tool = ToolDefinition(
                            name=tool_data["name"],
                            description=tool_data.get("description", ""),
                            input_schema=tool_data.get("inputSchema", {}),
                            tags=tool_data.get("tags", [])
                        )
                        tools.append(tool)
                        self._bridge.register_tool_from_server(server_id, tool)

                    server.tools = tools
                    server.resources = [
                        ResourceDefinition(
                            uri=r["uri"],
                            name=r["name"],
                            description=r.get("description", ""),
                            mime_type=r.get("mimeType", "application/json")
                        )
                        for r in data.get("resources", [])
                    ]
                    server.prompts = [
                        PromptDefinition(
                            name=p["name"],
                            description=p.get("description", ""),
                            arguments=p.get("arguments", [])
                        )
                        for p in data.get("prompts", [])
                    ]

                    self._discovery.index_server(server)

                    return {
                        "server_id": server_id,
                        "tools": len(tools),
                        "resources": len(server.resources),
                        "prompts": len(server.prompts)
                    }

        except Exception as e:
            return {"error": str(e)}

        return {}

    async def execute_tool(self, server_id: str, tool_name: str,
                          arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具

        Args:
            server_id: 服务器 ID
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            执行结果
        """
        server = self._servers.get(server_id)
        if not server:
            return {"success": False, "error": "Server not found"}

        if server.status != ServerStatus.CONNECTED:
            success = await self.connect_server(server_id)
            if not success:
                return {"success": False, "error": "Server not connected"}

        pool = self._pools.get(server_id)
        if not pool:
            return {"success": False, "error": "Connection pool not found"}

        conn_id = pool.acquire(timeout_ms=10000)
        if not conn_id:
            return {"success": False, "error": "No connection available"}

        try:
            start_time = time.perf_counter()
            session = await self._get_http_session()

            async with session.post(
                f"{server.url}/tools/{tool_name}/execute",
                json={"arguments": arguments},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                result = await response.json()
                execution_time_ms = (time.perf_counter() - start_time) * 1000

                server.health.total_calls += 1
                if response.status == 200:
                    server.health.success_calls += 1
                    server.health.consecutive_failures = 0
                    server.health.last_successful_call = datetime.now(timezone.utc).isoformat()
                else:
                    server.health.consecutive_failures += 1
                    server.health.last_error = result.get("error", "Unknown error")

                server.health.latency_ms = execution_time_ms

                return {
                    "success": response.status == 200,
                    "data": result,
                    "execution_time_ms": execution_time_ms
                }

        except Exception as e:
            server.health.consecutive_failures += 1
            server.health.last_error = str(e)
            return {
                "success": False,
                "error": str(e),
                "execution_time_ms": 0
            }

        finally:
            pool.release(conn_id)

    async def health_check(self, server_id: str) -> ServerHealthInfo:
        """
        健康检查

        Args:
            server_id: 服务器 ID

        Returns:
            健康信息
        """
        server = self._servers.get(server_id)
        if not server:
            return ServerHealthInfo(server_id=server_id, status="not_found")

        try:
            session = await self._get_http_session()
            start_time = time.perf_counter()

            async with session.get(
                f"{server.url}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status == 200:
                    server.health.status = ServerStatus.CONNECTED.value
                    server.health.latency_ms = latency_ms
                else:
                    server.health.consecutive_failures += 1
                    server.health.status = ServerStatus.ERROR.value

        except Exception as e:
            server.health.consecutive_failures += 1
            server.health.status = ServerStatus.ERROR.value
            server.health.last_error = str(e)

        return server.health

    def start_auto_health_check(self, server_id: str):
        """启动自动健康检查"""
        if server_id in self._health_monitors:
            return

        stop_event = threading.Event()
        self._stop_events[server_id] = stop_event

        def health_check_loop():
            while not stop_event.is_set():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.health_check(server_id))
                    loop.close()
                except Exception:
                    pass
                stop_event.wait(self._health_check_interval_ms / 1000)

        monitor = threading.Thread(target=health_check_loop, daemon=True)
        self._health_monitors[server_id] = monitor
        monitor.start()

    def stop_auto_health_check(self, server_id: str):
        """停止自动健康检查"""
        if server_id in self._stop_events:
            self._stop_events[server_id].set()
            del self._stop_events[server_id]
        if server_id in self._health_monitors:
            del self._health_monitors[server_id]

    def get_server(self, server_id: str) -> Optional[MCPServer]:
        """获取服务器"""
        return self._servers.get(server_id)

    def list_servers(self, status: str = None) -> List[MCPServer]:
        """列出所有服务器"""
        servers = list(self._servers.values())
        if status:
            servers = [s for s in servers if s.status.value == status]
        return servers

    def get_tools(self, server_id: str) -> List[ToolDefinition]:
        """获取服务器工具列表"""
        server = self._servers.get(server_id)
        return server.tools if server else []

    def get_pool_status(self, server_id: str) -> Optional[Dict[str, Any]]:
        """获取连接池状态"""
        pool = self._pools.get(server_id)
        return pool.get_status() if pool else None

    def get_discovery(self) -> MCPServerDiscovery:
        """获取发现引擎"""
        return self._discovery

    def get_bridge(self) -> MCPToolBridge:
        """获取桥接器"""
        return self._bridge

    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        total_servers = len(self._servers)
        connected = sum(1 for s in self._servers.values()
                       if s.status == ServerStatus.CONNECTED)
        error = sum(1 for s in self._servers.values()
                   if s.status == ServerStatus.ERROR)

        total_tools = sum(len(s.tools) for s in self._servers.values())
        total_calls = sum(s.health.total_calls for s in self._servers.values())
        success_calls = sum(s.health.success_calls for s in self._servers.values())

        return {
            "total_servers": total_servers,
            "connected_servers": connected,
            "error_servers": error,
            "total_tools": total_tools,
            "total_calls": total_calls,
            "success_calls": success_calls,
            "success_rate": (success_calls / total_calls * 100) if total_calls > 0 else 0,
            "servers": [
                {
                    "server_id": s.server_id,
                    "name": s.name,
                    "status": s.status.value,
                    "tool_count": len(s.tools),
                    "latency_ms": s.health.latency_ms,
                    "consecutive_failures": s.health.consecutive_failures
                }
                for s in self._servers.values()
            ]
        }


_global_mcp_manager: Optional[MCPServerManagerV2] = None


def get_mcp_manager() -> MCPServerManagerV2:
    """获取全局 MCP 管理器"""
    global _global_mcp_manager
    if _global_mcp_manager is None:
        _global_mcp_manager = MCPServerManagerV2()
    return _global_mcp_manager


if __name__ == "__main__":
    import asyncio

    async def test():
        manager = get_mcp_manager()

        print("=" * 60)
        print("MCP 协议适配器 v2 测试")
        print("=" * 60)

        print("\n1. 注册服务器:")
        server = await manager.register_server(
            name="test_server",
            url="http://localhost:8080",
            description="测试 MCP 服务器",
            capabilities=["tools", "resources"]
        )
        print(f"   服务器已注册: {server.name} (ID: {server.server_id})")

        print("\n2. 服务器列表:")
        servers = manager.list_servers()
        print(f"   共 {len(servers)} 个服务器")

        print("\n3. 连接池状态:")
        pool_status = manager.get_pool_status(server.server_id)
        print(f"   可用连接: {pool_status['available']}")
        print(f"   使用中: {pool_status['in_use']}")

        print("\n4. 健康报告:")
        report = manager.get_health_report()
        print(f"   总服务器数: {report['total_servers']}")
        print(f"   已连接: {report['connected_servers']}")
        print(f"   工具总数: {report['total_tools']}")

        print("\n" + "=" * 60)
        print("MCP 协议适配器 v2 测试完成")
        print("=" * 60)

    asyncio.run(test())