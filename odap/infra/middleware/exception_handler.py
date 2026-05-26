"""全局异常处理中间件"""

import logging
import traceback
from typing import Union

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("exception_handler")


class ExceptionHandlerMiddleware(BaseHTTPMiddleware):
    """全局异常处理中间件

    统一处理所有未捕获的异常，返回标准化的错误响应格式
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

        error_response = {
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "request_id": request_id,
                "path": str(request.url.path)
            }
        }

        if isinstance(exc, ValueError):
            logger.warning(
                f"[{request_id}] Validation error on {request.url.path}: {exc}"
            )
            return JSONResponse(
                status_code=400,
                content=error_response
            )

        if isinstance(exc, PermissionError):
            logger.warning(
                f"[{request_id}] Permission denied on {request.url.path}: {exc}"
            )
            return JSONResponse(
                status_code=403,
                content=error_response
            )

        logger.error(
            f"[{request_id}] Unhandled exception on {request.url.path}: {exc}\n"
            f"Traceback: {traceback.format_exc()}"
        )

        return JSONResponse(
            status_code=500,
            content=error_response
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
