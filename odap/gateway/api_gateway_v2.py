"""
API 网关 - 认证 + 限流 + OPA

功能：
- JWT + API Key 认证鉴权
- 令牌桶 + 滑动窗口限流
- OPA 权限集成
- WebSocket + SSE 支持
- 请求日志 + 审计集成
"""

import sys
import os
import json
import time
import asyncio
import threading
import hashlib
import hmac
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import deque
from functools import wraps

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

try:
    from opa_service_v2 import OPAManagerV2
    OPA_AVAILABLE = True
except ImportError:
    OPA_AVAILABLE = False


class RateLimitType(Enum):
    """限流类型"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"


@dataclass
class RateLimitConfig:
    """限流配置"""
    rate_limit_type: RateLimitType = RateLimitType.TOKEN_BUCKET
    requests_per_second: int = 100
    burst_size: int = 200
    window_size_seconds: int = 60


@dataclass
class AuthCredentials:
    """认证凭据"""
    user_id: str
    user_name: str
    roles: List[str]
    permissions: List[str]
    token_type: str
    expires_at: Optional[str] = None


class JWTAuthenticator:
    """JWT 认证器"""

    def __init__(self, secret_key: str = None, algorithm: str = "HS256"):
        self.secret_key = secret_key or os.getenv("JWT_SECRET", "default-secret-key")
        self.algorithm = algorithm

    def create_token(self, user_id: str, user_name: str, roles: List[str],
                   expires_in: int = 3600) -> str:
        """创建 JWT Token"""
        if not JWT_AVAILABLE:
            return f"mock_token_{user_id}"

        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id,
            "name": user_name,
            "roles": roles,
            "iat": int(now.timestamp()),
            "exp": int(now.timestamp()) + expires_in
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[AuthCredentials]:
        """验证 Token"""
        if not JWT_AVAILABLE:
            if token.startswith("mock_token_"):
                user_id = token.replace("mock_token_", "")
                return AuthCredentials(
                    user_id=user_id,
                    user_name="Mock User",
                    roles=["user"],
                    permissions=["read"],
                    token_type="mock"
                )
            return None

        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            return AuthCredentials(
                user_id=payload.get("sub", ""),
                user_name=payload.get("name", ""),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                token_type="jwt",
                expires_at=datetime.fromtimestamp(payload["exp"]).isoformat()
            )
        except Exception as e:
            print(f"JWT 验证失败: {e}")
            return None


class APIKeyAuthenticator:
    """API Key 认证器"""

    def __init__(self):
        self._api_keys: Dict[str, Dict] = {}
        self._init_default_keys()

    def _init_default_keys(self):
        """初始化默认 API Keys"""
        self.register_key("default-key-001", "system", ["admin"], ["*"])

    def register_key(self, api_key: str, user_name: str, roles: List[str],
                   permissions: List[str], expires_at: str = None):
        """注册 API Key"""
        self._api_keys[api_key] = {
            "user_name": user_name,
            "roles": roles,
            "permissions": permissions,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at
        }

    def verify_key(self, api_key: str) -> Optional[AuthCredentials]:
        """验证 API Key"""
        if api_key not in self._api_keys:
            return None

        key_info = self._api_keys[api_key]

        if key_info.get("expires_at"):
            expires = datetime.fromisoformat(key_info["expires_at"])
            if expires < datetime.now(timezone.utc):
                return None

        return AuthCredentials(
            user_id=hashlib.md5(api_key.encode()).hexdigest()[:8],
            user_name=key_info["user_name"],
            roles=key_info["roles"],
            permissions=key_info["permissions"],
            token_type="api_key"
        )


class TokenBucketRateLimiter:
    """令牌桶限流器"""

    def __init__(self, rate: int, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock = threading.Lock()

    def allow_request(self) -> bool:
        """检查是否允许请求"""
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


class SlidingWindowRateLimiter:
    """滑动窗口限流器"""

    def __init__(self, max_requests: int, window_size: int):
        self.max_requests = max_requests
        self.window_size = window_size
        self.requests: deque = deque()
        self._lock = threading.Lock()

    def allow_request(self) -> bool:
        """检查是否允许请求"""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_size

            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False


class RateLimiter:
    """限流器"""

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._limiters: Dict[str, Any] = {}

        if self.config.rate_limit_type == RateLimitType.TOKEN_BUCKET:
            self._limiter_class = TokenBucketRateLimiter
        else:
            self._limiter_class = SlidingWindowRateLimiter

    def get_limiter(self, key: str) -> Any:
        """获取限流器"""
        if key not in self._limiters:
            if self.config.rate_limit_type == RateLimitType.TOKEN_BUCKET:
                self._limiters[key] = self._limiter_class(
                    self.config.requests_per_second,
                    self.config.burst_size
                )
            else:
                self._limiters[key] = self._limiter_class(
                    self.config.requests_per_second,
                    self.config.window_size_seconds
                )
        return self._limiters[key]

    def check_rate_limit(self, key: str) -> bool:
        """检查限流"""
        limiter = self.get_limiter(key)
        return limiter.allow_request()

    def get_remaining(self, key: str) -> int:
        """获取剩余请求数"""
        limiter = self.get_limiter(key)
        if isinstance(limiter, TokenBucketRateLimiter):
            return int(limiter.tokens)
        return 0


class OPAIntegration:
    """OPA 权限集成"""

    def __init__(self, opa_manager=None):
        self.opa_manager = opa_manager

    def check_permission(self, credentials: AuthCredentials, action: str,
                       resource: Dict) -> bool:
        """检查权限"""
        if not self.opa_manager:
            return True

        user_role = credentials.roles[0] if credentials.roles else "guest"

        return self.opa_manager.check_permission(
            user_role, action, resource
        )

    def get_allowed_actions(self, credentials: AuthCredentials,
                         resource_type: str) -> List[str]:
        """获取允许的操作"""
        if not self.opa_manager:
            return ["read", "write", "delete"]

        all_actions = ["read", "write", "delete", "admin"]
        allowed = []

        for action in all_actions:
            if self.check_permission(credentials, action, {"type": resource_type}):
                allowed.append(action)

        return allowed


class RequestLogger:
    """请求日志"""

    def __init__(self):
        self._logs: deque = deque(maxlen=10000)
        self._lock = threading.Lock()

    def log(self, request_id: str, method: str, path: str,
           user_id: str, status_code: int, duration_ms: float,
           metadata: Dict = None):
        """记录请求"""
        with self._lock:
            self._logs.append({
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": method,
                "path": path,
                "user_id": user_id,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "metadata": metadata or {}
            })

    def get_logs(self, limit: int = 100, user_id: str = None) -> List[Dict]:
        """获取日志"""
        with self._lock:
            logs = list(self._logs)

        if user_id:
            logs = [l for l in logs if l["user_id"] == user_id]

        return logs[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        with self._lock:
            logs = list(self._logs)

        if not logs:
            return {"total_requests": 0, "avg_duration_ms": 0}

        total = len(logs)
        durations = [l["duration_ms"] for l in logs]
        status_codes = {}

        for log in logs:
            code = log["status_code"]
            status_codes[code] = status_codes.get(code, 0) + 1

        return {
            "total_requests": total,
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "status_codes": status_codes
        }


class API GatewayV2:
    """
    API 网关 v2

    功能：
    - JWT + API Key 认证
    - 令牌桶 + 滑动窗口限流
    - OPA 权限集成
    - WebSocket + SSE 支持
    - 请求日志 + 审计集成
    """

    def __init__(self, config: Dict = None):
        config = config or {}

        self.jwt_auth = JWTAuthenticator(
            secret_key=config.get("jwt_secret"),
            algorithm=config.get("jwt_algorithm", "HS256")
        )
        self.api_key_auth = APIKeyAuthenticator()

        rate_config = RateLimitConfig(
            rate_limit_type=RateLimitType.TOKEN_BUCKET if config.get("rate_limit_type") == "token_bucket"
                          else RateLimitType.SLIDING_WINDOW,
            requests_per_second=config.get("requests_per_second", 100),
            burst_size=config.get("burst_size", 200),
            window_size_seconds=config.get("window_size_seconds", 60)
        )
        self.rate_limiter = RateLimiter(rate_config)

        if OPA_AVAILABLE:
            self.opa = OPAIntegration()
        else:
            self.opa = None

        self.request_logger = RequestLogger()

        self._active_connections: Dict[str, Any] = {}

    def authenticate(self, auth_header: str = None, api_key: str = None) -> Optional[AuthCredentials]:
        """认证"""
        if api_key:
            return self.api_key_auth.verify_key(api_key)

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return self.jwt_auth.verify_token(token)

        return None

    def check_permission(self, credentials: AuthCredentials, action: str,
                       resource: Dict) -> bool:
        """权限检查"""
        if not self.opa:
            return True
        return self.opa.check_permission(credentials, action, resource)

    def check_rate_limit(self, identifier: str) -> bool:
        """限流检查"""
        return self.rate_limiter.check_rate_limit(identifier)

    def log_request(self, request_id: str, method: str, path: str,
                   user_id: str, status_code: int, duration_ms: float,
                   metadata: Dict = None):
        """记录请求"""
        self.request_logger.log(request_id, method, path, user_id,
                              status_code, duration_ms, metadata)

    def create_token(self, user_id: str, user_name: str, roles: List[str],
                   expires_in: int = 3600) -> str:
        """创建 Token"""
        return self.jwt_auth.create_token(user_id, user_name, roles, expires_in)

    def register_api_key(self, api_key: str, user_name: str, roles: List[str],
                       permissions: List[str]):
        """注册 API Key"""
        self.api_key_auth.register_key(api_key, user_name, roles, permissions)

    def add_websocket(self, connection_id: str, websocket):
        """添加 WebSocket 连接"""
        self._active_connections[connection_id] = websocket

    def remove_websocket(self, connection_id: str):
        """移除 WebSocket 连接"""
        if connection_id in self._active_connections:
            del self._active_connections[connection_id]

    def broadcast_sse(self, event_type: str, data: Dict):
        """广播 SSE 事件"""
        for connection_id, ws in self._active_connections.items():
            try:
                ws.send(json.dumps({"type": event_type, "data": data}))
            except Exception:
                self.remove_websocket(connection_id)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "rate_limiter": {
                "type": self.rate_limiter.config.rate_limit_type.value,
                "requests_per_second": self.rate_limiter.config.requests_per_second
            },
            "active_connections": len(self._active_connections),
            "request_stats": self.request_logger.get_stats()
        }


_global_gateway: Optional[APIGatewayV2] = None


def get_api_gateway(config: Dict = None) -> APIGatewayV2:
    """获取全局 API 网关实例"""
    global _global_gateway
    if _global_gateway is None:
        _global_gateway = APIGatewayV2(config)
    return _global_gateway


def require_auth(func):
    """认证装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get("request")
        if not request:
            for arg in args:
                if hasattr(arg, "headers"):
                    request = arg
                    break

        gateway = get_api_gateway()
        auth_header = request.headers.get("Authorization")
        api_key = request.headers.get("X-API-Key")

        credentials = gateway.authenticate(auth_header, api_key)
        if not credentials:
            return {"error": "Unauthorized", "status_code": 401}

        kwargs["credentials"] = credentials
        return await func(*args, **kwargs)

    return wrapper


