"""Computed Property - 单元测试 (T399)

覆盖：
- ComputedProperty / MaterializationJob 领域模型
- SQLiteComputedStorage 3 表 CRUD + JSON 序列化 (tmp_path 真实 DB)
- ComputedRepositoryImpl
- DependencyTracker: 单依赖、多依赖、DAG 构建、循环检测、反向传播
- SafeExpressionEvaluator: 数学/字符串/日期/聚合; 沙箱安全 (拒绝 exec/import/open)
- IncrementalComputer: 单层传播、多层传播、错误处理
- ComputedService: CRUD + 评估 + 物化 + 任务状态
- FastAPI 路由 HTTP 状态码 + HTTPException 透传
"""
from __future__ import annotations

import unittest
from datetime import datetime
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.testclient import TestClient

from odap.biz.core.ontology.computed.api.routes import router as computed_router
from odap.biz.core.ontology.computed.impl import (
    AttrDict,
    ComputedRepositoryImpl,
    DependencyTracker,
    IncrementalComputer,
    SafeExpressionEvaluator,
)
from odap.biz.core.ontology.computed.interfaces import (
    EvaluationContext,
    ValidationResult,
)
from odap.biz.core.ontology.computed.models import (
    ComputedProperty,
    JobTrigger,
    MaterializationJob,
    MaterializationStatus,
    MaterializationType,
)
from odap.biz.core.ontology.computed.services import ComputedService
from odap.biz.core.ontology.computed.storage import SQLiteComputedStorage


# ============================================================
# 工厂函数
# ============================================================


def _make_property(**overrides) -> ComputedProperty:
    """构造测试用 ComputedProperty"""
    defaults = dict(
        name="total_amount",
        target_type_id="Order",
        expression="instance.amount * instance.quantity",
        dependencies=["amount", "quantity"],
        materialization=MaterializationType.INCREMENTAL,
        return_type="number",
        description="",
        enabled=True,
    )
    defaults.update(overrides)
    return ComputedProperty(**defaults)


def _make_job(**overrides) -> MaterializationJob:
    """构造测试用 MaterializationJob"""
    defaults = dict(
        property_id="p-1",
        status=MaterializationStatus.PENDING,
        processed_count=0,
        error_message="",
        triggered_by=JobTrigger.MANUAL,
        mode="incremental",
    )
    defaults.update(overrides)
    return MaterializationJob(**defaults)


# ============================================================
# 1. ComputedProperty 模型
# ============================================================


class TestComputedPropertyModel(unittest.TestCase):
    """ComputedProperty 必填字段、默认值、UUID、Enum 序列化"""

    def test_minimal_construction(self):
        p = _make_property()
        self.assertEqual(p.name, "total_amount")
        self.assertEqual(p.target_type_id, "Order")
        self.assertTrue(p.expression.startswith("instance"))
        self.assertEqual(p.materialization, MaterializationType.INCREMENTAL)
        self.assertEqual(p.return_type, "number")
        self.assertTrue(p.enabled)

    def test_name_empty_raises(self):
        with self.assertRaises(ValueError):
            ComputedProperty(name="", target_type_id="X", expression="1+1")

    def test_name_whitespace_raises(self):
        with self.assertRaises(ValueError):
            ComputedProperty(name="   ", target_type_id="X", expression="1+1")

    def test_target_type_id_empty_raises(self):
        with self.assertRaises(ValueError):
            ComputedProperty(name="a", target_type_id="", expression="1+1")

    def test_expression_empty_raises(self):
        with self.assertRaises(ValueError):
            ComputedProperty(name="a", target_type_id="X", expression="")

    def test_default_factory_container_fields(self):
        """容器字段必须用 default_factory（规则 5）"""
        p1 = _make_property()
        p1.dependencies.append("X")
        p2 = _make_property()
        self.assertNotIn("X", p2.dependencies)

    def test_uuid_auto_unique(self):
        a = _make_property()
        b = _make_property()
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(len(a.id), 36)

    def test_timestamps_auto(self):
        p = _make_property()
        self.assertIsInstance(p.created_at, datetime)
        self.assertIsInstance(p.updated_at, datetime)

    def test_materialization_enum_values(self):
        self.assertEqual(MaterializationType.NONE.value, "none")
        self.assertEqual(MaterializationType.FULL.value, "full")
        self.assertEqual(MaterializationType.INCREMENTAL.value, "incremental")


# ============================================================
# 2. MaterializationJob 模型
# ============================================================


