"""
XSS / output-encoding middleware for FastAPI.

Scrubs outgoing JSON responses by html-escaping every plain string leaf
value so that stored-XSS payloads injected via text fields cannot execute
when the consuming frontend renders them with dangerouslySetInnerHTML or
legacy jQuery `.html()`.

Design notes
------------
* FastAPI JSONResponse.body is bytes; we re-parse, walk, escape, then
  re-serialize. The cost is paid only on response, which is cheaper than
  per-field input sanitization and avoids any double-encode bugs for
  downstream binary / numeric fields.
* HTML/PlainText responses are escaped via `html.escape`.
* Starlette StreamingResponse / FileResponse are passed through untouched
  (they serve raw bytes / files that callers have explicitly produced).
* Recursion depth is capped at 32 to prevent pathological deeply nested
  payloads from exhausting the Python C stack.
"""

from __future__ import annotations

import html
import json
from typing import Any

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, HTMLResponse, Response


_MAX_DEPTH = 32
_SKIP_HEADERS = frozenset(
    {b"content-length", b"content-type", b"content-encoding"}
)


def _escape_value(obj: Any, depth: int = 0) -> Any:
    if depth > _MAX_DEPTH:
        return None
    if isinstance(obj, dict):
        return {str(k): _escape_value(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_escape_value(v, depth + 1) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_escape_value(v, depth + 1) for v in obj)
    if isinstance(obj, str):
        return html.escape(obj, quote=True)
    return obj


class XSSMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response: Response = await call_next(request)

        if isinstance(response, PlainTextResponse):
            body = b"".join([chunk async for chunk in response.body_iterator])
            escaped = html.escape(body.decode(response.charset or "utf-8"), quote=True)
            return PlainTextResponse(
                content=escaped,
                status_code=response.status_code,
                headers=response.headers,
                media_type=response.media_type,
            )

        if isinstance(response, HTMLResponse):
            body = b"".join([chunk async for chunk in response.body_iterator])
            escaped = html.escape(body.decode(response.charset or "utf-8"), quote=True)
            return HTMLResponse(
                content=escaped,
                status_code=response.status_code,
                headers=response.headers,
                media_type=response.media_type,
            )

        if isinstance(response, JSONResponse):
            raw = b"".join([chunk async for chunk in response.body_iterator])
            if not raw:
                return response
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return response
            cleaned = _escape_value(payload)
            return JSONResponse(
                content=cleaned,
                status_code=response.status_code,
                headers=response.headers,
                media_type=response.media_type,
            )

        return response
