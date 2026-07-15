"""Action Type - 单元测试 (T387)

覆盖：
- ActionType / ActionExecution 领域模型
- SQLiteActionStorage CRUD + JSON 序列化 (tmp_path 真实 DB)
- ActionTypeRepositoryImpl 8 个方法
- SkillBackedExecutor: 正常 / Skill 缺失 / 超时 / 审计写入
- ActionService: CRUD / OPA 拒绝 / OPA 通过
- FastAPI 路由 HTTP 状态码
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.core.ontology.action.impl import (
    ActionTypeRepositoryImpl,
    SkillBackedExecutor,
)
from odap.biz.core.ontology.action.models import (
    ActionExecution,
    ActionExecutionStatus,
    ActionType,
)
from odap.biz.core.ontology.action.services import ActionService
from odap.biz.core.ontology.action.storage import SQLiteActionStorage


# ============================================================
# 工厂函数
# ============================================================


def _make_action_type(**overrides) -> ActionType:
    """构造测试用 ActionType"""
    defaults = dict(
        name="test-action",
        description="test",
        object_types=["Customer"],
        parameters={"type": "object"},
        return_type="void",
        side_effects=["create"],
        linked_skill_id="skill-test",
        opa_policy_ref="policy.test",
        enabled=True,
    )
    defaults.update(overrides)
    return ActionType(**defaults)


def _make_execution(**overrides) -> ActionExecution:
    """构造测试用 ActionExecution"""
    defaults = dict(
        action_type_id="at-1",
        parameters={"a": 1},
        result={"b": 2},
        status=ActionExecutionStatus.SUCCESS,
        error_message="",
        audit_record_id=None,
        user_id="u1",
        workspace_id="ws1",
    )
    defaults.update(overrides)
    return ActionExecution(**defaults)


# ============================================================
# 1. ActionType 模型
# ============================================================


class TestActionTypeModel(unittest.TestCase):
    """ActionType 必填字段、默认值、UUID、Enum 序列化"""

    def test_minimal_construction(self):
        at = ActionType(name="a1", linked_skill_id="s1")
        self.assertEqual(at.name, "a1")
        self.assertEqual(at.linked_skill_id, "s1")
        self.assertEqual(at.description, "")
        self.assertEqual(at.object_types, [])
        self.assertEqual(at.parameters, {})
        self.assertEqual(at.return_type, "void")
        self.assertEqual(at.side_effects, [])
        self.assertEqual(at.opa_policy_ref, "")
        self.assertTrue(at.enabled)

    def test_name_empty_raises(self):
        with self.assertRaises(ValueError):
            ActionType(name="", linked_skill_id="s1")

    def test_name_whitespace_raises(self):
        with self.assertRaises(ValueError):
            ActionType(name="   ", linked_skill_id="s1")

    def test_default_factory_container_fields(self):
        """容器字段必须用 default_factory（规则 5）"""
        at1 = ActionType(name="a", linked_skill_id="s")
        at1.object_types.append("X")
        at2 = ActionType(name="a", linked_skill_id="s")
        self.assertNotIn("X", at2.object_types)
        at1.parameters["k"] = 1
        self.assertNotIn("k", at2.parameters)

    def test_uuid_auto_unique(self):
        a = ActionType(name="a", linked_skill_id="s")
        b = ActionType(name="a", linked_skill_id="s")
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(len(a.id), 36)

    def test_timestamps_auto(self):
        at = ActionType(name="a", linked_skill_id="s")
        self.assertIsInstance(at.created_at, datetime)
        self.assertIsInstance(at.updated_at, datetime)

    def test_side_effects_and_object_types(self):
        at = ActionType(
            name="a",
            linked_skill_id="s",
            object_types=["A", "B"],
            side_effects=["create", "update"],
        )
        self.assertEqual(at.object_types, ["A", "B"])
        self.assertEqual(at.side_effects, ["create", "update"])

    def test_disabled_flag(self):
        at = ActionType(name="a", linked_skill_id="s", enabled=False)
        self.assertFalse(at.enabled)


# ============================================================
# 2. ActionExecution 模型
# ============================================================


class TestActionExecutionModel(unittest.TestCase):
    """ActionExecution 必填字段、Enum 序列化"""

    def test_minimal_construction(self):
        e = ActionExecution(action_type_id="at-1")
        self.assertEqual(e.action_type_id, "at-1")
        self.assertEqual(e.status, ActionExecutionStatus.PENDING)
        self.assertEqual(e.parameters, {})
        self.assertEqual(e.result, {})
        self.assertEqual(e.user_id, "system")
        self.assertEqual(e.workspace_id, "default")
        self.assertIsNone(e.finished_at)
        self.assertIsNone(e.duration_ms)
        self.assertIsNone(e.audit_record_id)

    def test_enum_str_compatibility(self):
        """ActionExecutionStatus 必须 (str, Enum) 双继承（规则 4）"""
        self.assertEqual(ActionExecutionStatus.SUCCESS, "success")
        self.assertEqual(ActionExecutionStatus.FAILED, "failed")
        self.assertEqual(ActionExecutionStatus.DENIED, "denied")

    def test_all_statuses(self):
        for v in ("pending", "running", "success", "failed", "denied"):
            self.assertEqual(ActionExecutionStatus(v).value, v)

    def test_default_factory_container_fields(self):
        e1 = ActionExecution(action_type_id="a")
        e1.parameters["k"] = 1
        e2 = ActionExecution(action_type_id="a")
        self.assertNotIn("k", e2.parameters)

    def test_finished_at_set_explicitly(self):
        e = ActionExecution(
            action_type_id="a", finished_at=datetime.now(), duration_ms=120
        )
        self.assertIsNotNone(e.finished_at)
        self.assertEqual(e.duration_ms, 120)

    def test_uuid_auto_unique(self):
        a = ActionExecution(action_type_id="a")
        b = ActionExecution(action_type_id="a")
        self.assertNotEqual(a.id, b.id)


# ============================================================
# 3. SQLite Storage
# ============================================================


class TestSQLiteActionStorage(unittest.TestCase):
    """SQLiteActionStorage CRUD + JSON 序列化（tmp_path 真实 DB）"""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.db_path = f"{tmp}/action.db"
        self.storage = SQLiteActionStorage(db_path=self.db_path)

    def _sample_at(self, **overrides) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        defaults = dict(
            id="at-1",
            name="n1",
            description="d1",
            object_types=["Customer"],
            parameters={"k": "v"},
            return_type="void",
            side_effects=["create"],
            linked_skill_id="s-1",
            opa_policy_ref="p1",
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        defaults.update(overrides)
        return defaults

    def test_save_and_get_action_type_roundtrip(self):
        at = self._sample_at()
        self.storage.save_action_type(at)
        got = self.storage.get_action_type("at-1")
        self.assertIsNotNone(got)
        self.assertEqual(got["id"], "at-1")
        self.assertEqual(got["name"], "n1")
        self.assertEqual(got["object_types"], ["Customer"])
        self.assertEqual(got["parameters"], {"k": "v"})
        self.assertEqual(got["linked_skill_id"], "s-1")
        self.assertTrue(got["enabled"])

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.storage.get_action_type("nope"))

    def test_list_action_types_enabled_only(self):
        self.storage.save_action_type(self._sample_at(id="a", enabled=True))
        self.storage.save_action_type(self._sample_at(id="b", enabled=False))
        self.assertEqual(len(self.storage.list_action_types(enabled_only=True)), 1)
        self.assertEqual(len(self.storage.list_action_types(enabled_only=False)), 2)

    def test_list_by_object_type(self):
        self.storage.save_action_type(
            self._sample_at(id="a", object_types=["Customer"])
        )
        self.storage.save_action_type(
            self._sample_at(id="b", object_types=["Order"])
        )
        self.assertEqual(
            len(self.storage.list_action_types_by_object_type("Customer")), 1
        )
        self.assertEqual(
            len(self.storage.list_action_types_by_object_type("Order")), 1
        )
        self.assertEqual(
            len(self.storage.list_action_types_by_object_type("Other")), 0
        )

    def test_delete_action_type(self):
        self.storage.save_action_type(self._sample_at())
        self.assertTrue(self.storage.delete_action_type("at-1"))
        self.assertIsNone(self.storage.get_action_type("at-1"))

    def test_delete_nonexistent_returns_false(self):
        self.assertFalse(self.storage.delete_action_type("missing"))

    def test_save_and_get_execution_roundtrip(self):
        ex = {
            "id": "ex-1",
            "action_type_id": "at-1",
            "parameters": {"x": 1},
            "result": {"y": 2},
            "status": "success",
            "error_message": "",
            "audit_record_id": "audit-1",
            "user_id": "u1",
            "workspace_id": "ws1",
            "started_at": datetime.now().isoformat(),
            "finished_at": datetime.now().isoformat(),
            "duration_ms": 100,
        }
        self.storage.save_execution(ex)
        got = self.storage.get_execution("ex-1")
        self.assertIsNotNone(got)
        self.assertEqual(got["status"], "success")
        self.assertEqual(got["parameters"], {"x": 1})
        self.assertEqual(got["result"], {"y": 2})
        self.assertEqual(got["audit_record_id"], "audit-1")
        self.assertEqual(got["duration_ms"], 100)

    def test_get_nonexistent_execution_returns_none(self):
        self.assertIsNone(self.storage.get_execution("nope"))

    def test_list_executions_by_type(self):
        for i in range(3):
            self.storage.save_execution({
                "id": f"e{i}", "action_type_id": "at-1",
                "parameters": {}, "result": {}, "status": "success",
                "error_message": "", "audit_record_id": None,
                "user_id": "u", "workspace_id": "ws",
                "started_at": datetime.now().isoformat(),
                "finished_at": datetime.now().isoformat(),
                "duration_ms": 10,
            })
        self.storage.save_execution({
            "id": "e_other", "action_type_id": "at-2",
            "parameters": {}, "result": {}, "status": "success",
            "error_message": "", "audit_record_id": None,
            "user_id": "u", "workspace_id": "ws",
            "started_at": datetime.now().isoformat(),
            "finished_at": datetime.now().isoformat(),
            "duration_ms": 10,
        })
        self.assertEqual(len(self.storage.list_executions("at-1")), 3)
        self.assertEqual(len(self.storage.list_executions("at-2")), 1)

    def test_list_executions_respects_limit(self):
        for i in range(5):
            self.storage.save_execution({
                "id": f"e{i}", "action_type_id": "at-1",
                "parameters": {}, "result": {}, "status": "success",
                "error_message": "", "audit_record_id": None,
                "user_id": "u", "workspace_id": "ws",
                "started_at": datetime.now().isoformat(),
                "finished_at": datetime.now().isoformat(),
                "duration_ms": 10,
            })
        self.assertEqual(len(self.storage.list_executions("at-1", limit=2)), 2)


# ============================================================
# 4. ActionTypeRepositoryImpl
# ============================================================


class TestActionTypeRepository(unittest.TestCase):
    """ActionTypeRepositoryImpl: 8 个抽象方法"""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.storage = SQLiteActionStorage(db_path=f"{tmp}/repo.db")
        self.repo = ActionTypeRepositoryImpl(storage=self.storage)

    def test_save_and_get(self):
        at = _make_action_type()
        self.repo.save(at)
        got = self.repo.get(at.id)
        self.assertIsNotNone(got)
        self.assertEqual(got.name, at.name)
        self.assertEqual(got.linked_skill_id, at.linked_skill_id)

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.repo.get("missing"))

    def test_list_all(self):
        a = _make_action_type(name="a1")
        b = _make_action_type(name="a2")
        self.repo.save(a)
        self.repo.save(b)
        self.assertEqual(len(self.repo.list()), 2)

    def test_list_enabled_only(self):
        self.repo.save(_make_action_type(name="e1", enabled=True))
        self.repo.save(_make_action_type(name="d1", enabled=False))
        self.assertEqual(len(self.repo.list(enabled_only=True)), 1)

    def test_list_by_object_type(self):
        self.repo.save(_make_action_type(name="a1", object_types=["Customer"]))
        self.repo.save(_make_action_type(name="a2", object_types=["Order"]))
        self.assertEqual(len(self.repo.list_by_object_type("Customer")), 1)

    def test_delete_existing(self):
        at = _make_action_type()
        self.repo.save(at)
        self.assertTrue(self.repo.delete(at.id))
        self.assertIsNone(self.repo.get(at.id))

    def test_delete_nonexistent(self):
        self.assertFalse(self.repo.delete("missing"))

    def test_save_execution_and_get(self):
        e = _make_execution(action_type_id="at-x")
        self.repo.save_execution(e)
        got = self.repo.get_execution(e.id)
        self.assertIsNotNone(got)
        self.assertEqual(got.status, ActionExecutionStatus.SUCCESS)

    def test_get_execution_nonexistent(self):
        self.assertIsNone(self.repo.get_execution("missing"))

    def test_list_executions(self):
        for _ in range(3):
            self.repo.save_execution(_make_execution(action_type_id="at-1"))
        self.assertEqual(len(self.repo.list_executions("at-1")), 3)


# ============================================================
# 5. SkillBackedExecutor
# ============================================================


class _FakeSkillOutput:
    def __init__(self, success=True, data=None, error=None):
        self.success = success
        self.data = data or {}
        self.error = error


class TestSkillBackedExecutor(unittest.TestCase):
    """SkillBackedExecutor: 正常 / Skill 缺失 / 超时 / 审计"""

    def _make_skill_registry(self, skill_obj=None, raise_exc=None,
                             deny=False):
        registry = MagicMock()
        if raise_exc is not None:
            registry.get.side_effect = raise_exc
        elif deny:
            registry.get.return_value = lambda **kwargs: {
                "status": "denied", "message": "no perm"
            }
        else:
            registry.get.return_value = skill_obj
        return registry

    def test_missing_linked_skill_id(self):
        at = _make_action_type(linked_skill_id=None)
        ex = SkillBackedExecutor(skill_registry=MagicMock()).execute(
            at, {}, {"user_id": "u1"}
        )
        self.assertEqual(ex.status, ActionExecutionStatus.FAILED)
        self.assertIn("linked_skill_id", ex.error_message)

    def test_skill_not_found(self):
        registry = self._make_skill_registry(skill_obj=None)
        at = _make_action_type(linked_skill_id="missing")
        ex = SkillBackedExecutor(skill_registry=registry).execute(
            at, {}, {"user_id": "u1"}
        )
        self.assertEqual(ex.status, ActionExecutionStatus.FAILED)
        self.assertIn("Skill not found", ex.error_message)
        self.assertIn("missing", ex.error_message)

    def test_skill_returns_dict_success(self):
        skill = MagicMock()
        skill.run.return_value = {"status": "ok", "value": 42}
        registry = self._make_skill_registry(skill_obj=skill)
        at = _make_action_type(linked_skill_id="s1")
        ex = SkillBackedExecutor(skill_registry=registry).execute(
            at, {"p": 1}, {"user_id": "u1"}
        )
        self.assertEqual(ex.status, ActionExecutionStatus.SUCCESS)
        self.assertEqual(ex.result.get("value"), 42)
        self.assertIsNotNone(ex.finished_at)
        self.assertIsNotNone(ex.duration_ms)

    def test_skill_returns_skill_output_success(self):
        skill = MagicMock()
        skill.run.return_value = _FakeSkillOutput(
            success=True, data={"k": "v"}
        )
        registry = self._make_skill_registry(skill_obj=skill)
        at = _make_action_type(linked_skill_id="s1")
        ex = SkillBackedExecutor(skill_registry=registry).execute(
            at, {}, {"user_id": "u1"}
        )
        self.assertEqual(ex.status, ActionExecutionStatus.SUCCESS)
        self.assertEqual(ex.result.get("k"), "v")

    def test_skill_returns_skill_output_failure(self):
        skill = MagicMock()
        skill.run.return_value = _FakeSkillOutput(
            success=False, data={}, error="boom"
        )
        registry = self._make_skill_registry(skill_obj=skill)
        at = _make_action_type(linked_skill_id="s1")
        ex = SkillBackedExecutor(skill_registry=registry).execute(
            at, {}, {"user_id": "u1"}
        )
        self.assertEqual(ex.status, ActionExecutionStatus.FAILED)
        self.assertIn("boom", ex.error_message)

    def test_skill_returns_dict_denied(self):
        skill = MagicMock()
        skill.run.return_value = {"status": "denied", "message": "no"}
        registry = self._make_skill_registry(skill_obj=skill)
        at = _make_action_type(linked_skill_id="s1")
        ex = SkillBackedExecutor(skill_registry=registry).execute(
            at, {}, {"user_id": "u1"}
        )
        self.assertEqual(ex.status, ActionExecutionStatus.DENIED)

    def test_skill_returns_scalar_wrapped(self):
        skill = MagicMock()
        skill.run.return_value = 99
        registry = self._make_skill_registry(skill_obj=skill)
        at = _make_action_type(linked_skill_id="s1")
        ex = SkillBackedExecutor(skill_registry=registry).execute(
            at, {}, {"user_id": "u1"}
        )
        self.assertEqual(ex.status, ActionExecutionStatus.SUCCESS)
        self.assertEqual(ex.result.get("result"), 99)

    def test_skill_timeout_marks_failed(self):
        skill = MagicMock()
        skill.run.side_effect = TimeoutError("took too long")
        registry = self._make_skill_registry(skill_obj=skill)
        at = _make_action_type(linked_skill_id="s1")
        ex = SkillBackedExecutor(skill_registry=registry).execute(
            at, {}, {"user_id": "u1"}
        )
        self.assertEqual(ex.status, ActionExecutionStatus.FAILED)
        self.assertIn("timeout", ex.error_message)

    def test_skill_generic_exception_marks_failed(self):
        skill = MagicMock()
        skill.run.side_effect = RuntimeError("nope")
        registry = self._make_skill_registry(skill_obj=skill)
        at = _make_action_type(linked_skill_id="s1")
        ex = SkillBackedExecutor(skill_registry=registry).execute(
            at, {}, {"user_id": "u1"}
        )
        self.assertEqual(ex.status, ActionExecutionStatus.FAILED)
        self.assertIn("nope", ex.error_message)

    def test_audit_record_id_set_when_audit_sink_returns_id(self):
        skill = MagicMock()
        skill.run.return_value = {"ok": True}
        registry = self._make_skill_registry(skill_obj=skill)
        audit_sink = MagicMock(return_value="audit-xyz")
        at = _make_action_type(linked_skill_id="s1")
        ex = SkillBackedExecutor(
            skill_registry=registry, audit_sink=audit_sink
        ).execute(at, {}, {"user_id": "u1"})
        self.assertEqual(ex.audit_record_id, "audit-xyz")
        self.assertTrue(audit_sink.called)

    def test_audit_sink_failure_does_not_break_execution(self):
        skill = MagicMock()
        skill.run.return_value = {"ok": True}
        registry = self._make_skill_registry(skill_obj=skill)
        audit_sink = MagicMock(side_effect=RuntimeError("audit down"))
        at = _make_action_type(linked_skill_id="s1")
        ex = SkillBackedExecutor(
            skill_registry=registry, audit_sink=audit_sink
        ).execute(at, {}, {"user_id": "u1"})
        self.assertEqual(ex.status, ActionExecutionStatus.SUCCESS)

    def test_registry_unavailable_marks_failed(self):
        at = _make_action_type(linked_skill_id="s1")
        with patch(
            "odap.tools.base.get_registry",
            side_effect=ImportError("no module"),
        ):
            ex = SkillBackedExecutor(
                skill_registry=None
            ).execute(at, {}, {"user_id": "u1"})
        self.assertEqual(ex.status, ActionExecutionStatus.FAILED)
        self.assertIn("registry", ex.error_message.lower())


# ============================================================
# 6. ActionService
# ============================================================


class TestActionService(unittest.TestCase):
    """ActionService: CRUD / OPA 拒绝 / OPA 通过"""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.storage = SQLiteActionStorage(db_path=f"{tmp}/svc.db")
        self.repo = ActionTypeRepositoryImpl(storage=self.storage)
        self.executor = MagicMock()
        self.svc = ActionService(
            repository=self.repo,
            executor=self.executor,
            storage=self.storage,
        )

    def _make_payload(self, **overrides) -> Dict[str, Any]:
        defaults = dict(
            name="a1",
            description="d1",
            object_types=["Customer"],
            parameters={"k": "v"},
            return_type="void",
            side_effects=["create"],
            linked_skill_id="s-1",
            opa_policy_ref="p1",
            enabled=True,
        )
        defaults.update(overrides)
        return defaults

    def test_create_action_type_ok(self):
        result = self.svc.create_action_type(self._make_payload())
        self.assertNotIn("status", result)
        self.assertEqual(result["name"], "a1")
        self.assertEqual(result["linked_skill_id"], "s-1")
        self.assertEqual(result["object_types"], ["Customer"])
        self.assertEqual(result["parameters"], {"k": "v"})

    def test_create_action_type_missing_linked_skill_id(self):
        payload = self._make_payload()
        payload.pop("linked_skill_id")
        result = self.svc.create_action_type(payload)
        self.assertEqual(result["status"], "error")
        self.assertIn("linked_skill_id", result["message"])

    def test_create_action_type_empty_name(self):
        result = self.svc.create_action_type(self._make_payload(name=""))
        self.assertEqual(result["status"], "error")

    def test_get_action_type_ok(self):
        at = _make_action_type()
        self.repo.save(at)
        result = self.svc.get_action_type(at.id)
        self.assertEqual(result["id"], at.id)

    def test_get_action_type_not_found(self):
        result = self.svc.get_action_type("missing")
        self.assertEqual(result["status"], "error")

    def test_list_action_types(self):
        self.repo.save(_make_action_type(name="a1"))
        self.repo.save(_make_action_type(name="a2"))
        result = self.svc.list_action_types()
        self.assertEqual(result["count"], 2)

    def test_list_action_types_by_object_type(self):
        self.repo.save(_make_action_type(name="a1", object_types=["X"]))
        result = self.svc.list_action_types(object_type="X")
        self.assertEqual(result["count"], 1)

    def test_update_action_type_ok(self):
        at = _make_action_type()
        self.repo.save(at)
        result = self.svc.update_action_type(
            at.id, {"description": "updated"}
        )
        self.assertEqual(result["description"], "updated")
        self.assertEqual(result["name"], at.name)  # 未传，保留

    def test_update_action_type_not_found(self):
        result = self.svc.update_action_type("missing", {"name": "x"})
        self.assertEqual(result["status"], "error")

    def test_delete_action_type_ok(self):
        at = _make_action_type()
        self.repo.save(at)
        result = self.svc.delete_action_type(at.id)
        self.assertTrue(result["deleted"])

    def test_delete_action_type_not_found(self):
        result = self.svc.delete_action_type("missing")
        self.assertEqual(result["status"], "error")

    # ---------- execute_action ----------

    def test_execute_action_opa_passes(self):
        at = _make_action_type()
        self.repo.save(at)
        self.executor.execute.return_value = _make_execution(
            action_type_id=at.id,
            status=ActionExecutionStatus.SUCCESS,
        )
        svc = ActionService(
            repository=self.repo, executor=self.executor, storage=self.storage,
            opa_check=lambda _at, _ctx: True,
        )
        result = svc.execute_action(at.id, {"p": 1}, {"user_id": "u1"})
        self.assertEqual(result["status"], "success")
        # execution 已落库
        self.assertEqual(len(self.repo.list_executions(at.id)), 1)

    def test_execute_action_opa_denied_marks_denied(self):
        at = _make_action_type()
        self.repo.save(at)
        self.executor.execute.return_value = _make_execution(
            action_type_id=at.id,
        )
        svc = ActionService(
            repository=self.repo, executor=self.executor, storage=self.storage,
            opa_check=lambda _at, _ctx: False,
        )
        result = svc.execute_action(at.id, {}, {"user_id": "u1"})
        self.assertEqual(result["status"], "denied")
        # executor.execute 不应在 OPA 拒绝时被调用
        self.executor.execute.assert_not_called()
        # denied execution 落库
        rows = self.repo.list_executions(at.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, ActionExecutionStatus.DENIED)

    def test_execute_action_opa_check_raises_fail_closed(self):
        at = _make_action_type()
        self.repo.save(at)
        self.executor.execute.return_value = _make_execution(
            action_type_id=at.id,
        )

        def bad_check(_at, _ctx):
            raise RuntimeError("OPA broken")

        svc = ActionService(
            repository=self.repo, executor=self.executor, storage=self.storage,
            opa_check=bad_check,
        )
        result = svc.execute_action(at.id, {}, {"user_id": "u1"})
        self.assertEqual(result["status"], "denied")
        self.executor.execute.assert_not_called()

    def test_execute_action_action_type_not_found(self):
        result = self.svc.execute_action("missing", {}, {"user_id": "u1"})
        self.assertEqual(result["status"], "error")

    def test_list_executions(self):
        at = _make_action_type()
        self.repo.save(at)
        for _ in range(3):
            self.repo.save_execution(_make_execution(action_type_id=at.id))
        result = self.svc.list_executions(at.id, limit=10)
        self.assertEqual(result["count"], 3)

    def test_list_executions_respects_limit(self):
        at = _make_action_type()
        self.repo.save(at)
        for _ in range(5):
            self.repo.save_execution(_make_execution(action_type_id=at.id))
        result = self.svc.list_executions(at.id, limit=2)
        self.assertEqual(result["count"], 2)

    def test_get_execution(self):
        e = _make_execution(action_type_id="at-1")
        self.repo.save_execution(e)
        result = self.svc.get_execution(e.id)
        self.assertEqual(result["id"], e.id)

    def test_get_execution_not_found(self):
        result = self.svc.get_execution("missing")
        self.assertEqual(result["status"], "error")

    def test_execution_dict_type_conversion(self):
        """execute_action 返回值包含 ISO 字符串时间、Enum 字符串值"""
        at = _make_action_type()
        self.repo.save(at)
        self.executor.execute.return_value = _make_execution(
            action_type_id=at.id,
            status=ActionExecutionStatus.SUCCESS,
        )
        svc = ActionService(
            repository=self.repo, executor=self.executor, storage=self.storage,
        )
        result = svc.execute_action(at.id, {}, {"user_id": "u1"})
        self.assertIsInstance(result["status"], str)
        self.assertIsInstance(result["started_at"], str)
        # ISO 字符串可被 fromisoformat 解析
        datetime.fromisoformat(result["started_at"])


# ============================================================
# 7. FastAPI 路由
# ============================================================


class TestActionRoutes(unittest.TestCase):
    """FastAPI 路由：HTTP 状态码、HTTPException 透传"""

    def setUp(self):
        from odap.biz.core.ontology.action.api import routes as routes_module
        from odap.biz.core.ontology.action.services import ActionService
        from odap.biz.core.ontology.action.storage import SQLiteActionStorage
        tmp = tempfile.mkdtemp()
        self.tmp = tmp
        routes_module.action_service = ActionService(
            storage=SQLiteActionStorage(db_path=f"{tmp}/api.db")
        )
        # 把 executor 替换成可控 mock（避免依赖外部 SkillRegistry）
        routes_module.action_service.executor = MagicMock()

        from odap.biz.core.ontology.action.api.routes import router
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)

    def test_create_200(self):
        r = self.client.post("/api/ontology/actions", json={
            "name": "a1", "linked_skill_id": "s-1",
        })
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["action_types"][0]["name"], "a1")

    def test_create_400_missing_linked_skill_id(self):
        r = self.client.post("/api/ontology/actions", json={"name": "a1"})
        self.assertEqual(r.status_code, 400)

    def test_list_200_empty(self):
        r = self.client.get("/api/ontology/actions")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["count"], 0)

    def test_list_200_with_results(self):
        from odap.biz.core.ontology.action.api import routes as rm
        rm.action_service.create_action_type(
            {"name": "a1", "linked_skill_id": "s-1"}
        )
        r = self.client.get("/api/ontology/actions")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

    def test_list_enabled_only(self):
        from odap.biz.core.ontology.action.api import routes as rm
        rm.action_service.create_action_type(
            {"name": "a1", "linked_skill_id": "s-1", "enabled": True}
        )
        rm.action_service.create_action_type(
            {"name": "a2", "linked_skill_id": "s-2", "enabled": False}
        )
        r = self.client.get(
            "/api/ontology/actions?enabled_only=true"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

    def test_get_200(self):
        from odap.biz.core.ontology.action.api import routes as rm
        created = rm.action_service.create_action_type(
            {"name": "a1", "linked_skill_id": "s-1"}
        )
        r = self.client.get(f"/api/ontology/actions/{created['id']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], created["id"])

    def test_get_404(self):
        r = self.client.get("/api/ontology/actions/missing")
        self.assertEqual(r.status_code, 404)

    def test_update_200(self):
        from odap.biz.core.ontology.action.api import routes as rm
        created = rm.action_service.create_action_type(
            {"name": "a1", "linked_skill_id": "s-1"}
        )
        r = self.client.put(
            f"/api/ontology/actions/{created['id']}",
            json={"description": "new"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["description"], "new")

    def test_update_404(self):
        r = self.client.put(
            "/api/ontology/actions/missing", json={"name": "x"}
        )
        self.assertEqual(r.status_code, 404)

    def test_delete_200(self):
        from odap.biz.core.ontology.action.api import routes as rm
        created = rm.action_service.create_action_type(
            {"name": "a1", "linked_skill_id": "s-1"}
        )
        r = self.client.delete(
            f"/api/ontology/actions/{created['id']}"
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["deleted"])

    def test_delete_404(self):
        r = self.client.delete("/api/ontology/actions/missing")
        self.assertEqual(r.status_code, 404)

    def test_execute_200(self):
        from odap.biz.core.ontology.action.api import routes as rm
        created = rm.action_service.create_action_type(
            {"name": "a1", "linked_skill_id": "s-1"}
        )
        rm.action_service.executor.execute.return_value = _make_execution(
            action_type_id=created["id"],
            status=ActionExecutionStatus.SUCCESS,
        )
        r = self.client.post(
            f"/api/ontology/actions/{created['id']}/execute",
            json={"parameters": {"x": 1}, "user_context": {"user_id": "u1"}},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "success")

    def test_execute_404(self):
        r = self.client.post(
            "/api/ontology/actions/missing/execute",
            json={"parameters": {}, "user_context": {}},
        )
        self.assertEqual(r.status_code, 404)

    def test_list_executions_200(self):
        from odap.biz.core.ontology.action.api import routes as rm
        created = rm.action_service.create_action_type(
            {"name": "a1", "linked_skill_id": "s-1"}
        )
        rm.action_service.repository.save_execution(
            _make_execution(action_type_id=created["id"])
        )
        r = self.client.get(
            f"/api/ontology/actions/{created['id']}/executions"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

    def test_list_executions_respects_limit(self):
        from odap.biz.core.ontology.action.api import routes as rm
        created = rm.action_service.create_action_type(
            {"name": "a1", "linked_skill_id": "s-1"}
        )
        for _ in range(3):
            rm.action_service.repository.save_execution(
                _make_execution(action_type_id=created["id"])
            )
        r = self.client.get(
            f"/api/ontology/actions/{created['id']}/executions?limit=2"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 2)


if __name__ == "__main__":
    unittest.main()
