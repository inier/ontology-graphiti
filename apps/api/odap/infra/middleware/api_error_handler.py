"""ApiError 全局处理器 —— 把业务错误翻译为 SPEC-v2 §5 的统一错误契约。

契约：`{error_code, message, detail, trace_id}`（禁止模糊文案，AC-56）。

为什么放在 infra：
    处理器是「表现层适配器」（异常 → HTTP JSON），但它只依赖 common（ApiError / ids），
    infra 在 common 之上、biz 之下，故 `web/app.py` 与 biz 路由均可安全引用；
    若放 web 层则 biz 无法引用（C2 禁止 biz→web）。

trace_id 口径：优先取请求头 `X-Request-ID`（网关/前端透传），否则按 SPEC 生成
`urn:odap:trace:<ulid>`，并回写到响应头便于前端关联。
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from odap.common.api_errors import ApiError
from odap.common.ids import new_trace_id

logger = logging.getLogger("api_error_handler")

TRACE_HEADER = "X-Request-ID"


def resolve_trace_id(request: Request) -> str:
    """取（或生成）本次请求的 trace_id。"""
    incoming = request.headers.get(TRACE_HEADER) or ""
    return incoming.strip() or new_trace_id()


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """ApiError → 统一错误响应。"""
    trace_id = resolve_trace_id(request)
    payload = exc.to_payload(trace_id)
    # 4xx 是预期的业务拒绝，用 warning 级别；5xx 才是需要告警的错误。
    log = logger.warning if exc.status_code < 500 else logger.error
    log(
        "api error: error_code=%s status=%s path=%s trace_id=%s message=%s",
        exc.error_code, exc.status_code, request.url.path, trace_id, exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=payload,
        headers={TRACE_HEADER: trace_id},
    )


def register_api_error_handler(app) -> None:
    """在 FastAPI 应用上注册 ApiError 处理器（由组合根调用，属装配行为）。"""
    app.add_exception_handler(ApiError, api_error_handler)


__all__ = ["api_error_handler", "register_api_error_handler", "resolve_trace_id", "TRACE_HEADER"]
