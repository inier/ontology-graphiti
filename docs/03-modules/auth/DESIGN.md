# 身份认证模块 (Authentication) - 设计文档

> **模块 ID**: M-20 | **优先级**: P0 | **相关 ADR**: ADR-003, ADR-028
> **版本**: 1.0.0 | **日期**: 2026-05-07 | **架构层**: L5 API 网关层 / L1 安全基础设施
> **对应需求**: NFR-S01 (SSO/OAuth2/本地认证), NFR-S02 (TLS 1.3)

---

## 1. 模块概述

### 1.1 模块定位

身份认证模块是 ODAP 平台的**安全入口**，负责验证用户身份并签发访问凭证。它与 OPA 权限系统职责互补：

```
┌─────────────────────────────────────────────────────────────┐
│                      安全架构分层                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────────────┐     ┌──────────────────┐            │
│   │   认证层 (Auth)   │────▶│   授权层 (OPA)    │            │
│   │   你是谁？        │     │   你能做什么？     │            │
│   └──────────────────┘     └──────────────────┘            │
│           │                          │                      │
│           ▼                          ▼                      │
│   ┌──────────────────┐     ┌──────────────────┐            │
│   │  JWT Token 签发   │     │  ABAC 权限校验    │            │
│   │  Session 管理     │     │  Rego 策略执行    │            │
│   └──────────────────┘     └──────────────────┘            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **多方式认证** | 灵活接入 | 同时支持 SSO/OAuth2/本地账号密码 |
| **无状态 Token** | 水平扩展友好 | JWT 自包含用户身份和角色信息 |
| **传输安全** | TLS 1.3 | 全链路加密传输 |
| **与 OPA 解耦** | 职责清晰 | 认证不参与权限决策，只传递身份 |

---

## 2. 认证方式设计

### 2.1 三种认证方式

| 方式 | 适用场景 | 优先级 | 依赖 |
|------|---------|:------:|------|
| OAuth2 (OIDC) | 企业内部 SSO、多系统统一登录 | P0 | Keycloak / Auth0 / Azure AD |
| 本地账号密码 | 独立部署、离线环境 | P0 | PostgreSQL (users 表) |
| API Key | 系统集成、自动化脚本 | P1 | PostgreSQL (api_keys 表) |

### 2.2 OAuth2 / OIDC 流程

```
┌─────────────────────────────────────────────────────────────┐
│                      OAuth2 Code Flow                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   用户浏览器             ODAP 后端            ID Provider   │
│   ────────              ────────            ────────────   │
│       │                     │                     │         │
│       │──GET /login────────▶│                     │         │
│       │                     │──redirect──────────▶│         │
│       │◀──302 to IdP────────│                     │         │
│       │                                               │      │
│       │──GET IdP /authorize─────────────────────────▶│      │
│       │◀──登录表单───────────────────────────────────│      │
│       │──POST 凭据────────────────────────────────▶│      │
│       │◀──302 /callback?code=xxx─────────────────────│      │
│       │                                               │      │
│       │──GET /auth/callback?code=xxx──▶│              │      │
│       │                     │──token(code)───────────▶│      │
│       │                     │◀──access_token + id_token│    │
│       │                     │                              │      │
│       │                     │  验证 id_token               │      │
│       │                     │  查找/创建本地用户            │      │
│       │                     │  签发 JWT (自包含角色)        │      │
│       │                     │                              │      │
│       │◀──JWT in cookie─────│                              │      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 本地认证流程

```
   用户                   ODAP 后端               PostgreSQL
   ────                  ────────               ──────────
     │                       │                       │
     │──POST /auth/login────▶│                       │
     │  {username, password} │──SELECT * FROM users──▶│
     │                       │◀──user record──────────│
     │                       │                       │
     │                       │  bcrypt.verify(password, hash)
     │                       │  签发 JWT (sub + role + ws)
     │                       │                       │
     │◀──JWT + user info────│                       │
```

---

## 3. JWT Token 设计

### 3.1 Token 结构

```python
class JWTPayload(TypedDict):
    iss: str       # Issuer: "odap"
    sub: str       # Subject: user_id (UUID)
    exp: int       # Expiration: Unix timestamp
    iat: int       # Issued At
    role: str      # 角色: commander / analyst / operator / admin
    ws_id: str     # 当前工作空间 ID
    ws_role: str   # 工作空间内角色（可不同于全局角色）

access_token: 15 分钟有效期
refresh_token: 7 天有效期 (存储在数据库，可吊销)
```

### 3.2 Token 签发

