"""
性能优化中间件

提供请求压缩、响应时间追踪、慢请求告警和请求ID注入。
"""

import time
import uuid
import gzip
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

logger = logging.getLogger(__name__)

_SLOW_REQUEST_THRESHOLD = 5.0
_EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


class PerformanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXCLUDED_PATHS:
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        duration_ms = round(duration * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        if duration > _SLOW_REQUEST_THRESHOLD:
            logger.warning(
                "Slow request: %s %s took %.2fs (request_id=%s)",
                request.method, request.url.path, duration, request_id,
            )

        return response


class GzipMiddleware(BaseHTTPMiddleware):
    _MIN_SIZE = 500
    _CONTENT_TYPES = {
        "application/json",
        "text/plain",
        "text/html",
        "text/css",
        "application/javascript",
    }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        accept_encoding = request.headers.get("Accept-Encoding", "")
        if "gzip" not in accept_encoding:
            return response

        content_type = response.headers.get("Content-Type", "")
        base_ct = content_type.split(";")[0].strip()
        if base_ct not in self._CONTENT_TYPES:
            return response

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) < self._MIN_SIZE:
            return response

        if isinstance(response, StreamingResponse):
            return response

        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                body += chunk.encode("utf-8")
            else:
                body += chunk

        if len(body) < self._MIN_SIZE:
            new_response = Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            new_response.headers["Content-Length"] = str(len(body))
            return new_response

        compressed = gzip.compress(body)
        new_response = Response(
            content=compressed,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
        new_response.headers["Content-Encoding"] = "gzip"
        new_response.headers["Content-Length"] = str(len(compressed))
        new_response.headers["Vary"] = "Accept-Encoding"

        return new_response
