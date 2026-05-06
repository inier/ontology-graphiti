# API 网关模块 (API Gateway) - 设计文档

> **模块 ID**: M-16 | **优先级**: P0 | **相关 ADR**: ADR-040
> **版本**: 2.0.0 | **日期**: 2026-04-19 | **架构层**: L5 API 网关层

---

## 1. 模块概述

### 1.1 模块定位

API 网关是 ODAP 平台的**统一入口与流量治理层**，所有外部请求（Web 前端、第三方系统、CLI 工具）都通过网关进入系统。它承担认证鉴权、路由分发、流量控制、协议转换和可观测性注入等横切职责。

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **统一入口** | 单一入口点 | 所有 API 通过网关暴露，后端服务对前端透明 |
| **认证鉴权** | 安全第一 | 统一认证 + OPA 策略校验，后端服务无需重复鉴权 |
| **流量治理** | 稳定保障 | 限流、熔断、重试，保护后端不被流量击穿 |
| **协议适配** | 多协议支持 | REST / WebSocket / SSE 统一管理 |
| **可观测** | 全链路追踪 | 请求追踪、指标采集、日志聚合 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 外部客户端                                                                   │
│     Web SPA / CLI / 第三方系统                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ ★ L5  API 网关层 ★                                                            │
│     ┌──────────────────────────────────────────────────────────┐             │
│     │  APIGateway                                              │             │
│     │  Request → Auth → RateLimit → Route → Proxy → Response   │             │
│     └──────────────────────────────────────────────────────────┘             │
├─────────────────────────────────────────────────────────────────────────────┤
│ L4  应用服务层                                                                │
│     QAEngine / SimulationService / WorkspaceService                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ L1-L3  基础设施/技能/Agent 层                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心概念模型

### 2.1 路由模型

```python
class Route:
    """API 路由定义"""
    id: str                         # 路由 ID
    path: str                       # 请求路径 (e.g. "/api/qa/ask")
    methods: list[str]              # HTTP 方法
    service: str                    # 目标服务名
    upstream: str                   # 上游地址 (e.g. "http://localhost:8000")
    upstream_path: str | None       # 上游路径（如需改写）
    auth_required: bool             # 是否需要认证
    permission: str | None          # 所需权限 (e.g. "qa:ask")
    rate_limit: RateLimitConfig | None  # 限流配置
    timeout_ms: int                 # 超时 (default: 30000)
    retry_count: int                # 重试次数 (default: 0)
    cache_ttl_ms: int | None        # 缓存 TTL
    deprecated: bool                # 是否已弃用
    description: str                # 描述

class RateLimitConfig:
    """限流配置"""
    requests_per_second: float      # 每秒请求数
    requests_per_minute: int        # 每分钟请求数
    burst_size: int                 # 突发大小
    per_user: bool                  # 是否按用户限流
    per_ip: bool                    # 是否按 IP 限流
```

### 2.2 认证模型

```python
class AuthConfig:
    """认证配置"""
    provider: AuthProvider          # 认证提供者
    secret_key: str                 # JWT 签名密钥
    token_expiry: timedelta         # Token 过期时间
    refresh_expiry: timedelta       # Refresh Token 过期时间
    allowed_origins: list[str]      # CORS 允许源

class AuthProvider(str, Enum):
    LOCAL = "local"                 # 本地认证（用户名/密码）
    JWT = "jwt"                     # JWT Token
    OAUTH2 = "oauth2"               # OAuth2
    API_KEY = "api_key"             # API Key

class UserInfo:
    """用户信息（从 Token 解析）"""
    user_id: str
    username: str
    roles: list[str]
    workspace_ids: list[str]        # 有权访问的工作空间
    token_issued_at: datetime
    token_expires_at: datetime
```

---

## 3. 核心组件设计

### 3.1 APIGateway

