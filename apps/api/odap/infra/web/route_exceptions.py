"""
Route exception handling helpers (R-P1-001).

This module provides:

1. `standardize_exceptions` decorator — wraps any FastAPI route to:
   - Always re-raise `HTTPException` (preserves 4xx/5xx codes)
   - Convert `ValueError`, `KeyError`, `TypeError`, `LookupError`, `AttributeError`
     to `HTTPException(400, ...)` with a clean message
   - Convert unexpected `Exception` to `HTTPException(500, ...)` with logging
   - Bind structured logging context (route_name, method)

This is the **centralized fix** for the P1 finding "40+ routes without
`except HTTPException: raise`". Instead of editing 40+ routes individually,
we wrap them with a single decorator.

Usage:
    from odap.infra.web.route_exceptions import standardize_exceptions

    @router.get("/foo")
    @standardize_exceptions("foo")
    async def get_foo():
        ...

For routes that have explicit try/except, use `safe_route_execute` directly.
"""
import functools
import logging
from typing import Callable, Any, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ============ Exception type → HTTP status mapping ============

# Domain exceptions that map to 400 (client error, bad request)
CLIENT_ERROR_EXCEPTIONS = (
    ValueError,
    KeyError,
    TypeError,
    LookupError,
    AttributeError,
)

# Domain exceptions that map to 404 (not found)
NOT_FOUND_EXCEPTIONS = ()


def standardize_exceptions(
    route_name: Optional[str] = None,
    *,
    log_unhandled: bool = True,
):
    """
    Decorator that standardizes exception handling for FastAPI routes.

    Args:
        route_name: Friendly name for logging context (default: function name)
        log_unhandled: Whether to log unhandled exceptions (default True)

    Behavior:
        - HTTPException: ALWAYS re-raised (preserves status, detail, headers)
        - ClientError exceptions (ValueError, KeyError, etc.) →
          HTTPException(400, str(e)) with info-level log
        - Other exceptions → HTTPException(500, "Internal server error")
          with exception-level log
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = route_name or func.__name__
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Re-raise FastAPI / Starlette HTTP exceptions as-is
                raise
            except CLIENT_ERROR_EXCEPTIONS as e:
                # Domain "client made a bad request" error
                logger.info(
                    f"Route {name}: client error: {type(e).__name__}: {e}"
                )
                raise HTTPException(status_code=400, detail=str(e)) from e
            except Exception as e:
                # Unhandled — log with full traceback and return 500
                if log_unhandled:
                    logger.exception(
                        f"Route {name}: unhandled exception"
                    )
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error",
                ) from e
        return async_wrapper

    # Handle both @standardize_exceptions and @standardize_exceptions(...)
    if callable(route_name):
        # Used as @standardize_exceptions (no parens)
        func = route_name
        route_name = None
        return decorator(func)

    return decorator


async def safe_route_execute(
    func: Callable,
    *args,
    route_name: Optional[str] = None,
    log_unhandled: bool = True,
    **kwargs,
) -> Any:
    """
    Helper for routes that already have explicit try/except blocks.

    Wrap the body of the try/except in safe_route_execute, then
    handle specific exceptions in the except.

    Example:
        @router.get("/foo")
        async def get_foo():
            try:
                return await safe_route_execute(_do_foo, "foo")
            except HTTPException:
                raise
            except SpecificDomainError as e:
                raise HTTPException(409, str(e))
    """
    name = route_name or getattr(func, "__name__", "route")
    try:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)
    except HTTPException:
        raise
    except CLIENT_ERROR_EXCEPTIONS as e:
        logger.info(f"Route {name}: client error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        if log_unhandled:
            logger.exception(f"Route {name}: unhandled exception")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


# Need this for the iscoroutinefunction check
import asyncio