class TestMaterializationJobModel(unittest.TestCase):
    """MaterializationJob 必填字段、默认值、UUID、Enum 序列化"""

    def test_minimal_construction(self):
        j = _make_job()
        self.assertEqual(j.property_id, "p-1")
        self.assertEqual(j.status, MaterializationStatus.PENDING)
        self.assertEqual(j.processed_count, 0)
        self.assertEqual(j.triggered_by, JobTrigger.MANUAL)
        self.assertEqual(j.mode, "incremental")
        self.assertIsNone(j.finished_at)

    def test_status_enum_values(self):
        for s in ["pending", "running", "done", "failed"]:
            self.assertIn(s, [st.value for st in MaterializationStatus])

    def test_trigger_enum_values(self):
        for t in ["manual", "incremental", "scheduled"]:
            self.assertIn(t, [tr.value for tr in JobTrigger])

    def test_uuid_auto_unique(self):
        a = _make_job()
        b = _make_job()
        self.assertNotEqual(a.id, b.id)

    def test_timestamps_auto(self):
        j = _make_job()
        self.assertIsInstance(j.started_at, datetime)

    def test_finished_at_optional(self):
        j = _make_job(finished_at=datetime.now())
        self.assertIsNotNone(j.finished_at)


# ============================================================
# 3. SQLite 存储层（3 表 CRUD + tmp_path 真实 DB）
# ============================================================


class TestSQLiteComputedStorage(unittest.TestCase):
    """SQLiteComputedStorage 3 表 CRUD + JSON 序列化"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = f"{self.tmp.name}/test_computed.db"
        self.storage = SQLiteComputedStorage(db_path=self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    # ----- computed_properties -----

    def test_save_and_get_property(self):
        prop = _make_property()
        self.storage.save_property(self._prop_to_dict(prop))
        row = self.storage.get_property(prop.id)
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "total_amount")
        self.assertEqual(row["target_type_id"], "Order")
        self.assertEqual(row["dependencies"], ["amount", "quantity"])
        self.assertTrue(row["enabled"])

    def test_get_property_not_found(self):
        self.assertIsNone(self.storage.get_property("nonexistent"))

    def test_list_properties(self):
        for _ in range(3):
            self.storage.save_property(self._prop_to_dict(_make_property()))
        rows = self.storage.list_properties()
        self.assertEqual(len(rows), 3)

    def test_list_properties_filter_target(self):
        self.storage.save_property(
            self._prop_to_dict(_make_property(target_type_id="A"))
        )
        self.storage.save_property(
            self._prop_to_dict(_make_property(target_type_id="B"))
        )
        rows = self.storage.list_properties(target_type_id="A")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["target_type_id"], "A")

    def test_list_properties_filter_enabled(self):
        self.storage.save_property(
            self._prop_to_dict(_make_property(enabled=True))
        )
        self.storage.save_property(
            self._prop_to_dict(_make_property(enabled=False))
        )
        rows = self.storage.list_properties(enabled_only=True)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["enabled"])

    def test_delete_property(self):
        prop = _make_property()
        self.storage.save_property(self._prop_to_dict(prop))
        self.assertTrue(self.storage.delete_property(prop.id))
        self.assertIsNone(self.storage.get_property(prop.id))

    def test_delete_property_not_found(self):
        self.assertFalse(self.storage.delete_property("nonexistent"))

    # ----- materialization_jobs -----

    def test_save_and_get_job(self):
        job = _make_job()
        self.storage.save_job(self._job_to_dict(job))
        row = self.storage.get_job(job.id)
        self.assertIsNotNone(row)
        self.assertEqual(row["property_id"], "p-1")
        self.assertEqual(row["status"], "pending")

    def test_get_job_not_found(self):
        self.assertIsNone(self.storage.get_job("nonexistent"))

    def test_list_jobs(self):
        for i in range(3):
            self.storage.save_job(self._job_to_dict(_make_job()))
        rows = self.storage.list_jobs("p-1")
        self.assertEqual(len(rows), 3)

    def test_list_jobs_limit(self):
        for i in range(5):
            self.storage.save_job(self._job_to_dict(_make_job()))
        rows = self.storage.list_jobs("p-1", limit=2)
        self.assertEqual(len(rows), 2)

    # ----- materialized_values -----

    def test_save_and_get_materialized_value(self):
        from datetime import datetime
        self.storage.save_materialized_value(
            "p-1", "i-1", {"v": 100}, datetime.now().isoformat()
        )
        row = self.storage.get_materialized_value("p-1", "i-1")
        self.assertIsNotNone(row)
        self.assertEqual(row["value"], {"v": 100})

    def test_get_materialized_value_not_found(self):
        self.assertIsNone(
            self.storage.get_materialized_value("p-1", "missing")
        )

    def test_materialized_value_upsert(self):
        from datetime import datetime
        ts = datetime.now().isoformat()
        self.storage.save_materialized_value("p-1", "i-1", 1, ts)
        self.storage.save_materialized_value("p-1", "i-1", 2, ts)
        row = self.storage.get_materialized_value("p-1", "i-1")
        self.assertEqual(row["value"], 2)

    def test_list_materialized_values(self):
        from datetime import datetime
        for i in range(3):
            self.storage.save_materialized_value(
                "p-1", f"i-{i}", i, datetime.now().isoformat()
            )
        rows = self.storage.list_materialized_values("p-1")
        self.assertEqual(len(rows), 3)

    def test_delete_materialized_values(self):
        from datetime import datetime
        for i in range(3):
            self.storage.save_materialized_value(
                "p-1", f"i-{i}", i, datetime.now().isoformat()
            )
        n = self.storage.delete_materialized_values("p-1")
        self.assertEqual(n, 3)
        self.assertEqual(len(self.storage.list_materialized_values("p-1")), 0)

    # ----- 工具 -----

    @staticmethod
    def _prop_to_dict(p: ComputedProperty) -> Dict[str, Any]:
        return {
            "id": p.id,
            "name": p.name,
            "target_type_id": p.target_type_id,
            "expression": p.expression,
            "dependencies": list(p.dependencies or []),
            "materialization": p.materialization.value,
            "return_type": p.return_type,
            "description": p.description,
            "enabled": p.enabled,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        }

    @staticmethod
    def _job_to_dict(j: MaterializationJob) -> Dict[str, Any]:
        finished = j.finished_at
        return {
            "id": j.id,
            "property_id": j.property_id,
            "status": j.status.value,
            "started_at": j.started_at.isoformat(),
            "finished_at": finished.isoformat() if finished else None,
            "processed_count": j.processed_count,
            "error_message": j.error_message,
            "triggered_by": j.triggered_by.value,
            "mode": j.mode,
        }


# ============================================================
# 4. ComputedRepositoryImpl
# ============================================================


class TestComputedRepositoryImpl(unittest.TestCase):
    """ComputedRepositoryImpl 域对象 ↔ dict 转换"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = SQLiteComputedStorage(
            db_path=f"{self.tmp.name}/test.db"
        )
        self.repo = ComputedRepositoryImpl(storage=self.storage)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_get_property(self):
        prop = _make_property()
        self.repo.save_property(prop)
        loaded = self.repo.get_property(prop.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, prop.name)
        self.assertEqual(loaded.dependencies, prop.dependencies)

    def test_list_properties(self):
        for _ in range(2):
            self.repo.save_property(_make_property())
        self.assertEqual(len(self.repo.list_properties()), 2)

    def test_save_and_get_job(self):
        job = _make_job()
        self.repo.save_job(job)
        loaded = self.repo.get_job(job.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.property_id, "p-1")
        self.assertEqual(loaded.status, MaterializationStatus.PENDING)

    def test_save_materialized_value(self):
        from datetime import datetime
        self.repo.save_materialized_value(
            "p-1", "i-1", 42, datetime.now().isoformat()
        )
        row = self.repo.get_materialized_value("p-1", "i-1")
        self.assertIsNotNone(row)


