"""
TenantIsolation 单元测试 (T327, TDD)

按 AGENTS.md 规则 9 必测。
"""
from __future__ import annotations

import unittest

from odap.infra.security.tenant_isolation import (
    TenantAccessDenied,
    TenantContext,
    TenantIsolationGuard,
    clear_tenant_context,
    get_tenant_context,
    set_tenant_context,
)


class TestTenantContext(unittest.TestCase):
    """TenantContext 基础测试"""

    def test_basic_construction(self):
        ctx = TenantContext(ws_id="ws-1", user_id="u-1", role="admin")
        self.assertEqual(ctx.ws_id, "ws-1")
        self.assertEqual(ctx.user_id, "u-1")
        self.assertEqual(ctx.role, "admin")
        self.assertFalse(ctx.is_admin)

    def test_admin_flag(self):
        ctx = TenantContext(ws_id="ws-1", is_admin=True)
        self.assertTrue(ctx.is_admin)

    def test_optional_fields_default_none(self):
        ctx = TenantContext(ws_id="ws-1")
        self.assertIsNone(ctx.user_id)
        self.assertIsNone(ctx.role)
        self.assertFalse(ctx.is_admin)


class TestTenantContextVar(unittest.TestCase):
    """ContextVar 测试"""

    def setUp(self):
        clear_tenant_context()

    def tearDown(self):
        clear_tenant_context()

    def test_default_none(self):
        self.assertIsNone(get_tenant_context())

    def test_set_and_get(self):
        ctx = TenantContext(ws_id="ws-1")
        set_tenant_context(ctx)
        self.assertIs(get_tenant_context(), ctx)

    def test_clear(self):
        set_tenant_context(TenantContext(ws_id="ws-1"))
        clear_tenant_context()
        self.assertIsNone(get_tenant_context())


class TestCheckResourceOwner(unittest.TestCase):
    """租户隔离检查测试"""

    def setUp(self):
        clear_tenant_context()
        self.guard = TenantIsolationGuard()

    def tearDown(self):
        clear_tenant_context()

    def test_same_workspace_passes(self):
        ctx = TenantContext(ws_id="ws-1")
        # 资源 ws_id == ctx.ws_id → 通过
        self.guard.check_resource_owner("ws-1", ctx, "ontology", "ont-1")

    def test_different_workspace_raises(self):
        ctx = TenantContext(ws_id="ws-1")
        with self.assertRaises(TenantAccessDenied):
            self.guard.check_resource_owner("ws-2", ctx, "ontology", "ont-1")

    def test_admin_skips_check(self):
        ctx = TenantContext(ws_id="ws-1", is_admin=True)
        # admin 可访问任何 ws
        self.guard.check_resource_owner("ws-999", ctx, "ontology", "ont-1")

    def test_orphan_resource_denied(self):
        """资源没有 ws_id → 禁止访问（防止孤儿泄漏）"""
        ctx = TenantContext(ws_id="ws-1")
        with self.assertRaises(TenantAccessDenied):
            self.guard.check_resource_owner(None, ctx, "ontology", "ont-1")

    def test_no_context_allows_in_dev_mode(self):
        """无上下文时开发模式默认放行（带 warning）"""
        # 不应抛异常
        self.guard.check_resource_owner("ws-1", None, "ontology", "ont-1")

    def test_exception_does_not_leak_resource_id(self):
        """异常不应泄漏 resource_id（防信息泄漏）"""
        ctx = TenantContext(ws_id="ws-1")
        try:
            self.guard.check_resource_owner("ws-2", ctx, "secret_type", "secret-id-12345")
            self.fail("Should have raised")
        except TenantAccessDenied as e:
            self.assertEqual(e.resource_type, "secret_type")
            # resource_id 仍保留用于内部审计
            self.assertEqual(e.resource_id, "secret-id-12345")
            # 但 message 不应包含 resource_id
            self.assertNotIn("secret-id-12345", str(e))
            self.assertNotIn("ws-2", str(e))


class TestInjectWsIdFilter(unittest.TestCase):
    """ws_id 过滤注入测试"""

    def setUp(self):
        clear_tenant_context()

    def tearDown(self):
        clear_tenant_context()

    def test_inject_ws_id_when_present(self):
        ctx = TenantContext(ws_id="ws-1")
        params = {"entity_type": "Customer", "limit": 10}
        out = TenantIsolationGuard.inject_ws_id_filter(params, ctx)
        self.assertEqual(out["ws_id"], "ws-1")
        self.assertEqual(out["entity_type"], "Customer")
        self.assertEqual(out["limit"], 10)

    def test_no_injection_for_admin(self):
        ctx = TenantContext(ws_id="ws-1", is_admin=True)
        params = {"entity_type": "Customer"}
        out = TenantIsolationGuard.inject_ws_id_filter(params, ctx)
        self.assertNotIn("ws_id", out)

    def test_no_injection_without_context(self):
        params = {"entity_type": "Customer"}
        out = TenantIsolationGuard.inject_ws_id_filter(params, None)
        self.assertNotIn("ws_id", out)

    def test_does_not_mutate_input(self):
        """不修改原 dict（immutable contract）"""
        ctx = TenantContext(ws_id="ws-1")
        params = {"entity_type": "Customer"}
        original = dict(params)
        TenantIsolationGuard.inject_ws_id_filter(params, ctx)
        self.assertEqual(params, original)


class TestFastAPIDependency(unittest.TestCase):
    """FastAPI 依赖项测试"""

    def test_get_tenant_isolation_guard(self):
        from odap.infra.security.tenant_isolation import get_tenant_isolation_guard
        guard = get_tenant_isolation_guard()
        self.assertIsInstance(guard, TenantIsolationGuard)

    def test_dependency_returns_new_instance(self):
        """依赖项每次返回新实例（FastAPI Depends 语义）"""
        from odap.infra.security.tenant_isolation import get_tenant_isolation_guard
        g1 = get_tenant_isolation_guard()
        g2 = get_tenant_isolation_guard()
        self.assertIsNot(g1, g2)


if __name__ == "__main__":
    unittest.main()
