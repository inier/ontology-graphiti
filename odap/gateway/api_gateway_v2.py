"""
API 网关 v2 - 对齐 docs/03-modules/api_gateway/DESIGN.md

路由模型 + 认证处理器 + 限流器 + 权限桥接 + 服务代理 + 连接管理 + 指标采集
"""

import sys
import os
import json
import uuid
import time
import asyncio
import hashlib
import threading
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import defaultdict, deque
from functools import wraps

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class RateLimitType(Enum):
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"


@dataclass
class RateLimitConfig:
    requests_per_second: float = 100.0
    requests_per_minute: int = 6000
    burst_size: int = 200
    per_user: bool = False
    per_ip: bool = False


@dataclass
class Route:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    path: str = ""
    methods: List[str] = field(default_factory=lambda: ["GET"])
    service: str = "default"
    upstream: str = "http://localhost:8000"
    upstream_path: Optional[str] = None
    auth_required: bool = True
    permission: Optional[str] = None
    rate_limit: Optional[RateLimitConfig] = None
    timeout_ms: int = 30000
    retry_count: int = 0
    cache_ttl_ms: Optional[int] = None
    deprecated: bool = False
    description: str = ""


class AuthProvider(str, Enum):
    LOCAL = "local"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    API_KEY = "api_key"


@dataclass
class AuthConfig:
    provider: AuthProvider = AuthProvider.JWT
    secret_key: str = ""
    token_expiry: int = 900
    refresh_expiry: int = 604800
    allowed_origins: List[str] = field(default_factory=list)


@dataclass
class UserInfo:
    user_id: str
    username: str
    roles: List[str] = field(default_factory=list)
    workspace_ids: List[str] = field(default_factory=list)
    token_issued_at: Optional[datetime] = None
    token_expires_at: Optional[datetime] = None


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900


class AuthError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


class RateLimitError(Exception):
    pass


class RouteNotFoundError(Exception):
    pass