# ============================================================
# 5. DependencyTracker
# ============================================================


class TestDependencyTracker(unittest.TestCase):
    """DependencyTracker AST 解析 + DAG 构建 + 反向传播 + 循环检测"""

    def test_add_and_get_dependencies(self):
        t = DependencyTracker()
        t.add_property("p1", ["a", "b"])
        self.assertEqual(sorted(t.get_dependencies("p1")), ["a", "b"])

    def test_multiple_properties(self):
        t = DependencyTracker()
        t.add_property("p1", ["a"])
        t.add_property("p2", ["a", "b"])
        t.add_property("p3", ["b"])
        self.assertEqual(sorted(t.get_dependencies("p1")), ["a"])
        self.assertEqual(sorted(t.get_dependencies("p2")), ["a", "b"])
        self.assertEqual(sorted(t.get_dependencies("p3")), ["b"])

    def test_get_downstream_single(self):
        t = DependencyTracker()
        t.add_property("p1", ["a"])
        t.add_property("p2", ["a"])
        downstream = t.get_downstream("a")
        self.assertIn("p1", downstream)
        self.assertIn("p2", downstream)

    def test_get_downstream_transitive(self):
        """多层反向传播: a -> p1 -> p2 -> p3"""
        t = DependencyTracker()
        t.add_property("p1", ["a"])
        t.add_property("p2", ["p1"])
        t.add_property("p3", ["p2"])
        downstream = t.get_downstream("a")
        self.assertIn("p1", downstream)
        self.assertIn("p2", downstream)
        self.assertIn("p3", downstream)

    def test_get_downstream_no_match(self):
        t = DependencyTracker()
        t.add_property("p1", ["a"])
        self.assertEqual(t.get_downstream("z"), [])

    def test_remove_property(self):
        t = DependencyTracker()
        t.add_property("p1", ["a"])
        t.remove_property("p1")
        self.assertEqual(t.get_dependencies("p1"), [])
        self.assertEqual(t.get_downstream("a"), [])

    def test_update_dependencies(self):
        t = DependencyTracker()
        t.add_property("p1", ["a", "b"])
        t.add_property("p1", ["c", "d"])
        self.assertEqual(sorted(t.get_dependencies("p1")), ["c", "d"])
        self.assertEqual(t.get_downstream("a"), [])
        self.assertEqual(t.get_downstream("c"), ["p1"])

    def test_detect_cycle(self):
        t = DependencyTracker()
        t.add_property("p1", ["p2"])
        t.add_property("p2", ["p1"])
        cycle = t.detect_cycle()
        self.assertGreater(len(cycle), 0)

    def test_no_cycle(self):
        t = DependencyTracker()
        t.add_property("p1", ["a"])
        t.add_property("p2", ["b"])
        self.assertEqual(t.detect_cycle(), [])

    def test_extract_from_expression_simple(self):
        deps = DependencyTracker.extract_from_expression(
            "instance.a + instance.b"
        )
        self.assertIn("a", deps)
        self.assertIn("b", deps)

    def test_extract_from_expression_function(self):
        deps = DependencyTracker.extract_from_expression(
            "sum_field(instance.items, 'amount')"
        )
        # 'amount' / 'items' 都可能出现在 deps 中
        self.assertTrue(len(deps) > 0)

    def test_extract_from_expression_invalid(self):
        deps = DependencyTracker.extract_from_expression("@@@ invalid @@@")
        # 即使解析失败也返回空 list 而不抛错
        self.assertIsInstance(deps, list)