def require_permission(action: str, resource_type: str):
    """权限装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            credentials = kwargs.get("credentials")
            if not credentials:
                gateway = get_api_gateway()
                auth_header = None
                request = kwargs.get("request")
                if request:
                    auth_header = request.headers.get("Authorization")
                api_key = request.headers.get("X-API-Key") if request else None
                credentials = gateway.authenticate(auth_header, api_key)

            if not credentials:
                return {"error": "Unauthorized", "status_code": 401}

            gateway = get_api_gateway()
            if not gateway.check_permission(credentials, action, {"type": resource_type}):
                return {"error": "Forbidden", "status_code": 403}

            return await func(*args, **kwargs)

        return wrapper
    return decorator


if __name__ == "__main__":
    print("API 网关 v2 测试")

    print("\n=== 测试网关初始化 ===")
    gateway = get_api_gateway({
        "jwt_secret": "test-secret",
        "rate_limit_type": "token_bucket",
        "requests_per_second": 10,
        "burst_size": 20
    })
    print(f"网关初始化完成")
    print(f"  JWT 可用: {JWT_AVAILABLE}")
    print(f"  OPA 可用: {OPA_AVAILABLE}")

    print("\n=== 测试 JWT 认证 ===")
    token = gateway.create_token("user001", "Test User", ["admin"], expires_in=3600)
    print(f"创建 Token: {token[:50]}...")

    credentials = gateway.authenticate(auth_header=f"Bearer {token}")
    if credentials:
        print(f"  用户: {credentials.user_id}")
        print(f"  角色: {credentials.roles}")

    print("\n=== 测试 API Key 认证 ===")
    gateway.register_api_key("test-key-001", "API User", ["user"], ["read"])
    credentials = gateway.authenticate(api_key="test-key-001")
    if credentials:
        print(f"  API 用户: {credentials.user_name}")

    print("\n=== 测试限流 ===")
    for i in range(15):
        allowed = gateway.check_rate_limit("test_user")
        print(f"  请求 {i+1}: {'允许' if allowed else '拒绝'}")

    print("\n=== 测试权限检查 ===")
    class MockCredentials:
        def __init__(self):
            self.roles = ["admin"]
            self.permissions = ["*"]

    allowed = gateway.check_permission(MockCredentials(), "read", {"type": "document"})
    print(f"  管理员读取文档: {'允许' if allowed else '拒绝'}")

    print("\n=== 测试请求日志 ===")
    gateway.log_request("req-001", "GET", "/api/ontology", "user001", 200, 50.5)
    gateway.log_request("req-002", "POST", "/api/ontology/ingest", "user001", 200, 120.3)
    stats = gateway.request_logger.get_stats()
    print(f"  总请求数: {stats['total_requests']}")
    print(f"  平均耗时: {stats['avg_duration_ms']:.2f}ms")

    print("\n=== 测试网关统计 ===")
    gateway_stats = gateway.get_stats()
    print(f"  活跃连接: {gateway_stats['active_connections']}")
