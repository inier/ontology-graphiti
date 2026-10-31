"""统一成功响应包络（openapi-v2 `Envelope`）—— 纯函数，common 叶子层。

    成功：{"code": 0, "data": <payload>, "message": ""}
    错误：由 `odap.infra.middleware.api_error_handler` 输出
          {"error_code", "message", "detail", "trace_id"}（SPEC-v2 §5）

两者不混用：错误响应**不**再套 code=0 的包络，避免前端把失败当成功解析。
"""

from __future__ import annotations

from typing import Any


def envelope(data: Any = None, message: str = "") -> dict:
    return {"code": 0, "data": data, "message": message}


def page_envelope(
    items: list,
    total: int,
    page: int,
    limit: int,
    message: str = "",
) -> dict:
    return envelope(
        {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "hasMore": page * limit < total,
        },
        message=message,
    )


__all__ = ["envelope", "page_envelope"]