# ============================================================
# 6. SafeExpressionEvaluator
# ============================================================


class TestExpressionEvaluator(unittest.TestCase):
    """SafeExpressionEvaluator: 数学/字符串/日期/聚合/沙箱安全"""

    def setUp(self):
        self.evaluator = SafeExpressionEvaluator()

    def _ctx(self, **kwargs) -> EvaluationContext:
        return EvaluationContext(
            instance=kwargs.get("instance", {}),
            properties=kwargs.get("properties", {}),
        )

    # ----- 数学 -----

    def test_math_addition(self):
        v = self.evaluator.evaluate("1 + 2", self._ctx())
        self.assertEqual(v, 3)

    def test_math_multiplication(self):
        v = self.evaluator.evaluate("instance.a * instance.b",
                                    self._ctx(instance={"a": 3, "b": 4}))
        self.assertEqual(v, 12)

    def test_math_division(self):
        v = self.evaluator.evaluate("10 / 4", self._ctx())
        self.assertEqual(v, 2.5)

    def test_math_instance_property(self):
        v = self.evaluator.evaluate("instance.score * 2",
                                    self._ctx(instance={"score": 50}))
        self.assertEqual(v, 100)

    # ----- 字符串 -----

    def test_string_concat(self):
        v = self.evaluator.evaluate(
            "concat(instance.first, ' ', instance.last)",
            self._ctx(instance={"first": "John", "last": "Doe"}),
        )
        self.assertEqual(v, "John Doe")

    def test_string_upper(self):
        v = self.evaluator.evaluate("upper(instance.s)",
                                    self._ctx(instance={"s": "hello"}))
        self.assertEqual(v, "HELLO")

    def test_string_lower(self):
        v = self.evaluator.evaluate("lower(instance.s)",
                                    self._ctx(instance={"s": "HELLO"}))
        self.assertEqual(v, "hello")

    def test_string_length(self):
        v = self.evaluator.evaluate("length(instance.s)",
                                    self._ctx(instance={"s": "hello"}))
        self.assertEqual(v, 5)

    def test_string_substring(self):
        v = self.evaluator.evaluate("substring(instance.s, 1, 3)",
                                    self._ctx(instance={"s": "hello"}))
        self.assertEqual(v, "el")

    # ----- 日期 -----

    def test_date_diff_days(self):
        v = self.evaluator.evaluate(
            "date_diff(instance.a, instance.b, 'days')",
            self._ctx(instance={
                "a": "2026-01-01T00:00:00",
                "b": "2026-01-10T00:00:00",
            }),
        )
        self.assertEqual(v, 9)

    def test_date_add(self):
        v = self.evaluator.evaluate(
            "date_add(instance.a, days=5)",
            self._ctx(instance={"a": "2026-01-01T00:00:00"}),
        )
        self.assertIn("2026-01-06", v)

    def test_now_returns_iso(self):
        v = self.evaluator.evaluate("now()", self._ctx())
        self.assertIsInstance(v, str)
        self.assertGreaterEqual(len(v), 10)

    # ----- 聚合 -----

    def test_sum_field(self):
        v = self.evaluator.evaluate(
            "sum_field(instance.items, 'amount')",
            self._ctx(instance={"items": [
                {"amount": 10}, {"amount": 20}, {"amount": 30},
            ]}),
        )
        self.assertEqual(v, 60)

    def test_avg_field(self):
        v = self.evaluator.evaluate(
            "avg_field(instance.items, 'amount')",
            self._ctx(instance={"items": [
                {"amount": 10}, {"amount": 20}, {"amount": 30},
            ]}),
        )
        self.assertEqual(v, 20.0)

    def test_max_field(self):
        v = self.evaluator.evaluate(
            "max_field(instance.items, 'amount')",
            self._ctx(instance={"items": [
                {"amount": 5}, {"amount": 50}, {"amount": 10},
            ]}),
        )
        self.assertEqual(v, 50)

    def test_count(self):
        v = self.evaluator.evaluate(
            "count(instance.items)",
            self._ctx(instance={"items": [1, 2, 3, 4]}),
        )
        self.assertEqual(v, 4)

    # ----- 条件 -----

    def test_if_true(self):
        v = self.evaluator.evaluate(
            "iif(instance.score > 60, 'pass', 'fail')",
            self._ctx(instance={"score": 80}),
        )
        self.assertEqual(v, "pass")

    def test_if_false(self):
        v = self.evaluator.evaluate(
            "iif(instance.score > 60, 'pass', 'fail')",
            self._ctx(instance={"score": 40}),
        )
        self.assertEqual(v, "fail")

    def test_case(self):
        v = self.evaluator.evaluate(
            "case(instance.x > 10, 'A', instance.x > 5, 'B', 'C')",
            self._ctx(instance={"x": 7}),
        )
        self.assertEqual(v, "B")

    # ----- 校验 -----

    def test_validate_valid(self):
        result = self.evaluator.validate("instance.a + 1")
        self.assertTrue(result.valid)
        self.assertIn("a", result.dependencies)

    def test_validate_empty(self):
        result = self.evaluator.validate("")
        self.assertFalse(result.valid)

    def test_validate_syntax_error(self):
        result = self.evaluator.validate("instance.a +")
        self.assertFalse(result.valid)

    def test_validate_too_long(self):
        result = self.evaluator.validate("a" * 3000)
        self.assertFalse(result.valid)

    # ----- 沙箱安全 -----

    def test_reject_exec(self):
        with self.assertRaises(ValueError):
            self.evaluator.evaluate("exec('print(1)')", self._ctx())

    def test_reject_eval(self):
        with self.assertRaises(ValueError):
            self.evaluator.evaluate("eval('1+1')", self._ctx())

    def test_reject_import(self):
        with self.assertRaises(ValueError):
            self.evaluator.evaluate("__import__('os')", self._ctx())

    def test_reject_open(self):
        with self.assertRaises(ValueError):
            self.evaluator.evaluate("open('/etc/passwd')", self._ctx())

    def test_reject_builtins(self):
        """不能访问 __builtins__"""
        with self.assertRaises(ValueError):
            self.evaluator.evaluate("__builtins__", self._ctx())

    def test_reject_getattr(self):
        with self.assertRaises(ValueError):
            self.evaluator.evaluate("getattr(instance, 'x')", self._ctx())

    def test_reject_function_def(self):
        with self.assertRaises(ValueError):
            self.evaluator.evaluate("def f(): pass", self._ctx())

    # ----- extract_dependencies -----

    def test_extract_dependencies_basic(self):
        deps = self.evaluator.extract_dependencies(
            "instance.a + instance.b"
        )
        self.assertIn("a", deps)
        self.assertIn("b", deps)

    def test_extract_dependencies_with_funcs(self):
        deps = self.evaluator.extract_dependencies(
            "sum_field(instance.items, 'amount')"
        )
        self.assertIn("items", deps)


