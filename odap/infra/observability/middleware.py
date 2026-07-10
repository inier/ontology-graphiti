"""OTel Trace Middleware — ADR-064

为每个 HTTP 请求：
  1. 提取或生成 trace_id
  2. 存储到 request.state.trace_id（下游业务可用）
  3. 设置 OTel span attribute
  4. 注入响应头 X-Trace-Id
"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from odap.infra.observability.setup import get_tracer, OBSERVABILITY_AVAILABLE
from odap.infra.observability.metrics import (
    http_request_duration_seconds,
    http_requests_total,
    http_request_errors_total,
)

logger = logging.getLogger("odap.observability.middleware")

_TRACE_HEADER = "X-Trace-Id"
_SPAN_HEADER = "X-Span-Id"


class TraceMiddleware(BaseHTTPMiddleware):
    """OTel 追踪中间件。

    优先级: 请求头 X-Trace-Id（前端透传）> 自动生成 uuid。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. 提取或生成 trace_id
        trace_id = request.headers.get(_TRACE_HEADER) or uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]

        # 2. 存储到 request.state
        request.state.trace_id = trace_id
        request.state.span_id = span_id

        start = time.monotonic()
        status_code = 500
        method = request.method
        endpoint = request.url.path

        # 3. 创建 OTel span
        tracer = get_tracer("odap.http")
        span_name = f"{method} {endpoint}"
        with tracer.start_as_current_span(span_name) as span:
            if span.is_recording():
                span.set_attribute("http.method", method)
                span.set_attribute("http.url", str(request.url))
                span.set_attribute("http.route", endpoint)
                span.set_attribute("trace_id", trace_id)
                span.set_attribute("span_id", span_id)

            # 4. 执行请求
            try:
                response: Response = await call_next(request)
                status_code = response.status_code
            except Exception as exc:
                status_code = 500
                http_request_errors_total.labels(
                    method=method, endpoint=endpoint, error_type=type(exc).__name__
                ).inc()
                raise
            finally:
                elapsed = time.monotonic() - start
                status_str = str(status_code)
                http_request_duration_seconds.labels(
                    method=method, endpoint=endpoint, status_code=status_str
                ).observe(elapsed)
                http_requests_total.labels(
                    method=method, endpoint=endpoint, status_code=status_str
                ).inc()

            if span.is_recording():
                span.set_attribute("http.status_code", status_code)
                if status_code >= 400:
                    span.set_attribute("error", True)

            # 5. 注入响应头
            response.headers[_TRACE_HEADER] = trace_id
            response.headers[_SPAN_HEADER] = span_id

            return response
