"""审计中间件

自动记录写操作（POST/PUT/DELETE/PATCH）到审计日志。
GET 请求不记录，避免大量重复查询记录。
"""

import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_EXCLUDED_PATHS = {
    "/docs",
    "/openapi.json",
    "/redoc",
    "/health",
    "/favicon.ico",
}

_EXCLUDED_PREFIXES = (
    "/static",
    "/api/audit",
)

_WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def _extract_user_from_request(request: Request) -> tuple:
    """从请求中提取用户信息和工作空间 ID

    Returns:
        (user_id, workspace_id) 元组。无法提取时返回 ("anonymous", "default")。
        过期 token 返回 ("expired_token", "default") 以避免错误归属。
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt as pyjwt
            from odap.infra.security.config import security_config
            token = auth_header[7:]
            # 验证签名 + 过期时间（默认 verify_exp=True）
            payload = pyjwt.decode(
                token,
                security_config.get_jwt_secret(),
                algorithms=[security_config.get_jwt_algorithm()],
            )
            user_id = payload.get("name") or payload.get("sub") or "authenticated"
            workspace_id = payload.get("ws_id", "default")
            return user_id, workspace_id
        except Exception as e:
            # 过期 token 或无效 token - 不归属到任何用户
            logger.debug(f"Audit middleware: token decode failed: {e}")
            return "anonymous", "default"
    return "anonymous", "default"


class AuditMiddleware(BaseHTTPMiddleware):
    """审计中间件 - 仅记录写操作（POST/PUT/DELETE/PATCH）"""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path in _EXCLUDED_PATHS:
            return await call_next(request)

        if not path.startswith("/api/"):
            return await call_next(request)

        for prefix in _EXCLUDED_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        method = request.method

        if method not in _WRITE_METHODS:
            return await call_next(request)

        start_time = time.time()
        trace_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        user, workspace_id = _extract_user_from_request(request)

        response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)

        try:
            from odap.infra.security.unified_audit import log_audit

            status_code = response.status_code

            # HTTP 状态码映射到审计 result_status
            if status_code < 400:
                result_status = "success"
                result_message = f"HTTP {status_code}"
            elif status_code in (401, 403):
                result_status = "denied"
                result_message = f"HTTP {status_code} - {'Unauthorized' if status_code == 401 else 'Forbidden'}"
            else:
                result_status = "failure"
                result_message = f"HTTP {status_code}"

            parts = path.strip("/").split("/")
            api_module = parts[1] if len(parts) > 1 else "unknown"

            if user == "anonymous" and path == "/api/auth/login" and method == "POST":
                user = "login_user"

            action = f"{method.lower()}_{api_module}"
            resource = path

            log_audit(
                action=action,
                resource=resource,
                user=user,
                service=api_module,
                result_status=result_status,
                result_message=result_message,
                details={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else "unknown",
                    "trace_id": trace_id,
                },
                workspace_id=workspace_id,
                duration_ms=duration_ms
            )
        except Exception as e:
            logger.warning(f"Audit log write failed: {e}")

        return response