```python
class APIGateway:
    """
    API 网关 - 核心入口

    请求处理管道：
    Request → CORS → Auth → RateLimit → Route → Permission → Proxy → Response

    技术选型：基于 FastAPI 中间件实现（单进程部署），
    后续可迁移到 Kong/Nginx（生产环境）。
    """

    def __init__(
        self,
        auth_handler: AuthHandler,
        rate_limiter: RateLimiter,
        router: Router,
        permission_bridge: PermissionBridge,
        proxy: ServiceProxy,
        metrics_collector: MetricsCollector,
    ):
        self._auth = auth_handler
        self._rate_limiter = rate_limiter
        self._router = router
        self._permission = permission_bridge
        self._proxy = proxy
        self._metrics = metrics_collector

    async def handle_request(self, request: Request) -> Response:
        """
        处理请求

        管道流程：
        1. CORS 检查
        2. 认证（提取 Token → 验证 → 解析 UserInfo）
        3. 限流检查
        4. 路由匹配
        5. 权限校验（OPA）
        6. 代理转发
        7. 指标采集
        8. 返回响应
        """
        trace_id = generate_trace_id()
        start_time = datetime.now()

        try:
            # Step 1: CORS
            self._check_cors(request)

            # Step 2: Auth
            route = self._router.match(request.path, request.method)
            user = None
            if route.auth_required:
                user = await self._auth.authenticate(request)

            # Step 3: Rate Limit
            await self._rate_limiter.check(request, route, user)

            # Step 4: Permission
            if route.permission:
                await self._permission.check(route.permission, user, request)

            # Step 5: Proxy
            response = await self._proxy.forward(request, route, trace_id)

            # Step 6: Metrics
            self._metrics.record(trace_id, start_time, success=True)

            return response

        except AuthError as e:
            self._metrics.record(trace_id, start_time, success=False, error="auth")
            return Response(status=401, body={"error": str(e)})
        except PermissionDeniedError as e:
            self._metrics.record(trace_id, start_time, success=False, error="permission")
            return Response(status=403, body={"error": str(e)})
        except RateLimitError as e:
            self._metrics.record(trace_id, start_time, success=False, error="rate_limit")
            return Response(status=429, body={"error": str(e)})
        except RouteNotFoundError as e:
            return Response(status=404, body={"error": str(e)})
        except Exception as e:
            self._metrics.record(trace_id, start_time, success=False, error="internal")
            return Response(status=500, body={"error": "Internal server error"})
```

### 3.2 AuthHandler（认证处理器）

```python
class AuthHandler:
    """
    认证处理器

    支持多种认证方式：
    - JWT Bearer Token（默认）
    - API Key（服务间调用）
    - OAuth2（第三方集成）
    """

    async def authenticate(self, request: Request) -> UserInfo:
        """
        认证请求

        流程：
        1. 从 Authorization header 提取 Token
        2. 验证 Token 签名和过期时间
        3. 解析 UserInfo
        4. 验证用户有权访问当前工作空间
        """
        ...

    async def login(self, username: str, password: str) -> TokenPair:
        """用户登录，返回 access_token + refresh_token"""
        ...

    async def refresh(self, refresh_token: str) -> TokenPair:
        """刷新 Token"""
        ...

    async def logout(self, token: str) -> None:
        """注销（Token 加入黑名单）"""
        ...

class TokenPair:
    """Token 对"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # 秒
```

### 3.3 RateLimiter（限流器）

```python
class RateLimiter:
    """
    限流器

    实现：滑动窗口 + 令牌桶
    存储：内存（单机）/ Redis（集群）
    """

    async def check(self, request: Request, route: Route, user: UserInfo | None) -> None:
        """
        检查限流

        优先级：
        1. 全局限流（保护系统）
        2. 路由级限流（保护特定服务）
        3. 用户级限流（防止单用户过载）
        """
        ...

    def _get_key(self, request: Request, route: Route, user: UserInfo | None) -> str:
        """生成限流 key"""
        if route.rate_limit and route.rate_limit.per_user and user:
            return f"rate:{route.path}:{user.user_id}"
        elif route.rate_limit and route.rate_limit.per_ip:
            return f"rate:{route.path}:{request.client_ip}"
        else:
            return f"rate:{route.path}"
```

### 3.4 PermissionBridge（权限桥接）