class AuthHandler:
    """认证处理器 - 对齐 DESIGN.md §3.2"""

    def __init__(self, auth_config: AuthConfig = None):
        self.config = auth_config or AuthConfig()

    async def authenticate(self, request) -> UserInfo:
        auth_header = getattr(request, "headers", {}).get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return await self._verify_jwt(auth_header[7:])
        raise AuthError("Missing or invalid Authorization header")

    async def _verify_jwt(self, token: str) -> UserInfo:
        try:
            import jwt
            payload = jwt.decode(
                token, self.config.secret_key,
                algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
            return UserInfo(
                user_id=payload["sub"],
                username=payload.get("name", payload["sub"]),
                roles=payload.get("roles", [payload.get("role", "user")]),
                workspace_ids=[payload.get("ws_id", "")] if payload.get("ws_id") else [],
            )
        except Exception as e:
            raise AuthError(f"JWT verification failed: {e}")

    async def login(self, username: str, password: str) -> TokenPair:
        import jwt
        now = datetime.now(timezone.utc)
        payload = {
            "sub": username,
            "name": username,
            "exp": int(now.timestamp()) + self.config.token_expiry,
            "iat": int(now.timestamp()),
            "roles": ["user"],
        }
        access = jwt.encode(payload, self.config.secret_key, algorithm="HS256")

        refresh_payload = {
            "sub": username,
            "exp": int(now.timestamp()) + self.config.refresh_expiry,
            "iat": int(now.timestamp()),
            "type": "refresh",
        }
        refresh = jwt.encode(refresh_payload, self.config.secret_key, algorithm="HS256")

        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.config.token_expiry,
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        import jwt
        try:
            payload = jwt.decode(
                refresh_token, self.config.secret_key, algorithms=["HS256"],
            )
            return await self.login(payload["sub"], "")
        except Exception as e:
            raise AuthError(f"Refresh failed: {e}")

    async def logout(self, token: str):
        pass


class RateLimiter:
    """限流器 - 滑动窗口 + 令牌桶"""

    def __init__(self):
        self._buckets: Dict[str, Any] = {}
        self._windows: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    async def check(self, request, route: Route, user: UserInfo = None):
        key = self._get_key(request, route, user)
        cfg = route.rate_limit

        if cfg:
            rate = cfg.requests_per_second if cfg.requests_per_second > 0 else cfg.requests_per_minute / 60.0

            with self._lock:
                if key not in self._buckets:
                    self._buckets[key] = {
                        "tokens": cfg.burst_size,
                        "last": time.time(),
                        "rate": rate,
                        "burst": cfg.burst_size,
                    }
                bucket = self._buckets[key]
                now = time.time()
                elapsed = now - bucket["last"]
                bucket["tokens"] = min(bucket["burst"], bucket["tokens"] + elapsed * bucket["rate"])
                bucket["last"] = now

                if bucket["tokens"] < 1:
                    raise RateLimitError("Rate limit exceeded")
                bucket["tokens"] -= 1

    def _get_key(self, request, route: Route, user: UserInfo = None) -> str:
        cfg = route.rate_limit
        parts = [route.path]
        if cfg and cfg.per_user and user:
            parts.append(user.user_id)
        elif cfg and cfg.per_ip:
            parts.append(getattr(request, "client_ip", "unknown"))
        return ":".join(parts)


class PermissionBridge:
    """权限桥接 - OPA 策略查询"""

    def __init__(self, opa_client=None):
        self._opa = opa_client

    async def check(self, permission: str, user: UserInfo, request) -> None:
        if not self._opa:
            return

        query_input = {
            "action": permission,
            "subject": {"id": user.user_id, "roles": user.roles},
            "resource": {
                "type": "api",
                "path": getattr(request, "path", ""),
            },
            "context": {"method": getattr(request, "method", "GET")},
        }

        try:
            result = await self._opa.evaluate("gateway/allow", query_input)
            if not result.get("allow", True):
                raise PermissionDeniedError(result.get("reason", "Access denied"))
        except PermissionDeniedError:
            raise
        except Exception as e:
            raise PermissionDeniedError(f"Permission check error: {e}")


class ServiceProxy:
    """服务代理 - 转发到上游服务"""

    async def forward(self, request, route: Route, trace_id: str) -> dict:
        return {"status": "ok", "route": route.path}

    async def forward_ws(self, ws, route: Route, trace_id: str):
        pass

    async def forward_sse(self, request, route: Route, trace_id: str) -> AsyncIterator[str]:
        yield "data: ok\\n\\n"


class ConnectionManager:
    """连接管理器 - WebSocket / SSE"""

    def __init__(self):
        self._connections: Dict[str, Any] = {}
        self._lock = threading.Lock()

    async def accept_ws(self, ws, user: UserInfo, channel: str) -> str:
        conn_id = str(uuid.uuid4())
        with self._lock:
            self._connections[conn_id] = {
                "ws": ws,
                "user": user,
                "channel": channel,
            }
        return conn_id

    async def broadcast(self, channel: str, message: dict, workspace_id: str = None) -> int:
        count = 0
        with self._lock:
            for conn in list(self._connections.values()):
                if conn["channel"] == channel:
                    try:
                        if hasattr(conn["ws"], "send"):
                            conn["ws"].send(json.dumps(message))
                            count += 1
                    except Exception:
                        pass
        return count

    async def disconnect(self, connection_id: str):
        with self._lock:
            self._connections.pop(connection_id, None)

    def get_active_count(self, channel: str = None) -> int:
        with self._lock:
            if channel:
                return sum(1 for c in self._connections.values() if c["channel"] == channel)
            return len(self._connections)


class MetricsCollector:
    """指标采集器"""

    def __init__(self):
        self._metrics: List[dict] = []
        self._lock = threading.Lock()

    def record(self, trace_id: str, start_time: datetime, *, success: bool, error: str = None):
        with self._lock:
            latency = (datetime.now() - start_time).total_seconds() * 1000
            self._metrics.append({
                "trace_id": trace_id,
                "latency_ms": latency,
                "success": success,
                "error": error,
            })
            if len(self._metrics) > 10000:
                self._metrics = self._metrics[-5000:]

    def get_metrics(self, window: str = "1m") -> dict:
        with self._lock:
            if not self._metrics:
                return {"total_requests": 0}
            total = len(self._metrics)
            latencies = [m["latency_ms"] for m in self._metrics]
            successes = sum(1 for m in self._metrics if m["success"])
            return {
                "total_requests": total,
                "success_requests": successes,
                "failed_requests": total - successes,
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            }


class APIGatewayV2:
    """API 网关 v2 - 对齐 DESIGN.md §3.1"""

    def __init__(
        self,
        auth_handler: AuthHandler = None,
        rate_limiter: RateLimiter = None,
        permission_bridge: PermissionBridge = None,
        proxy: ServiceProxy = None,
        metrics_collector: MetricsCollector = None,
        config: dict = None,
    ):
        self._auth = auth_handler or AuthHandler()
        self._rate_limiter = rate_limiter or RateLimiter()
        self._permission = permission_bridge or PermissionBridge()
        self._proxy = proxy or ServiceProxy()
        self._metrics = metrics_collector or MetricsCollector()

        self.routes: List[Route] = []
        self.connection_manager = ConnectionManager()
        self._init_default_routes()

    def _init_default_routes(self):
        self.routes = [
            Route(path="/api/auth/login", methods=["POST"], service="auth", auth_required=False,
                  description="用户登录"),
            Route(path="/api/auth/refresh", methods=["POST"], service="auth", auth_required=False,
                  description="刷新Token"),
            Route(path="/api/auth/logout", methods=["POST"], service="auth", permission="auth:logout",
                  description="登出"),
            Route(path="/api/workspaces", methods=["GET"], service="workspace", permission="workspace:list",
                  description="列出工作空间"),
            Route(path="/api/workspaces", methods=["POST"], service="workspace", permission="workspace:create",
                  description="创建工作空间"),
            Route(path="/api/workspaces/{id}", methods=["GET"], service="workspace", permission="workspace:read",
                  description="获取工作空间"),
            Route(path="/api/workspaces/{id}", methods=["PUT"], service="workspace", permission="workspace:update",
                  description="更新工作空间"),
            Route(path="/api/qa/ask", methods=["POST"], service="qa", permission="qa:ask",
                  description="问答"),
            Route(path="/api/qa/ask/stream", methods=["POST"], service="qa", permission="qa:ask",
                  timeout_ms=60000, description="流式问答"),
            Route(path="/api/ontology/schema", methods=["GET"], service="ontology", permission="ontology:read",
                  description="获取本体Schema"),
            Route(path="/api/ontology/entities", methods=["GET"], service="ontology", permission="ontology:read",
                  description="查询实体"),
            Route(path="/api/ontology/entities", methods=["POST"], service="ontology", permission="ontology:create",
                  description="创建实体"),
            Route(path="/api/graph/search", methods=["POST"], service="graphiti", permission="graph:search",
                  description="图谱搜索"),
            Route(path="/api/graph/nodes", methods=["GET"], service="graphiti", permission="graph:read",
                  description="获取节点"),
            Route(path="/api/simulations/scenarios", methods=["GET"], service="simulation",
                  permission="simulation:scenario:list", description="列出场景"),
            Route(path="/api/simulations/scenarios", methods=["POST"], service="simulation",
                  permission="simulation:scenario:create", description="创建场景"),
            Route(path="/api/audit/events", methods=["GET"], service="audit", permission="audit:read",
                  description="查询审计事件"),
            Route(path="/api/tools", methods=["GET"], service="tools", permission="tool:list",
                  description="列出工具"),
            Route(path="/ws/simulation/{id}", methods=["WS"], service="simulation", auth_required=False,
                  description="模拟器WebSocket"),
            Route(path="/ws/graph/updates", methods=["WS"], service="graphiti", auth_required=False,
                  description="图谱更新WebSocket"),
        ]

    def find_route(self, path: str, method: str) -> Optional[Route]:
        for route in self.routes:
            if route.path == path and method in route.methods:
                return route
        for route in self.routes:
            if route.path in path and method in route.methods:
                return route
        return None

    async def handle_request(self, request) -> dict:
        trace_id = str(uuid.uuid4())[:16]
        start_time = datetime.now()

        try:
            route = self.find_route(
                getattr(request, "path", "/"),
                getattr(request, "method", "GET"),
            )

            if route is None:
                self._metrics.record(trace_id, start_time, success=False, error="route_not_found")
                return {"error": "Route not found", "status_code": 404}

            user = None
            if route.auth_required:
                try:
                    user = await self._auth.authenticate(request)
                except AuthError as e:
                    self._metrics.record(trace_id, start_time, success=False, error="auth")
                    return {"error": str(e), "status_code": 401}

            try:
                await self._rate_limiter.check(request, route, user)
            except RateLimitError as e:
                self._metrics.record(trace_id, start_time, success=False, error="rate_limit")
                return {"error": str(e), "status_code": 429}

            if route.permission:
                try:
                    await self._permission.check(route.permission, user, request)
                except PermissionDeniedError as e:
                    self._metrics.record(trace_id, start_time, success=False, error="permission")
                    return {"error": str(e), "status_code": 403}

            response = await self._proxy.forward(request, route, trace_id)
            self._metrics.record(trace_id, start_time, success=True)
            return response

        except Exception as e:
            self._metrics.record(trace_id, start_time, success=False, error=str(e))
            return {"error": f"Gateway error: {e}", "status_code": 500}

    def get_stats(self) -> dict:
        return {
            "routes": len(self.routes),
            "active_ws": self.connection_manager.get_active_count(),
            "metrics": self._metrics.get_metrics(),
        }


_global_gateway: Optional[APIGatewayV2] = None


def get_api_gateway(config: dict = None) -> APIGatewayV2:
    global _global_gateway
    if _global_gateway is None:
        _global_gateway = APIGatewayV2(config=config)
    return _global_gateway
