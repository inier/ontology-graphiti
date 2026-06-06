"""
租户隔离中间件 (T326)

所有 API 自动注入 ws_id 过滤条件，越权访问返回 403（不泄漏存在性）。

核心能力：
- TenantContext：当前请求的租户上下文
- TenantIsolationGuard：检查资源是否属于当前 ws_id
- inject_ws_id_filter：在 SQL/查询中自动注入 ws_id 条件
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------- 异常 ----------

class TenantAccessDenied(Exception):
    """租户越权访问异常（不泄漏资源存在性）"""
    def __init__(self, resource_type: str, resource_id: Optional[str] = None):
        self.resource_type = resource_type
        self.resource_id = resource_id
        # 不在 message 中包含 resource_id（避免泄漏存在性）
        super().__init__(f"Access denied to {resource_type}")


# ---------- 上下文 ----------

@dataclass
class TenantContext:
    """当前请求的租户上下文"""
    ws_id: str                # 工作空间 ID（必须）
    user_id: Optional[str] = None
    role: Optional[str] = None
    is_admin: bool = False


# ContextVar 用于跨层传递（FastAPI 依赖注入之外的场景）
_tenant_context: ContextVar[Optional[TenantContext]] = ContextVar("tenant_context", default=None)


def set_tenant_context(ctx: TenantContext) -> None:
    """设置当前租户上下文"""
    _tenant_context.set(ctx)


def get_tenant_context() -> Optional[TenantContext]:
    """获取当前租户上下文（可能为 None）"""
    return _tenant_context.get()


def clear_tenant_context() -> None:
    """清除租户上下文"""
    _tenant_context.set(None)


# ---------- 隔离守卫 ----------

class TenantIsolationGuard:
    """租户隔离守卫"""

    @staticmethod
    def check_resource_owner(
        resource_ws_id: Optional[str],
        ctx: Optional[TenantContext] = None,
        resource_type: str = "resource",
        resource_id: Optional[str] = None,
    ) -> None:
        """
        检查资源是否属于当前租户。

        越权时抛出 TenantAccessDenied（不泄漏存在性）。
        """
        ctx = ctx or get_tenant_context()
        if ctx is None:
            logger.warning("No tenant context; defaulting to allow in dev mode")
            return  # 无上下文时开发模式默认放行

        if ctx.is_admin:
            return  # admin 跳过检查

        if resource_ws_id is None:
            # 资源没有 ws_id 标记（孤儿资源）：禁止访问
            logger.warning("Resource %s has no ws_id", resource_type)
            raise TenantAccessDenied(resource_type=resource_type, resource_id=resource_id)

        if resource_ws_id != ctx.ws_id:
            # 越权：不记录 resource_id（不泄漏）
            logger.warning(
                "Tenant access denied: ctx.ws_id=%s resource.ws_id=%s type=%s",
                ctx.ws_id, resource_ws_id, resource_type,
            )
            raise TenantAccessDenied(resource_type=resource_type, resource_id=resource_id)

    @staticmethod
    def inject_ws_id_filter(
        query_params: Dict[str, Any],
        ctx: Optional[TenantContext] = None,
    ) -> Dict[str, Any]:
        """
        自动注入 ws_id 过滤条件到查询参数。

        返回新的 query_params dict（不修改原对象）。
        """
        ctx = ctx or get_tenant_context()
        if ctx is None or ctx.is_admin:
            return query_params
        # 创建副本避免修改原 dict
        return {**query_params, "ws_id": ctx.ws_id}


# ---------- FastAPI 集成（依赖项） ----------

def get_tenant_isolation_guard() -> TenantIsolationGuard:
    """FastAPI 依赖项：注入 TenantIsolationGuard"""
    return TenantIsolationGuard()