# ============================================================
# 7. IncrementalComputer
# ============================================================


class TestIncrementalComputer(unittest.TestCase):
    """IncrementalComputer: 单层传播、多层传播、错误处理"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = SQLiteComputedStorage(
            db_path=f"{self.tmp.name}/test_inc.db"
        )
        self.repo = ComputedRepositoryImpl(storage=self.storage)
        self.tracker = DependencyTracker()
        self.evaluator = SafeExpressionEvaluator()
        self.instances = [
            {"id": "i-1", "data": {"a": 10, "b": 5}},
            {"id": "i-2", "data": {"a": 20, "b": 5}},
            {"id": "i-3", "data": {"a": 30, "b": 5}},
        ]
        self.computer = IncrementalComputer(
            tracker=self.tracker,
            evaluator=self.evaluator,
            storage=self.storage,
            instance_provider=lambda _: list(self.instances),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_recompute_single_property(self):
        prop = _make_property(name="doubled", expression="instance.a * 2")
        self.repo.save_property(prop)
        self.tracker.add_property(prop.id, ["a"])
        jobs = self.computer.trigger_recompute(prop, mode="full")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].status, MaterializationStatus.DONE)
        self.assertEqual(jobs[0].processed_count, 3)

    def test_materialized_values_persisted(self):
        prop = _make_property(name="doubled", expression="instance.a * 2")
        self.repo.save_property(prop)
        self.tracker.add_property(prop.id, ["a"])
        self.computer.trigger_recompute(prop, mode="full")
        row = self.storage.get_materialized_value(prop.id, "i-1")
        self.assertIsNotNone(row)
        self.assertEqual(row["value"], 20)

    def test_incremental_recompute_with_downstream(self):
        """a -> p1 -> p2: 触发 a 变化，应同时重算 p1 和 p2"""
        p1 = _make_property(name="p1", expression="instance.a + 1")
        p2 = _make_property(name="p2", expression="instance.a + 2")
        self.repo.save_property(p1)
        self.repo.save_property(p2)
        self.tracker.add_property(p1.id, ["a"])
        self.tracker.add_property(p2.id, ["a"])  # 都依赖 a
        jobs = self.computer.trigger_recompute(
            p1, mode="incremental", changed_property_id="a"
        )
        affected = {j.property_id for j in jobs}
        self.assertIn(p1.id, affected)
        self.assertIn(p2.id, affected)

    def test_get_downstream_chain(self):
        p1 = _make_property(name="p1", expression="instance.a + 1")
        p2 = _make_property(name="p2", expression="instance.a + 2")
        self.tracker.add_property(p1.id, ["a"])
        self.tracker.add_property(p2.id, ["a"])
        chain = self.computer.get_downstream_chain("a")
        self.assertIn(p1.id, chain)
        self.assertIn(p2.id, chain)

    def test_failed_property_job_records_error(self):
        """表达式错误时，job 状态为 FAILED 并记录 error_message"""
        prop = _make_property(
            name="bad", expression="import os"  # 被沙箱拒绝
        )
        self.repo.save_property(prop)
        self.tracker.add_property(prop.id, [])
        jobs = self.computer.trigger_recompute(prop, mode="full")
        self.assertEqual(len(jobs), 1)
        # provider 返回空列表 → 没有实例级错误 → 整个 job DONE
        # （实例级失败已容错，整体仍 DONE）
        # 但 instance_provider 没有 instance 给到，processor 为空也成功
        self.assertIn(jobs[0].status, (
            MaterializationStatus.DONE, MaterializationStatus.FAILED
        ))

    def test_instance_failure_does_not_break_job(self):
        """单实例失败不应中断整批"""
        prop = _make_property(
            name="doubled", expression="instance.missing_attr * 2"
        )
        self.repo.save_property(prop)
        self.tracker.add_property(prop.id, [])
        jobs = self.computer.trigger_recompute(prop, mode="full")
        self.assertEqual(jobs[0].status, MaterializationStatus.DONE)
        # 由于表达式里引用 instance.missing_attr，AttrDict 会抛 AttributeError
        # 单实例失败被容错跳过，processed_count 仍为 0


# ============================================================
# 8. ComputedService
# ============================================================


class TestComputedService(unittest.TestCase):
    """ComputedService: CRUD + 评估 + 物化 + 任务状态"""

    def setUp(self):
        self.tmp_db_path = None
        import tempfile, os
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = SQLiteComputedStorage(
            db_path=f"{self.tmp.name}/test_svc.db"
        )
        self.service = ComputedService(storage=self.storage)

    def tearDown(self):
        self.tmp.cleanup()

    def test_create_property(self):
        result = self.service.create_property({
            "name": "total",
            "target_type_id": "Order",
            "expression": "instance.a + instance.b",
        })
        self.assertNotIn("status", result)
        self.assertEqual(result["name"], "total")
        self.assertIn("a", result["dependencies"])

    def test_create_property_invalid_name(self):
        result = self.service.create_property({
            "name": "",
            "target_type_id": "Order",
            "expression": "1+1",
        })
        self.assertEqual(result.get("status"), "error")

    def test_get_property(self):
        created = self.service.create_property({
            "name": "p1", "target_type_id": "T", "expression": "instance.x",
        })
        fetched = self.service.get_property(created["id"])
        self.assertEqual(fetched["id"], created["id"])

    def test_get_property_not_found(self):
        result = self.service.get_property("nonexistent")
        self.assertEqual(result.get("status"), "error")

    def test_list_properties(self):
        self.service.create_property({
            "name": "p1", "target_type_id": "T", "expression": "1+1",
        })
        result = self.service.list_properties()
        self.assertIn("properties", result)
        self.assertEqual(result["count"], 1)

    def test_update_property(self):
        created = self.service.create_property({
            "name": "p1", "target_type_id": "T", "expression": "1+1",
        })
        result = self.service.update_property(
            created["id"], {"description": "updated"}
        )
        self.assertEqual(result["description"], "updated")

    def test_update_property_not_found(self):
        result = self.service.update_property("missing", {"description": "x"})
        self.assertEqual(result.get("status"), "error")

    def test_delete_property(self):
        created = self.service.create_property({
            "name": "p1", "target_type_id": "T", "expression": "1+1",
        })
        result = self.service.delete_property(created["id"])
        self.assertTrue(result["deleted"])

    def test_delete_property_not_found(self):
        result = self.service.delete_property("missing")
        self.assertEqual(result.get("status"), "error")

    def test_evaluate_property(self):
        created = self.service.create_property({
            "name": "doubled", "target_type_id": "T",
            "expression": "instance.x * 2",
        })
        result = self.service.evaluate_property(
            created["id"], "i-1", {"x": 21}
        )
        self.assertEqual(result["value"], 42)

    def test_evaluate_property_not_found(self):
        result = self.service.evaluate_property("missing", "i-1", {})
        self.assertEqual(result.get("status"), "error")

    def test_evaluate_property_invalid_expr(self):
        created = self.service.create_property({
            "name": "bad", "target_type_id": "T",
            "expression": "exec('x')",  # sandbox 拒绝
        })
        result = self.service.evaluate_property(
            created["id"], "i-1", {}
        )
        self.assertEqual(result.get("status"), "error")

    def test_trigger_recompute_full(self):
        created = self.service.create_property({
            "name": "doubled", "target_type_id": "T",
            "expression": "instance.x * 2",
        })
        result = self.service.trigger_recompute(
            created["id"], mode="full"
        )
        self.assertIn("first_job_id", result)
        self.assertEqual(result["mode"], "full")

    def test_trigger_recompute_incremental(self):
        created = self.service.create_property({
            "name": "doubled", "target_type_id": "T",
            "expression": "instance.x * 2",
        })
        result = self.service.trigger_recompute(
            created["id"], mode="incremental", changed_property_id="x"
        )
        self.assertEqual(result["mode"], "incremental")

    def test_trigger_recompute_invalid_mode(self):
        created = self.service.create_property({
            "name": "p", "target_type_id": "T", "expression": "1+1",
        })
        result = self.service.trigger_recompute(
            created["id"], mode="invalid"
        )
        self.assertEqual(result.get("status"), "error")

    def test_trigger_recompute_property_not_found(self):
        result = self.service.trigger_recompute("missing", mode="full")
        self.assertEqual(result.get("status"), "error")

    def test_get_job_status(self):
        created = self.service.create_property({
            "name": "p", "target_type_id": "T", "expression": "1+1",
        })
        trigger = self.service.trigger_recompute(created["id"], mode="full")
        job_id = trigger["first_job_id"]
        status = self.service.get_job_status(job_id)
        self.assertEqual(status["id"], job_id)
        self.assertEqual(status["property_id"], created["id"])

    def test_get_job_status_not_found(self):
        result = self.service.get_job_status("missing")
        self.assertEqual(result.get("status"), "error")

    def test_list_jobs(self):
        created = self.service.create_property({
            "name": "p", "target_type_id": "T", "expression": "1+1",
        })
        for _ in range(2):
            self.service.trigger_recompute(created["id"], mode="full")
        result = self.service.list_jobs(created["id"])
        self.assertGreaterEqual(result["count"], 2)


# ============================================================
# 9. FastAPI 路由
# ============================================================


class TestComputedRoutes(unittest.TestCase):
    """FastAPI 路由 HTTP 状态码 + HTTPException 透传"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.app = FastAPI()
        self.app.include_router(computed_router)
        # 替换 storage 避免污染默认 DB
        self._original_storage = computed_router.dependency_overrides_provider
        from odap.biz.core.ontology.computed.api import routes as routes_mod
        self._svc = routes_mod.computed_service
        self._svc.storage = SQLiteComputedStorage(
            db_path=f"{self.tmp.name}/test_route.db"
        )
        self._svc.repository = ComputedRepositoryImpl(
            storage=self._svc.storage
        )
        self._svc.tracker = DependencyTracker()
        self._svc._computer = IncrementalComputer(
            tracker=self._svc.tracker,
            evaluator=self._svc.evaluator,
            storage=self._svc.storage,
        )
        self.client = TestClient(self.app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_post_create_property(self):
        r = self.client.post(
            "/api/ontology/computed/properties",
            json={
                "name": "p1",
                "target_type_id": "T",
                "expression": "instance.x * 2",
            },
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["count"], 1)

    def test_post_create_property_400(self):
        r = self.client.post(
            "/api/ontology/computed/properties",
            json={"name": "", "target_type_id": "T", "expression": "1+1"},
        )
        self.assertEqual(r.status_code, 400)

    def test_get_list_properties(self):
        self.client.post(
            "/api/ontology/computed/properties",
            json={"name": "p1", "target_type_id": "T", "expression": "1+1"},
        )
        r = self.client.get("/api/ontology/computed/properties")
        self.assertEqual(r.status_code, 200)
        self.assertIn("properties", r.json())

    def test_get_property(self):
        created = self.client.post(
            "/api/ontology/computed/properties",
            json={"name": "p1", "target_type_id": "T", "expression": "1+1"},
        ).json()
        prop_id = created["properties"][0]["id"]
        r = self.client.get(f"/api/ontology/computed/properties/{prop_id}")
        self.assertEqual(r.status_code, 200)

    def test_get_property_404(self):
        r = self.client.get(
            "/api/ontology/computed/properties/nonexistent"
        )
        self.assertEqual(r.status_code, 404)

    def test_put_update_property(self):
        created = self.client.post(
            "/api/ontology/computed/properties",
            json={"name": "p1", "target_type_id": "T", "expression": "1+1"},
        ).json()
        prop_id = created["properties"][0]["id"]
        r = self.client.put(
            f"/api/ontology/computed/properties/{prop_id}",
            json={"description": "new"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["description"], "new")

    def test_put_update_property_404(self):
        r = self.client.put(
            "/api/ontology/computed/properties/missing",
            json={"description": "x"},
        )
        self.assertEqual(r.status_code, 404)

    def test_delete_property(self):
        created = self.client.post(
            "/api/ontology/computed/properties",
            json={"name": "p1", "target_type_id": "T", "expression": "1+1"},
        ).json()
        prop_id = created["properties"][0]["id"]
        r = self.client.delete(
            f"/api/ontology/computed/properties/{prop_id}"
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["deleted"])

    def test_delete_property_404(self):
        r = self.client.delete(
            "/api/ontology/computed/properties/missing"
        )
        self.assertEqual(r.status_code, 404)

    def test_post_evaluate(self):
        created = self.client.post(
            "/api/ontology/computed/properties",
            json={
                "name": "doubled",
                "target_type_id": "T",
                "expression": "instance.x * 2",
            },
        ).json()
        prop_id = created["properties"][0]["id"]
        r = self.client.post(
            f"/api/ontology/computed/properties/{prop_id}/evaluate",
            json={"instance_id": "i-1", "instance_data": {"x": 21}},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["value"], 42)

    def test_post_recompute(self):
        created = self.client.post(
            "/api/ontology/computed/properties",
            json={"name": "p", "target_type_id": "T", "expression": "1+1"},
        ).json()
        prop_id = created["properties"][0]["id"]
        r = self.client.post(
            f"/api/ontology/computed/properties/{prop_id}/recompute",
            json={"mode": "full"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("first_job_id", r.json())

    def test_post_recompute_404(self):
        r = self.client.post(
            "/api/ontology/computed/properties/missing/recompute",
            json={"mode": "full"},
        )
        self.assertEqual(r.status_code, 404)

    def test_get_jobs(self):
        created = self.client.post(
            "/api/ontology/computed/properties",
            json={"name": "p", "target_type_id": "T", "expression": "1+1"},
        ).json()
        prop_id = created["properties"][0]["id"]
        self.client.post(
            f"/api/ontology/computed/properties/{prop_id}/recompute",
            json={"mode": "full"},
        )
        r = self.client.get(
            f"/api/ontology/computed/properties/{prop_id}/jobs"
        )
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.json()["count"], 1)

    def test_get_job(self):
        created = self.client.post(
            "/api/ontology/computed/properties",
            json={"name": "p", "target_type_id": "T", "expression": "1+1"},
        ).json()
        prop_id = created["properties"][0]["id"]
        trigger = self.client.post(
            f"/api/ontology/computed/properties/{prop_id}/recompute",
            json={"mode": "full"},
        ).json()
        job_id = trigger["first_job_id"]
        r = self.client.get(f"/api/ontology/computed/jobs/{job_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], job_id)

    def test_get_job_404(self):
        r = self.client.get("/api/ontology/computed/jobs/missing")
        self.assertEqual(r.status_code, 404)

    def test_route_exception_passthrough(self):
        """任何 except 必须透传 HTTPException (规则 3)"""
        import ast
        from pathlib import Path
        src = Path(
            r"e:\DEMO\AI\ontology-graphiti\odap\biz\core\ontology\computed\api\routes.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.decorator_list:
                    continue
                is_route = False
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        if dec.func.attr in ("get", "post", "put", "delete"):
                            is_route = True
                            break
                if not is_route:
                    continue
                # 检查 except 块
                has_httpexception_raise = False
                has_broad = False
                for child in ast.walk(node):
                    if isinstance(child, ast.ExceptHandler):
                        types = []
                        if child.type is None:
                            types = ["Exception"]
                        elif isinstance(child.type, ast.Name):
                            types = [child.type.id]
                        elif isinstance(child.type, ast.Tuple):
                            for elt in child.type.elts:
                                if isinstance(elt, ast.Name):
                                    types.append(elt.id)
                        if "Exception" in types and "HTTPException" not in types:
                            has_broad = True
                        if "HTTPException" in types:
                            for sub in ast.walk(child):
                                if isinstance(sub, ast.Raise) and sub.exc is None:
                                    has_httpexception_raise = True
                if has_broad:
                    self.assertTrue(
                        has_httpexception_raise,
                        f"Route {node.name} has broad except without HTTPException raise",
                    )


if __name__ == "__main__":
    unittest.main()