```python
import jwt
from datetime import datetime, timedelta, timezone

class JWTService:
    ACCESS_TTL = timedelta(minutes=15)
    REFRESH_TTL = timedelta(days=7)
    ALGORITHM = "RS256"

    def __init__(self, private_key_pem: str, public_key_pem: str):
        self._private_key = private_key_pem
        self._public_key = public_key_pem

    def issue_access_token(self, user: User, workspace_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "odap",
            "sub": str(user.id),
            "exp": now + self.ACCESS_TTL,
            "iat": now,
            "role": user.global_role,
            "ws_id": workspace_id,
            "ws_role": user.get_workspace_role(workspace_id),
        }
        return jwt.encode(payload, self._private_key, algorithm=self.ALGORITHM)

    def verify_token(self, token: str) -> JWTPayload:
        return jwt.decode(token, self._public_key, algorithms=[self.ALGORITHM],
                          options={"require": ["exp", "sub", "role"]})
```

### 3.3 Token 刷新

```python
class TokenService:
    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        record = await self._db.find_refresh_token(refresh_token)
        if not record or record.expires_at < datetime.now(timezone.utc):
            raise InvalidRefreshToken

        user = await self._user_service.get_by_id(record.user_id)
        new_access = self._jwt.issue_access_token(user, record.workspace_id)
        new_refresh = self._jwt.issue_refresh_token(user, record.workspace_id)

        await self._db.revoke_refresh_token(refresh_token)  # 旧 refresh 失效
        await self._db.store_refresh_token(new_refresh, user.id)

        return TokenPair(access_token=new_access, refresh_token=new_refresh)
```

---

## 4. 数据模型

### 4.1 用户表

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      TEXT NOT NULL UNIQUE,
    email         TEXT UNIQUE,
    password_hash TEXT,                    -- 本地认证用，SSO 用户为空
    global_role   TEXT NOT NULL DEFAULT 'analyst',
    auth_provider TEXT NOT NULL DEFAULT 'local',  -- 'local' / 'oidc'
    provider_uid  TEXT,                    -- OIDC subject (sub claim)
    is_active     BOOLEAN NOT NULL DEFAULT true,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_provider ON users(auth_provider, provider_uid)
    WHERE provider_uid IS NOT NULL;
```

### 4.2 工作空间角色表

```sql
CREATE TABLE workspace_memberships (
    user_id       UUID NOT NULL REFERENCES users(id),
    workspace_id  TEXT NOT NULL REFERENCES workspaces(id),
    role          TEXT NOT NULL DEFAULT 'analyst',
    joined_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, workspace_id)
);
```

### 4.3 刷新令牌表

```sql
CREATE TABLE refresh_tokens (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id),
    token_hash    TEXT NOT NULL UNIQUE,     -- SHA-256(token)
    workspace_id  TEXT NOT NULL,
    expires_at    TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked       BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);

CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id, revoked);
```

### 4.4 API Key 表

```sql
CREATE TABLE api_keys (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id),
    name          TEXT NOT NULL,            -- 用途描述
    key_hash      TEXT NOT NULL UNIQUE,     -- SHA-256(api_key)
    prefix        TEXT NOT NULL,            -- 前 8 位明文用于 UI 展示
    scopes        TEXT[] NOT NULL DEFAULT '{}',
    last_used_at  TIMESTAMP WITH TIME ZONE,
    expires_at    TIMESTAMP WITH TIME ZONE,
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

---

## 5. Pydantic 数据模型

```python
from pydantic import BaseModel, EmailStr
from enum import Enum

class AuthProvider(str, Enum):
    LOCAL = "local"
    OIDC = "oidc"

class GlobalRole(str, Enum):
    ADMIN = "admin"
    COMMANDER = "commander"
    ANALYST = "analyst"
    OPERATOR = "operator"
    OBSERVER = "observer"

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int                     # seconds

class UserInfo(BaseModel):
    id: str
    username: str
    email: str | None
    global_role: GlobalRole
    workspaces: list[WorkspaceMembership]

class WorkspaceMembership(BaseModel):
    workspace_id: str
    workspace_name: str
    role: str
```

---

## 6. API 端点

| 方法 | 路径 | 认证 | 描述 |
|------|------|:----:|------|
| POST | `/api/v1/auth/login` | 无 | 本地账号密码登录 |
| POST | `/api/v1/auth/refresh` | 无 | 刷新 access_token |
| POST | `/api/v1/auth/logout` | JWT | 吊销 refresh_token |
| GET | `/api/v1/auth/me` | JWT | 获取当前用户信息 |
| GET | `/api/v1/auth/providers` | 无 | 列出可用的 OIDC Provider |
| GET | `/api/v1/auth/oidc/login/{provider}` | 无 | 发起 OIDC 登录 (redirect) |
| GET | `/api/v1/auth/oidc/callback/{provider}` | 无 | OIDC 回调处理 |
| POST | `/api/v1/auth/api-keys` | JWT | 创建 API Key |
| DELETE | `/api/v1/auth/api-keys/{id}` | JWT | 吊销 API Key |
| PUT | `/api/v1/users/password` | JWT | 修改密码（本地用户） |

