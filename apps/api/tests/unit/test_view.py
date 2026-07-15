"""Object View - 单元测试 (T412)

覆盖：
- ObjectView / ViewPermission 领域模型
- SQLiteViewStorage CRUD + JSON 序列化（用 tmp_path 真实 DB）
- ViewRepositoryImpl 9 个方法
- ViewQueryEngineImpl:
  - 字段投影 (白名单)
  - 过滤 (6 操作符: eq/ne/gt/lt/in/contains)
  - 排序 (asc/desc)
  - 行限制 + truncated 标志
  - 脱敏: REMOVE / mask_email / mask_ssn / 自定义 pattern
  - OPA 拒绝路径 (抛出 AccessDenied)
- ViewService 编排层
- FastAPI 路由 HTTP 状态码
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from odap.biz.core.ontology.view.api.routes import router as view_router
from odap.biz.core.ontology.view.impl import (
    AccessDeniedError,
    ViewQueryEngineImpl,
    ViewRepositoryImpl,
)
from odap.biz.core.ontology.view.interfaces import (
    ViewQueryContext,
    ViewQueryResult,
)
from odap.biz.core.ontology.view.models import ObjectView, ViewPermission
from odap.biz.core.ontology.view.services import ViewService
from odap.biz.core.ontology.view.storage import SQLiteViewStorage


# ============================================================
# 工厂函数
# ============================================================


def _make_view(**overrides) -> ObjectView:
    """构造测试用 ObjectView"""
    defaults = dict(
        name="customer-view",
        description="test view",
        base_type_id="Customer",
        role="analyst",
        projected_properties=["id", "name", "email"],
        filters={"status": {"eq": "active"}},
        row_limit=10,
        sort_order=[{"property": "name", "direction": "asc"}],
        enabled=True,
        created_by="tester",
    )
    defaults.update(overrides)
    return ObjectView(**defaults)


def _make_perm(view_id: str, role: str = "analyst", **overrides) -> ViewPermission:
    """构造测试用 ViewPermission"""
    defaults = dict(
        view_id=view_id,
        role=role,
        can_export=True,
        can_share=False,
        redaction_rules={"$.ssn": "***-**-####"},
    )
    defaults.update(overrides)
    return ViewPermission(**defaults)


def _sample_data() -> List[Dict[str, Any]]:
    """构造测试用数据集"""
    return [
        {"id": "1", "name": "Alice", "email": "alice@example.com", "ssn": "123-45-6789", "status": "active", "salary": 100000},
        {"id": "2", "name": "Bob", "email": "bob@example.com", "ssn": "987-65-4321", "status": "active", "salary": 80000},
        {"id": "3", "name": "Carol", "email": "carol@example.com", "ssn": "555-44-3333", "status": "inactive", "salary": 120000},
    ]


# ============================================================
# 1. ObjectView 模型
# ============================================================


class TestObjectViewModel(unittest.TestCase):
    """ObjectView 必填字段、默认值、UUID、容器 default_factory"""

    def test_required_fields_minimal(self):
        view = ObjectView(name="v1", base_type_id="T", role="r")
        self.assertEqual(view.name, "v1")
        self.assertEqual(view.base_type_id, "T")
        self.assertEqual(view.role, "r")
        self.assertEqual(view.description, "")
        self.assertEqual(view.row_limit, 100)
        self.assertTrue(view.enabled)
        self.assertEqual(view.projected_properties, [])
        self.assertEqual(view.filters, {})
        self.assertEqual(view.sort_order, [])

    def test_default_factory_container_fields(self):
        """容器字段必须用 default_factory（规则 5）"""
        v1 = ObjectView(name="a", base_type_id="T", role="r")
        v1.projected_properties.append("x")
        v1.filters["k"] = "v"
        v2 = ObjectView(name="b", base_type_id="T", role="r")
        self.assertEqual(v2.projected_properties, [])
        self.assertEqual(v2.filters, {})

    def test_uuid_auto_generated_unique(self):
        a = ObjectView(name="a", base_type_id="T", role="r")
        b = ObjectView(name="b", base_type_id="T", role="r")
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(len(a.id), 36)

    def test_created_updated_auto_set(self):
        v = ObjectView(name="a", base_type_id="T", role="r")
        self.assertIsInstance(v.created_at, datetime)
        self.assertIsInstance(v.updated_at, datetime)

    def test_row_limit_default(self):
        v = ObjectView(name="a", base_type_id="T", role="r")
        self.assertEqual(v.row_limit, 100)

    def test_created_by_default_system(self):
        v = ObjectView(name="a", base_type_id="T", role="r")
        self.assertEqual(v.created_by, "system")

    def test_enabled_default_true(self):
        v = ObjectView(name="a", base_type_id="T", role="r")
        self.assertTrue(v.enabled)


# ============================================================
# 2. ViewPermission 模型
# ============================================================


class TestViewPermissionModel(unittest.TestCase):
    """ViewPermission 必填字段、UUID、容器 default_factory"""

    def test_required_fields_minimal(self):
        p = ViewPermission(view_id="v1", role="r")
        self.assertEqual(p.view_id, "v1")
        self.assertEqual(p.role, "r")
        self.assertFalse(p.can_export)
        self.assertFalse(p.can_share)
        self.assertEqual(p.redaction_rules, {})

    def test_default_factory_redaction_rules(self):
        p1 = ViewPermission(view_id="v1", role="r")
        p1.redaction_rules["k"] = "v"
        p2 = ViewPermission(view_id="v1", role="r")
        self.assertNotIn("k", p2.redaction_rules)

    def test_uuid_auto_unique(self):
        a = ViewPermission(view_id="v1", role="r")
        b = ViewPermission(view_id="v1", role="r")
        self.assertNotEqual(a.id, b.id)

    def test_can_export_share_flags(self):
        p = ViewPermission(view_id="v", role="r", can_export=True, can_share=True)
        self.assertTrue(p.can_export)
        self.assertTrue(p.can_share)

    def test_created_at_default_now(self):
        p = ViewPermission(view_id="v", role="r")
        self.assertIsInstance(p.created_at, datetime)


# ============================================================
# 3. SQLite Storage
# ============================================================


class TestSQLiteViewStorage(unittest.TestCase):
    """SQLiteViewStorage CRUD + JSON 序列化（tmp_path 真实 DB）"""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.db_path = f"{tmp}/view.db"
        self.storage = SQLiteViewStorage(db_path=self.db_path)

    def _view_dict(self, **overrides) -> Dict[str, Any]:
        defaults = dict(
            id="v-1",
            name="n1",
            description="d1",
            base_type_id="Customer",
            role="analyst",
            projected_properties=["id", "name"],
            filters={"status": "active"},
            row_limit=50,
            sort_order=[{"property": "name", "direction": "asc"}],
            enabled=True,
            created_by="tester",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        defaults.update(overrides)
        return defaults

    def _perm_dict(self, **overrides) -> Dict[str, Any]:
        defaults = dict(
            id="p-1",
            view_id="v-1",
            role="analyst",
            can_export=1,
            can_share=0,
            redaction_rules={"$.ssn": "***-**-####"},
            created_at=datetime.now().isoformat(),
        )
        defaults.update(overrides)
        return defaults

    def test_save_and_get_view(self):
        self.storage.save_view(self._view_dict())
        row = self.storage.get_view("v-1")
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "n1")
        self.assertEqual(row["base_type_id"], "Customer")
        self.assertEqual(row["row_limit"], 50)
        self.assertEqual(row["projected_properties"], ["id", "name"])
        self.assertEqual(row["filters"], {"status": "active"})

    def test_get_view_not_found(self):
        self.assertIsNone(self.storage.get_view("nonexistent"))

    def test_list_views(self):
        self.storage.save_view(self._view_dict(id="v-1"))
        self.storage.save_view(self._view_dict(id="v-2"))
        rows = self.storage.list_views()
        self.assertEqual(len(rows), 2)

    def test_list_views_by_base_type(self):
        self.storage.save_view(self._view_dict(id="v-1", base_type_id="Customer"))
        self.storage.save_view(self._view_dict(id="v-2", base_type_id="Order"))
        rows = self.storage.list_views_by_base_type("Customer")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["base_type_id"], "Customer")

    def test_list_views_by_role(self):
        self.storage.save_view(self._view_dict(id="v-1", role="analyst"))
        self.storage.save_view(self._view_dict(id="v-2", role="admin"))
        rows = self.storage.list_views_by_role("analyst")
        self.assertEqual(len(rows), 1)

    def test_delete_view_cascades_permissions(self):
        self.storage.save_view(self._view_dict(id="v-1"))
        self.storage.save_permission(self._perm_dict(view_id="v-1"))
        self.assertTrue(self.storage.delete_view("v-1"))
        self.assertIsNone(self.storage.get_view("v-1"))
        self.assertEqual(self.storage.list_permissions("v-1"), [])

    def test_delete_view_not_found(self):
        self.assertFalse(self.storage.delete_view("nonexistent"))

    def test_save_and_list_permission(self):
        self.storage.save_view(self._view_dict(id="v-1"))
        self.storage.save_permission(self._perm_dict(view_id="v-1"))
        perms = self.storage.list_permissions("v-1")
        self.assertEqual(len(perms), 1)
        self.assertEqual(perms[0]["redaction_rules"], {"$.ssn": "***-**-####"})

    def test_delete_permission(self):
        self.storage.save_view(self._view_dict(id="v-1"))
        self.storage.save_permission(self._perm_dict(id="p-1", view_id="v-1"))
        self.assertTrue(self.storage.delete_permission("p-1"))
        self.assertFalse(self.storage.delete_permission("p-1"))

    def test_view_unique_id_pk(self):
        """view id 是主键：upsert 同 id 会覆盖"""
        self.storage.save_view(self._view_dict(id="v-1", name="n1"))
        self.storage.save_view(self._view_dict(id="v-1", name="n1-updated"))
        row = self.storage.get_view("v-1")
        self.assertEqual(row["name"], "n1-updated")
        self.assertEqual(len(self.storage.list_views()), 1)

    def test_invalid_json_safely_handled(self):
        """非法 JSON 应回退到 default"""
        conn = None
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO object_views (id, name, base_type_id, role, projected_properties, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("v-bad", "n", "T", "r", "not-json", "", ""),
            )
            conn.commit()
        finally:
            conn.close()
        row = self.storage.get_view("v-bad")
        self.assertEqual(row["projected_properties"], [])


# ============================================================
# 4. ViewRepository
# ============================================================


class TestViewRepository(unittest.TestCase):
    """ViewRepositoryImpl 9 个方法"""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.db_path = f"{tmp}/view_repo.db"
        self.storage = SQLiteViewStorage(db_path=self.db_path)
        self.repo = ViewRepositoryImpl(storage=self.storage)

    def test_save_and_get_view(self):
        v = _make_view()
        saved = self.repo.save(v)
        self.assertEqual(saved.id, v.id)
        loaded = self.repo.get(v.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "customer-view")

    def test_list_views(self):
        self.repo.save(_make_view(name="a"))
        self.repo.save(_make_view(name="b"))
        self.assertEqual(len(self.repo.list()), 2)

    def test_list_by_base_type(self):
        self.repo.save(_make_view(name="a", base_type_id="Customer"))
        self.repo.save(_make_view(name="b", base_type_id="Order"))
        self.assertEqual(len(self.repo.list_by_base_type("Customer")), 1)

    def test_list_by_role(self):
        self.repo.save(_make_view(name="a", role="analyst"))
        self.repo.save(_make_view(name="b", role="admin"))
        self.assertEqual(len(self.repo.list_by_role("analyst")), 1)

    def test_delete_view(self):
        v = _make_view()
        self.repo.save(v)
        self.assertTrue(self.repo.delete(v.id))
        self.assertIsNone(self.repo.get(v.id))

    def test_save_permission(self):
        v = _make_view()
        self.repo.save(v)
        perm = _make_perm(view_id=v.id)
        self.repo.save_permission(perm)
        perms = self.repo.get_permissions(v.id)
        self.assertEqual(len(perms), 1)
        self.assertEqual(perms[0].role, "analyst")

    def test_delete_permission(self):
        v = _make_view()
        self.repo.save(v)
        perm = _make_perm(view_id=v.id)
        self.repo.save_permission(perm)
        self.assertTrue(self.repo.delete_permission(perm.id))
        self.assertFalse(self.repo.delete_permission(perm.id))


# ============================================================
# 5. ViewQueryEngine
# ============================================================


class TestViewQueryEngine(unittest.TestCase):
    """ViewQueryEngineImpl 完整流水线"""

    def setUp(self):
        self.data = _sample_data()
        self.engine = ViewQueryEngineImpl(
            opa_check=lambda v, c: True,
            data_loader=lambda bt: self.data,
        )
        self.ctx = ViewQueryContext(user_id="u1", ws_id="ws1", role="analyst")

    def test_projection_whitelist(self):
        """字段投影：只保留 projected_properties 中声明的属性"""
        view = _make_view(
            projected_properties=["id", "name"],
            filters={},
        )
        result = self.engine.query(view, self.ctx)
        self.assertEqual(len(result.rows), 3)
        for r in result.rows:
            self.assertEqual(set(r.keys()), {"id", "name"})

    def test_projection_empty_keeps_all(self):
        """projected_properties 为空时保留所有字段"""
        view = _make_view(projected_properties=[], filters={})
        result = self.engine.query(view, self.ctx)
        self.assertIn("ssn", result.rows[0])

    def test_filter_eq(self):
        view = _make_view(
            projected_properties=["id", "name", "status"],
            filters={"status": {"eq": "active"}},
        )
        result = self.engine.query(view, self.ctx)
        self.assertEqual(len(result.rows), 2)
        for r in result.rows:
            self.assertEqual(r["status"], "active")

    def test_filter_ne(self):
        view = _make_view(
            projected_properties=["id", "name", "status"],
            filters={"status": {"ne": "active"}},
        )
        result = self.engine.query(view, self.ctx)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0]["status"], "inactive")

    def test_filter_gt(self):
        view = _make_view(
            projected_properties=["id", "salary"],
            filters={"salary": {"gt": 90000}},
        )
        result = self.engine.query(view, self.ctx)
        salaries = [r["salary"] for r in result.rows]
        self.assertEqual(sorted(salaries), [100000, 120000])

    def test_filter_lt(self):
        view = _make_view(
            projected_properties=["id", "salary"],
            filters={"salary": {"lt": 90000}},
        )
        result = self.engine.query(view, self.ctx)
        self.assertEqual([r["salary"] for r in result.rows], [80000])

    def test_filter_in(self):
        view = _make_view(
            projected_properties=["id", "name"],
            filters={"name": {"in": ["Alice", "Bob"]}},
        )
        result = self.engine.query(view, self.ctx)
        names = sorted(r["name"] for r in result.rows)
        self.assertEqual(names, ["Alice", "Bob"])

    def test_filter_contains(self):
        view = _make_view(
            projected_properties=["id", "email"],
            filters={"email": {"contains": "example.com"}},
        )
        result = self.engine.query(view, self.ctx)
        self.assertEqual(len(result.rows), 3)

    def test_sort_asc(self):
        view = _make_view(
            projected_properties=["id", "name"],
            sort_order=[{"property": "name", "direction": "asc"}],
            filters={},
        )
        result = self.engine.query(view, self.ctx)
        names = [r["name"] for r in result.rows]
        self.assertEqual(names, sorted(names))

    def test_sort_desc(self):
        view = _make_view(
            projected_properties=["id", "salary"],
            sort_order=[{"property": "salary", "direction": "desc"}],
            filters={},
        )
        result = self.engine.query(view, self.ctx)
        salaries = [r["salary"] for r in result.rows]
        self.assertEqual(salaries, sorted(salaries, reverse=True))

    def test_row_limit_and_truncated(self):
        view = _make_view(row_limit=2, filters={})
        result = self.engine.query(view, self.ctx)
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.total_count, 3)
        self.assertTrue(result.truncated)

    def test_row_limit_not_truncated(self):
        view = _make_view(row_limit=10, filters={})
        result = self.engine.query(view, self.ctx)
        self.assertEqual(len(result.rows), 3)
        self.assertEqual(result.total_count, 3)
        self.assertFalse(result.truncated)

    def test_redaction_remove(self):
        view = _make_view(
            projected_properties=["id", "salary", "name"],
            filters={},
        )
        self.engine.set_permission_provider(
            lambda vid, role: {"redaction_rules": {"salary": "REMOVE"}}
        )
        result = self.engine.query(view, self.ctx)
        for r in result.rows:
            self.assertNotIn("salary", r)

    def test_redaction_mask_email(self):
        view = _make_view(
            projected_properties=["id", "email"],
            filters={},
        )
        self.engine.set_permission_provider(
            lambda vid, role: {"redaction_rules": {"email": "mask_email"}}
        )
        result = self.engine.query(view, self.ctx)
        for r in result.rows:
            self.assertIn("***@", r["email"])
            self.assertNotIn("alice", r["email"])

    def test_redaction_mask_ssn(self):
        view = _make_view(
            projected_properties=["id", "ssn"],
            filters={},
        )
        self.engine.set_permission_provider(
            lambda vid, role: {"redaction_rules": {"ssn": "mask_ssn"}}
        )
        result = self.engine.query(view, self.ctx)
        for r in result.rows:
            self.assertTrue(r["ssn"].startswith("***-**-"))
            # 后 4 位应保留
            self.assertIn(r["ssn"][-4:], ["6789", "4321", "3333"])

    def test_redaction_custom_pattern(self):
        view = _make_view(
            projected_properties=["id", "name"],
            filters={},
        )
        self.engine.set_permission_provider(
            lambda vid, role: {"redaction_rules": {"name": "***-**-####"}}
        )
        result = self.engine.query(view, self.ctx)
        # Alice → A***-**-lice (5 字符 pattern 替换 5 字符)
        # pattern 比 name 短时取 prefix
        for r in result.rows:
            self.assertNotEqual(r["name"], "Alice")

    def test_opa_denied_raises_access_denied(self):
        view = _make_view()
        engine = ViewQueryEngineImpl(
            opa_check=lambda v, c: False,
            data_loader=lambda bt: self.data,
        )
        with self.assertRaises(AccessDeniedError):
            engine.query(view, self.ctx)

    def test_access_denied_is_permission_error(self):
        self.assertTrue(issubclass(AccessDeniedError, PermissionError))

    def test_default_opa_check_fails_closed(self):
        engine = ViewQueryEngineImpl(data_loader=lambda bt: self.data)
        with self.assertRaises(AccessDeniedError):
            engine.query(_make_view(), self.ctx)

    def test_default_data_loader_returns_empty(self):
        engine = ViewQueryEngineImpl(opa_check=lambda v, c: True)
        result = engine.query(_make_view(row_limit=10), self.ctx)
        self.assertEqual(result.rows, [])
        self.assertEqual(result.total_count, 0)
        self.assertFalse(result.truncated)

    def test_no_redaction_rules_returns_raw(self):
        view = _make_view(projected_properties=["id", "name"], filters={})
        result = self.engine.query(view, self.ctx)
        self.assertEqual(result.rows[0]["name"], "Alice")


# ============================================================
# 6. ViewService 编排层
# ============================================================


class TestViewService(unittest.TestCase):
    """ViewService 编排层"""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.db_path = f"{tmp}/view_svc.db"
        self.storage = SQLiteViewStorage(db_path=self.db_path)
        self.service = ViewService(storage=self.storage)
        self.service.set_opa_check(lambda v, c: True)
        self.service.set_data_loader(lambda bt: _sample_data())

    def test_create_view_success(self):
        result = self.service.create_view({
            "name": "v1",
            "base_type_id": "Customer",
            "role": "analyst",
            "projected_properties": ["id", "name"],
        })
        self.assertNotIn("status", result)
        self.assertEqual(result["name"], "v1")
        self.assertEqual(result["role"], "analyst")

    def test_create_view_missing_name(self):
        result = self.service.create_view({"base_type_id": "T", "role": "r"})
        self.assertEqual(result["status"], "error")

    def test_create_view_missing_base_type_id(self):
        result = self.service.create_view({"name": "v", "role": "r"})
        self.assertEqual(result["status"], "error")

    def test_create_view_missing_role(self):
        result = self.service.create_view({"name": "v", "base_type_id": "T"})
        self.assertEqual(result["status"], "error")

    def test_get_view_not_found(self):
        result = self.service.get_view("nonexistent")
        self.assertEqual(result["status"], "error")

    def test_list_views_filter_by_base_type(self):
        self.service.create_view({"name": "a", "base_type_id": "Customer", "role": "r"})
        self.service.create_view({"name": "b", "base_type_id": "Order", "role": "r"})
        result = self.service.list_views(base_type="Customer")
        self.assertEqual(result["count"], 1)

    def test_list_views_filter_by_role(self):
        self.service.create_view({"name": "a", "base_type_id": "T", "role": "analyst"})
        self.service.create_view({"name": "b", "base_type_id": "T", "role": "admin"})
        result = self.service.list_views(role="admin")
        self.assertEqual(result["count"], 1)

    def test_update_view(self):
        created = self.service.create_view({
            "name": "v1", "base_type_id": "T", "role": "r",
        })
        vid = created["id"]
        result = self.service.update_view(vid, {"description": "updated"})
        self.assertEqual(result["description"], "updated")
        self.assertEqual(result["name"], "v1")

    def test_update_view_not_found(self):
        result = self.service.update_view("nonexistent", {"name": "x"})
        self.assertEqual(result["status"], "error")

    def test_delete_view(self):
        created = self.service.create_view({
            "name": "v1", "base_type_id": "T", "role": "r",
        })
        result = self.service.delete_view(created["id"])
        self.assertEqual(result["deleted"], True)
        self.assertEqual(self.service.get_view(created["id"])["status"], "error")

    def test_delete_view_not_found(self):
        result = self.service.delete_view("nonexistent")
        self.assertEqual(result["status"], "error")

    def test_query_view_basic(self):
        created = self.service.create_view({
            "name": "v1",
            "base_type_id": "Customer",
            "role": "analyst",
            "projected_properties": ["id", "name"],
            "filters": {"status": {"eq": "active"}},
            "row_limit": 10,
        })
        result = self.service.query_view(created["id"], {
            "user_id": "u1", "ws_id": "ws1", "role": "analyst",
        })
        self.assertEqual(result["total_count"], 2)
        self.assertFalse(result["truncated"])

    def test_query_view_opa_denied(self):
        self.service.set_opa_check(lambda v, c: False)
        created = self.service.create_view({
            "name": "v1", "base_type_id": "T", "role": "r",
        })
        result = self.service.query_view(created["id"], {
            "user_id": "u1", "ws_id": "ws1", "role": "r",
        })
        self.assertEqual(result["status"], "error")
        self.assertIn("denied", result["message"].lower())

    def test_query_view_not_found(self):
        result = self.service.query_view("nonexistent", {
            "user_id": "u1", "ws_id": "ws1", "role": "r",
        })
        self.assertEqual(result["status"], "error")

    def test_attach_permission(self):
        created = self.service.create_view({
            "name": "v1", "base_type_id": "T", "role": "analyst",
        })
        result = self.service.attach_permission(created["id"], {
            "role": "guest",
            "can_export": False,
            "redaction_rules": {"$.email": "mask_email"},
        })
        self.assertNotIn("status", result)
        self.assertEqual(result["role"], "guest")

    def test_attach_permission_view_not_found(self):
        result = self.service.attach_permission("nonexistent", {"role": "r"})
        self.assertEqual(result["status"], "error")

    def test_attach_permission_missing_role(self):
        created = self.service.create_view({
            "name": "v1", "base_type_id": "T", "role": "r",
        })
        result = self.service.attach_permission(created["id"], {})
        self.assertEqual(result["status"], "error")

    def test_list_permissions(self):
        created = self.service.create_view({
            "name": "v1", "base_type_id": "T", "role": "r",
        })
        self.service.attach_permission(created["id"], {"role": "analyst"})
        self.service.attach_permission(created["id"], {"role": "admin"})
        result = self.service.get_permissions(created["id"])
        self.assertEqual(result["count"], 2)

    def test_detach_permission(self):
        created = self.service.create_view({
            "name": "v1", "base_type_id": "T", "role": "r",
        })
        attached = self.service.attach_permission(created["id"], {"role": "r"})
        result = self.service.detach_permission(attached["id"])
        self.assertEqual(result["deleted"], True)

    def test_detach_permission_not_found(self):
        result = self.service.detach_permission("nonexistent")
        self.assertEqual(result["status"], "error")


# ============================================================
# 7. View API 路由
# ============================================================


class TestViewRoutes(unittest.TestCase):
    """FastAPI 路由 HTTP 状态码"""

    def setUp(self):
        from fastapi import FastAPI

        # 用 MagicMock 替换 view_service 单例以隔离真实存储
        self.mock_service = MagicMock()
        from odap.biz.core.ontology.view.api import routes as routes_module
        self._orig_service = routes_module.view_service
        routes_module.view_service = self.mock_service
        self.app = FastAPI()
        self.app.include_router(view_router)
        self.client = TestClient(self.app)

    def tearDown(self):
        from odap.biz.core.ontology.view.api import routes as routes_module
        routes_module.view_service = self._orig_service

    def test_create_view_201_success(self):
        self.mock_service.create_view.return_value = {
            "id": "v1", "name": "v1",
            "base_type_id": "T", "role": "r",
            "description": "", "projected_properties": [],
            "filters": {}, "row_limit": 100,
            "sort_order": [], "enabled": True,
            "created_by": "system",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        r = self.client.post("/api/ontology/views", json={
            "name": "v1", "base_type_id": "T", "role": "r",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], "v1")

    def test_create_view_400(self):
        """服务层返回 error 时，路由层翻译为 400"""
        # 发送合法 Pydantic body，但 service 内部校验失败
        self.mock_service.create_view.return_value = {
            "status": "error", "message": "row_limit must be >= 0",
        }
        r = self.client.post("/api/ontology/views", json={
            "name": "v1", "base_type_id": "T", "role": "r",
        })
        self.assertEqual(r.status_code, 400)

    def test_list_views(self):
        self.mock_service.list_views.return_value = {
            "views": [], "count": 0,
        }
        r = self.client.get("/api/ontology/views")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 0)

    def test_get_view_200(self):
        self.mock_service.get_view.return_value = {
            "id": "v1", "name": "v1",
            "base_type_id": "T", "role": "r",
            "description": "", "projected_properties": [],
            "filters": {}, "row_limit": 100,
            "sort_order": [], "enabled": True,
            "created_by": "system",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        r = self.client.get("/api/ontology/views/v1")
        self.assertEqual(r.status_code, 200)

    def test_get_view_404(self):
        self.mock_service.get_view.return_value = {
            "status": "error", "message": "view not found",
        }
        r = self.client.get("/api/ontology/views/nonexistent")
        self.assertEqual(r.status_code, 404)

    def test_update_view_200(self):
        self.mock_service.update_view.return_value = {
            "id": "v1", "name": "v1-updated",
            "base_type_id": "T", "role": "r",
            "description": "", "projected_properties": [],
            "filters": {}, "row_limit": 100,
            "sort_order": [], "enabled": True,
            "created_by": "system",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        r = self.client.put("/api/ontology/views/v1", json={"name": "v1-updated"})
        self.assertEqual(r.status_code, 200)

    def test_update_view_404(self):
        self.mock_service.update_view.return_value = {
            "status": "error", "message": "view not found: x",
        }
        r = self.client.put("/api/ontology/views/x", json={"name": "y"})
        self.assertEqual(r.status_code, 404)

    def test_delete_view_200(self):
        self.mock_service.delete_view.return_value = {
            "view_id": "v1", "deleted": True,
        }
        r = self.client.delete("/api/ontology/views/v1")
        self.assertEqual(r.status_code, 200)

    def test_delete_view_404(self):
        self.mock_service.delete_view.return_value = {
            "status": "error", "message": "view not found",
        }
        r = self.client.delete("/api/ontology/views/nonexistent")
        self.assertEqual(r.status_code, 404)

    def test_query_view_200(self):
        self.mock_service.query_view.return_value = {
            "rows": [{"id": "1"}], "total_count": 1, "truncated": False,
        }
        r = self.client.post("/api/ontology/views/v1/query", json={
            "user_id": "u", "ws_id": "ws", "role": "r",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["total_count"], 1)

    def test_query_view_403_opa_denied(self):
        self.mock_service.query_view.return_value = {
            "status": "error",
            "message": "OPA denied access for role=r",
        }
        r = self.client.post("/api/ontology/views/v1/query", json={
            "user_id": "u", "ws_id": "ws", "role": "r",
        })
        self.assertEqual(r.status_code, 403)

    def test_query_view_404(self):
        self.mock_service.query_view.return_value = {
            "status": "error", "message": "view not found",
        }
        r = self.client.post("/api/ontology/views/nonexistent/query", json={
            "user_id": "u", "ws_id": "ws", "role": "r",
        })
        self.assertEqual(r.status_code, 404)

    def test_attach_permission_200(self):
        self.mock_service.attach_permission.return_value = {
            "id": "p1", "view_id": "v1", "role": "r",
            "can_export": False, "can_share": False,
            "redaction_rules": {}, "created_at": "2024-01-01T00:00:00",
        }
        self.mock_service.get_permissions.return_value = {
            "permissions": [{
                "id": "p1", "view_id": "v1", "role": "r",
                "can_export": False, "can_share": False,
                "redaction_rules": {}, "created_at": "2024-01-01T00:00:00",
            }],
            "count": 1,
        }
        r = self.client.post("/api/ontology/views/v1/permissions", json={"role": "r"})
        self.assertEqual(r.status_code, 200)

    def test_attach_permission_404(self):
        self.mock_service.attach_permission.return_value = {
            "status": "error", "message": "view not found: x",
        }
        r = self.client.post("/api/ontology/views/x/permissions", json={"role": "r"})
        self.assertEqual(r.status_code, 404)

    def test_list_permissions_200(self):
        self.mock_service.get_permissions.return_value = {
            "permissions": [], "count": 0,
        }
        r = self.client.get("/api/ontology/views/v1/permissions")
        self.assertEqual(r.status_code, 200)

    def test_detach_permission_200(self):
        self.mock_service.detach_permission.return_value = {
            "perm_id": "p1", "deleted": True,
        }
        r = self.client.delete("/api/ontology/views/permissions/p1")
        self.assertEqual(r.status_code, 200)

    def test_detach_permission_404(self):
        self.mock_service.detach_permission.return_value = {
            "status": "error", "message": "permission not found",
        }
        r = self.client.delete("/api/ontology/views/permissions/nonexistent")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
