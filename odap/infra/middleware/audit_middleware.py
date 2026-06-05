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


def _extract_user_from_request(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt as pyjwt
            from odap.infra.security.config import security_config
            token = auth_header[7:]
            payload = pyjwt.decode(
                token,
                # P0-8 fix: use lazy-validated method
                security_config.get_jwt_secret(),
                algorithms=[security_config.get_jwt_algorithm()],
                options={"verify_exp": False},
            )
            return payload.get("name") or payload.get("sub") or "authenticated"
        except Exception:
            pass
    return "anonymous"


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
        user = _extract_user_from_request(request)

        response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)

        try:
            from odap.infra.security.unified_audit import log_audit

            status_code = response.status_code

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
                details={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else "unknown",
                    "trace_id": trace_id,
                }
            )
        except Exception as e:
            logger.warning(f"Audit log write failed: {e}")

        return response