---

## 7. 中间件设计

### 7.1 JWT 认证中间件

```python
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer(auto_error=False)

class AuthMiddleware:
    """FastAPI 中间件：从 Cookie 或 Authorization Header 提取 JWT 并注入请求上下文"""

    async def __call__(self, request: Request, call_next):
        token = self._extract_token(request)
        if token:
            try:
                payload = self._jwt_service.verify_token(token)
                request.state.user_id = payload["sub"]
                request.state.user_role = payload["role"]
                request.state.workspace_id = payload["ws_id"]
                request.state.workspace_role = payload["ws_role"]
            except jwt.ExpiredSignatureError:
                pass    # 让路由层处理 401
            except jwt.InvalidTokenError:
                pass

        return await call_next(request)

    def _extract_token(self, request: Request) -> str | None:
        # 优先从 Authorization Header 读取
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        # 其次从 Cookie 读取（浏览器场景）
        return request.cookies.get("odap_access_token")
```

### 7.2 API Key 认证中间件

```python
class APIKeyMiddleware:
    async def __call__(self, request: Request, call_next):
        api_key = request.headers.get("X-ODAP-API-Key")
        if api_key and not hasattr(request.state, "user_id"):
            record = await self._api_key_service.validate(api_key)
            if record:
                request.state.user_id = str(record.user_id)
                request.state.user_role = record.role
                request.state.auth_method = "api_key"
        return await call_next(request)
```

---

## 8. 依赖注入装饰器

```python
from functools import wraps

def require_auth(roles: list[str] | None = None):
    """路由依赖：要求 JWT 认证 + 可选角色限制"""

    def decorator(endpoint):
        @wraps(endpoint)
        async def wrapper(request: Request, *args, **kwargs):
            if not hasattr(request.state, "user_id"):
                raise HTTPException(status_code=401, detail="未认证")

            if roles and request.state.user_role not in roles:
                raise HTTPException(status_code=403, detail="权限不足")

            return await endpoint(request, *args, **kwargs)
        return wrapper
    return decorator
```

---

## 9. 与 OPA 的对接点

认证模块向 OPA 传递身份信息（`user_id` / `role` / `ws_role` / `auth_method`），OPA 基于 Rego 规则决策 `allow=true/false`。

> **📘 详细的对接实现代码（Python OPAPermissionChecker + Rego 规则完整示例）见**:
> [opa_policy/DESIGN.md §7 权限检查与认证对接](../opa_policy/DESIGN.md#7-权限检查与认证对接)

关键接口约定：
- 认证中间件写入 `request.state.user_id` / `.user_role` / `.workspace_role` / `.auth_method`
- OPA `input` 结构: `{user: {id, role, ws_role, auth_method}, action, resource, workspace_id}`
- Rego 包名: `odap.authz`

---

## 10. 传输安全 (TLS 1.3)

| 措施 | 实现 |
|------|------|
| HTTPS 强制 | Nginx 反向代理层 301 重定向 HTTP → HTTPS |
| TLS 版本 | nginx.conf: `ssl_protocols TLSv1.3;` |
| 证书管理 | Docker Compose 中的 certbot + Let's Encrypt 自动续期 |
| HSTS | `add_header Strict-Transport-Security "max-age=63072000" always;` |
| Cookie 安全 | JWT Cookie 设置 `Secure; HttpOnly; SameSite=Lax` |

---

## 11. 安全最佳实践

| 措施 | 说明 |
|------|------|
| 密码哈希 | bcrypt (cost=12) |
| 登录限流 | 5 次失败 / 15 分钟 / IP，超过锁定 30 分钟 |
| JWT Key 轮换 | RS256 密钥对，定期轮换（30天），旧公钥保留验证窗口 |
| Refresh Token Rotation | 每次刷新时旧 token 立即失效 |
| Session 管理 | 支持主动登出吊销所有 refresh_token |
| 审计记录 | 登录/登出/Token 刷新/角色变更 均记录审计日志 |

---

## 12. 相关文档

- [ADR-003: OPA 策略治理引擎](../../07-adr/ADR-003_opa_策略治理引擎mvp_生产化.md)
- [ADR-028: 权限检查 OPA 集成](../../07-adr/ADR-028_permission_checker_opa_integration.md)
- [OPA Policy 模块设计](../opa_policy/DESIGN.md)
- [全链路深入实现设计](../../02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md) — Phase 4 Skill 执行中 OPA 校验流程
- [架构文档 (L1 基础设施)](../../02-architecture/ARCHITECTURE_INFRA.md)
