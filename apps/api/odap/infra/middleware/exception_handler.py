"""全局异常处理中间件"""

import logging
import os
import traceback
from typing import Union

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("exception_handler")


def _is_production_env() -> bool:
    """是否为生产环境（决定是否屏蔽内部异常详情）。"""
    return os.environ.get("ENV", os.environ.get("ENVIRONMENT", "")).lower() in (
        "production", "prod", "live",
    )


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件

    统一处理所有未捕获的异常，返回标准化的错误响应格式。

    P0-M2 整改：500 错误不再向客户端泄漏 str(exc)（可能含连接串/路径/密钥片段）。
    - ValueError/PermissionError 仍返回简短描述（业务校验错误，可读性必要）
    - 其他未捕获异常：生产环境返回 generic "Internal server error"，
      详情仅入日志；开发环境保留 type+message 便于调试
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            raise
        except Exception as exc:
            return self._handle_exception(request, exc)

    def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID", "unknown")
        is_prod = _is_production_env()

        # ValueError: 业务校验错误，返回简短描述（不含堆栈）
        if isinstance(exc, ValueError):
            logger.warning(
                f"[{request_id}] Validation error on {request.url.path}: {exc}"
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "type": exc.__class__.__name__,
                        "message": str(exc)[:500],  # 截断防超长
                        "request_id": request_id,
                        "path": str(request.url.path),
                    }
                },
            )

        # PermissionError: 权限错误
        if isinstance(exc, PermissionError):
            logger.warning(
                f"[{request_id}] Permission denied on {request.url.path}: {exc}"
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "type": exc.__class__.__name__,
                        "message": "Permission denied",
                        "request_id": request_id,
                        "path": str(request.url.path),
                    }
                },
            )

        # 其他未捕获异常：详情入日志，客户端只看 generic 文案（生产）
        logger.error(
            f"[{request_id}] Unhandled exception on {request.url.path}: {exc}\n"
            f"Traceback: {traceback.format_exc()}"
        )

        if is_prod:
            # 生产：完全不泄漏内部信息
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "type": "InternalServerError",
                        "message": "Internal server error",
                        "request_id": request_id,
                        "path": str(request.url.path),
                    }
                },
            )
        else:
            # 开发：保留 type + 截断的 message 便于调试
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "type": exc.__class__.__name__,
                        "message": str(exc)[:500],
                        "request_id": request_id,
                        "path": str(request.url.path),
                    }
                },
            )


def register_exception_handler(app: FastAPI) -> None:
    """注册全局异常处理中间件"""
    app.add_middleware(ExceptionHandlerMiddleware)


class APIError(Exception):
    """自定义 API 错误类型"""

    def __init__(
        self,
        message: str,
        error_code: str = "API_ERROR",
        status_code: int = 500,
        details: Union[dict, None] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        result = {
            "error": {
                "code": self.error_code,
                "message": self.message
            }
        }
        if self.details:
            result["error"]["details"] = self.details
        return result


class ValidationError(APIError):
    """验证错误"""

    def __init__(self, message: str, details: Union[dict, None] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )


class NotFoundError(APIError):
    """资源不存在错误"""

    def __init__(self, message: str, details: Union[dict, None] = None):
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=details
        )


class ConflictError(APIError):
    """资源冲突错误"""

    def __init__(self, message: str, details: Union[dict, None] = None):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=409,
            details=details
        )
