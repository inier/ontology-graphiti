# ADR-040: API 网关统一入口

## 状态
已接受

## 上下文

ODAP 平台需要一个统一的 API 入口层，承担以下横切职责：

1. **认证鉴权**：JWT + API Key + SSO，统一认证后后端服务无需重复鉴权
2. **权限校验**：每请求 OPA 策略校验
3. **流量治理**：限流、熔断，保护后端
4. **路由分发**：按模块分组路由，RESTful API 规范
5. **协议适配**：REST + WebSocket + SSE 统一管理
6. **可观测性**：请求追踪、指标采集、日志聚合

### 选型考量

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A. FastAPI 中间件** | 在现有 FastAPI 应用内实现网关功能 | 零额外部署、Python 原生、调试方便 | 性能受限于 Python、无法独立扩缩 |
| **B. Nginx/Kong** | 外部反向代理作为网关 | 高性能、成熟生态 | 多一层运维、配置复杂、Python 逻辑需 sidecar |
| **C. 独立网关服务** | 用 Go/Rust 写独立网关 | 高性能、可独立扩缩 | 开发成本高、多语言栈 |

### 约束

- ADR-046 决策：Phase 4 模块化单体，单进程部署
- 团队 3-5 人，无专职 DevOps
- 后端所有服务 in-process，无需跨进程路由

## 决策

**采用方案 A：基于 FastAPI 中间件的 API 网关**。

在现有 FastAPI 应用内通过中间件链实现网关职责，不引入外部网关组件。

### 中间件栈

```
Request → CORS → AuthMiddleware → PermissionMiddleware → RateLimiter → Router → Handler
                                                                              │
Response ← LoggingMiddleware ← CompressionMiddleware ← Handler ←─────────────┘
```

### 路由分组

```
/api/auth/*       → 认证模块
/api/qa/*         → QAEngine
/api/ontology/*   → OntologyManager
/api/workspace/*  → WorkspaceManager
/api/simulation/* → SimulationEngine
/api/audit/*      → AuditLogger
/api/agents/*     → SwarmOrchestrator
/api/tools/*      → ToolRegistry
/api/hooks/*      → HookSystem
/api/admin/*      → 管理后台
/ws/*             → WebSocket 端点
/sse/*            → SSE 端点
```

### 认证流程

```
1. 请求到达 AuthMiddleware
2. 提取 Authorization Header / API Key / Cookie
3. JWT 验证（本地公钥验证，< 5ms）
4. 提取 user_id + roles → 注入 Request.state
5. PermissionMiddleware 调用 OPA（带缓存，< 20ms）
6. 通过 → 继续处理；拒绝 → 403
```

## 后果

### 变得更容易

- **开发效率**：纯 Python，与业务代码同进程，无序列化开销
- **部署简单**：无额外组件，Docker Compose 少一个容器
- **调试友好**：断点可以跨中间件和业务逻辑
- **OPA 集成**：in-process 调用，无网络延迟

### 变得更难

- **性能上限**：Python GIL 限制，单进程并发上限约 1000 RPS
- **独立扩缩**：网关和业务耦合，无法独立水平扩展
- **语言限制**：中间件逻辑必须用 Python，无法引入高性能语言

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| 单进程性能瓶颈 | uvicorn + 多 worker + 异步 IO，预估 500 RPS 足够 |
| 中间件顺序错误导致安全漏洞 | 中间件栈硬编码，不可配置顺序 |
| 未来需要独立网关 | FastAPI 中间件逻辑可迁移到 Nginx/Kong，路由规则兼容 |

## 可逆性

**高**。FastAPI 中间件 → 外部网关的迁移路径清晰：将认证/限流逻辑迁移到 Nginx/Kong，路由规则保持一致。当前设计按模块分组的路由结构天然兼容外部网关。

## 关联

- 关联 ADR-046（模块化单体部署）
- 关联 ADR-028（OPA 权限校验）
- 关联 M-16 DESIGN.md
- 影响 WR-17（API 网关）