```python
class PermissionBridge:
    """
    权限桥接 - 将 API 请求映射为 OPA 策略查询

    网关层做粗粒度权限（能否访问该 API），
    服务层做细粒度权限（能否操作该资源）。
    """

    def __init__(self, opa_client: "OPAClient"):
        self._opa = opa_client

    async def check(self, permission: str, user: UserInfo, request: Request) -> None:
        """
        校验 API 级别权限

        OPA 查询：
        input = {
            "action": permission,  # e.g. "qa:ask"
            "subject": {"id": user.user_id, "roles": user.roles},
            "resource": {"type": "api", "path": request.path},
            "context": {"method": request.method}
        }
        """
        result = await self._opa.evaluate("gateway/allow", query_input)
        if not result.allow:
            raise PermissionDeniedError(result.reason)
```

### 3.5 ServiceProxy（服务代理）

```python
class ServiceProxy:
    """
    服务代理 - 将请求转发到上游服务

    支持：
    - HTTP/HTTPS 转发
    - WebSocket 代理
    - SSE 流代理
    - 请求/响应改写
    - 超时控制
    - 重试
    """

    async def forward(self, request: Request, route: Route, trace_id: str) -> Response:
        """
        转发请求

        流程：
        1. 构造上游请求（注入 trace_id、user_info header）
        2. 设置超时
        3. 发送请求
        4. 处理响应
        5. 失败时重试（如果配置了）
        """
        ...

    async def forward_ws(self, ws: WebSocket, route: Route, trace_id: str) -> None:
        """WebSocket 代理（双向转发）"""
        ...

    async def forward_sse(self, request: Request, route: Route, trace_id: str) -> AsyncIterator[str]:
        """SSE 流代理"""
        ...
```

---

## 4. 路由配置

### 4.1 路由注册表

```python
# 默认路由配置
ROUTES = [
    # 认证
    Route(path="/api/auth/login", methods=["POST"], service="auth", auth_required=False),
    Route(path="/api/auth/refresh", methods=["POST"], service="auth", auth_required=False),
    Route(path="/api/auth/logout", methods=["POST"], service="auth", permission="auth:logout"),

    # 工作空间
    Route(path="/api/workspaces", methods=["GET"], service="workspace", permission="workspace:list"),
    Route(path="/api/workspaces", methods=["POST"], service="workspace", permission="workspace:create"),
    Route(path="/api/workspaces/{id}", methods=["GET"], service="workspace", permission="workspace:read"),
    Route(path="/api/workspaces/{id}", methods=["PUT"], service="workspace", permission="workspace:update"),
    Route(path="/api/workspaces/{id}", methods=["DELETE"], service="workspace", permission="workspace:delete"),
    Route(path="/api/workspaces/{id}/switch", methods=["POST"], service="workspace", permission="workspace:switch"),

    # 问答
    Route(path="/api/qa/ask", methods=["POST"], service="qa", permission="qa:ask"),
    Route(path="/api/qa/ask/stream", methods=["POST"], service="qa", permission="qa:ask",
          timeout_ms=60000),  # 流式超时更长

    # 本体
    Route(path="/api/ontology/schema", methods=["GET"], service="ontology", permission="ontology:read"),
    Route(path="/api/ontology/entities", methods=["GET"], service="ontology", permission="ontology:read"),
    Route(path="/api/ontology/entities", methods=["POST"], service="ontology", permission="ontology:create"),

    # 图谱
    Route(path="/api/graph/search", methods=["POST"], service="graphiti", permission="graph:search"),
    Route(path="/api/graph/nodes", methods=["GET"], service="graphiti", permission="graph:read"),

    # 模拟
    Route(path="/api/simulations/scenarios", methods=["GET"], service="simulation", permission="simulation:scenario:list"),
    Route(path="/api/simulations/scenarios", methods=["POST"], service="simulation", permission="simulation:scenario:create"),
    Route(path="/api/simulations/scenarios/{id}/events", methods=["GET"], service="simulation", permission="simulation:event:read"),

    # 审计
    Route(path="/api/audit/events", methods=["GET"], service="audit", permission="audit:read"),

    # 工具
    Route(path="/api/tools", methods=["GET"], service="tools", permission="tool:list"),
    Route(path="/api/tools/{id}/execute", methods=["POST"], service="tools", permission="tool:execute"),

    # WebSocket
    Route(path="/ws/simulation/{id}", methods=["WS"], service="simulation", auth_required=True),
    Route(path="/ws/graph/updates", methods=["WS"], service="graphiti", auth_required=True),
]
```

---

## 5. WebSocket / SSE 管理

### 5.1 连接管理

```python
class ConnectionManager:
    """WebSocket / SSE 连接管理器"""

    async def accept_ws(self, ws: WebSocket, user: UserInfo, channel: str) -> str:
        """
        接受 WebSocket 连接

        流程：
        1. 认证验证（从 query param 或 header 获取 token）
        2. 权限校验
        3. 注册连接
        4. 返回连接 ID
        """
        ...

    async def broadcast(self, channel: str, message: dict, workspace_id: str | None = None) -> int:
        """
        广播消息到频道

        返回实际送达的连接数
        workspace_id: 仅发送到特定工作空间的连接
        """
        ...

    async def send_to_user(self, user_id: str, message: dict) -> bool:
        """发送消息到特定用户"""
        ...

    async def disconnect(self, connection_id: str) -> None:
        """断开连接"""
        ...

    def get_active_count(self, channel: str | None = None) -> int:
        """获取活跃连接数"""
        ...
```

---

## 6. 指标与可观测

### 6.1 MetricsCollector

```python
class MetricsCollector:
    """指标采集器"""

    def record(
        self,
        trace_id: str,
        start_time: datetime,
        *,
        success: bool,
        error: str | None = None,
    ) -> None:
        """记录请求指标"""
        ...

    def get_metrics(self, window: str = "1m") -> GatewayMetrics:
        """获取网关指标"""
        ...

class GatewayMetrics:
    """网关指标"""
    total_requests: int
    success_requests: int
    failed_requests: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    requests_per_second: float
    auth_failures: int
    permission_denials: int
    rate_limit_rejections: int
    active_ws_connections: int
    errors_by_type: dict[str, int]
```

---

## 7. 非功能设计

| 维度 | 指标 | 实现方式 |
|------|------|---------|
| 网关延迟 | < 10ms (P95) | 内存路由表 + 异步转发 |
| 吞吐量 | > 1000 RPS | 异步 I/O + 连接池 |
| 可用性 | 99.9% | 健康检查 + 自动重启 |
| 最大并发 WS | > 500 | 连接管理器优化 |
| 认证延迟 | < 5ms | JWT 本地验证 |
| 权限延迟 | < 20ms | OPA 本地缓存 |

---

## 8. 部署拓扑

### Phase 0-1（单进程）

```
FastAPI Application
├── APIGateway (Middleware)
├── All Services (in-process)
└── Static Files (SPA)
```

### Phase 2+（微服务，视需演进）

> ⚠️ ADR-046 决策：Phase 4 采用模块化单体。微服务拆分仅在 Phase 5+ 满足触发条件时执行（团队 8+ 人、独立扩缩容需求、有专职 SRE）。

```
Nginx / Kong (L7)
    ├── /api/* → APIGateway Service
    ├── /ws/* → WebSocket Gateway
    └── /* → Static Files (SPA)

APIGateway Service
    ├── /api/qa/* → QA Service
    ├── /api/simulation/* → Simulation Service
    ├── /api/workspace/* → Workspace Service
    └── /api/graph/* → Graphiti Service
```

---

## 9. 实现路径

### Phase 0 (当前)

- [x] Route 模型定义
- [x] APIGateway 管道设计
- [ ] FastAPI 中间件实现
- [ ] JWT 认证处理器

### Phase 1

- [ ] 限流器实现
- [ ] OPA 权限桥接
- [ ] WebSocket/SSE 代理
- [ ] 指标采集

### Phase 2

- [ ] API Key 认证
- [ ] OAuth2 集成
- [ ] 请求/响应改写
- [ ] 服务发现与负载均衡
- [ ] 迁移到 Kong/Nginx（可选）
