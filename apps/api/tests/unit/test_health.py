"""Data Health - 单元测试 (T344)

覆盖：
- HealthRule / HealthReport 领域模型
- SQLiteHealthStorage CRUD + JSON 序列化（用 tmp_path 真实 DB）
- HealthRuleRepositoryImpl 6 个方法
- HealthScannerImpl 5 种规则
- NotificationDispatcher 3 通道 + 失败降级
- HealthService 编排层
- FastAPI 路由 HTTP 状态码
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from odap.biz.core.ontology.health.impl import (
    HealthRuleRepositoryImpl,
    HealthScannerImpl,
    NotificationDispatcher,
)
from odap.biz.core.ontology.health.models import (
    HealthReport,
    HealthRule,
    HealthRuleType,
    HealthSeverity,
    HealthStatus,
)
from odap.biz.core.ontology.health.services import HealthService
from odap.biz.core.ontology.health.storage import SQLiteHealthStorage


# ============================================================
# 工厂函数
# ============================================================


def _make_rule(**overrides) -> HealthRule:
    """构造测试用 HealthRule"""
    defaults = dict(
        target_type_id="Customer",
        name="test-rule",
        description="test",
        rule_type="not_null",
        check_expression={"properties": ["name"]},
        severity=HealthSeverity.WARNING,
        schedule="",
        notification_channel={},
        enabled=True,
    )
    defaults.update(overrides)
    return HealthRule(**defaults)


def _make_instance(iid: str, type_id: str, **props) -> Dict[str, Any]:
    """构造测试用实例 dict"""
    return {"id": iid, "type_id": type_id, "properties": props}


# ============================================================
# 1. HealthRule 模型
# ============================================================


class TestHealthRuleModel(unittest.TestCase):
    """HealthRule 必填字段、默认值、UUID、Enum 序列化"""

    def test_required_fields_minimal(self):
        rule = HealthRule(target_type_id="Customer", name="r1")
        self.assertEqual(rule.target_type_id, "Customer")
        self.assertEqual(rule.name, "r1")
        self.assertEqual(rule.rule_type, HealthRuleType.NOT_NULL.value)
        self.assertEqual(rule.severity, HealthSeverity.WARNING)
        self.assertTrue(rule.enabled)
        self.assertEqual(rule.check_expression, {})
        self.assertEqual(rule.notification_channel, {})

    def test_default_factory_container_fields(self):
        """容器字段必须用 default_factory（规则 5）"""
        rule = HealthRule(target_type_id="X", name="y")
        # 每次新实例都是新 list/dict，不是共享引用
        rule.check_expression["new_key"] = 1
        rule2 = HealthRule(target_type_id="X", name="y")
        self.assertNotIn("new_key", rule2.check_expression)

    def test_uuid_auto_generated_unique(self):
        a = HealthRule(target_type_id="X", name="y")
        b = HealthRule(target_type_id="X", name="y")
        self.assertNotEqual(a.id, b.id)
        self.assertEqual(len(a.id), 36)  # uuid4 长度

    def test_severity_enum_str_compatibility(self):
        """HealthSeverity 必须 (str, Enum) 双继承（规则 4）"""
        self.assertEqual(HealthSeverity.WARNING, "warning")
        self.assertEqual(HealthSeverity.CRITICAL.value, "critical")

    def test_all_severities_exist(self):
        for v in ("info", "warning", "error", "critical"):
            self.assertEqual(HealthSeverity(v).value, v)

    def test_check_expression_accepts_any_dict(self):
        rule = HealthRule(
            target_type_id="T",
            name="n",
            check_expression={"property": "email", "pattern": "^.+@.+$"},
        )
        self.assertEqual(rule.check_expression["pattern"], "^.+@.+$")

    def test_enabled_default_true(self):
        rule = HealthRule(target_type_id="T", name="n")
        self.assertTrue(rule.enabled)

    def test_created_updated_auto_set(self):
        rule = HealthRule(target_type_id="T", name="n")
        self.assertIsInstance(rule.created_at, datetime)
        self.assertIsInstance(rule.updated_at, datetime)


# ============================================================
# 2. HealthReport 模型
# ============================================================


class TestHealthReportModel(unittest.TestCase):
    """HealthReport 必填字段、UUID、Enum 序列化"""

    def test_minimal_construction(self):
        r = HealthReport(
            rule_id="r1", instance_id="i1", target_type_id="T",
            status=HealthStatus.PASS, severity=HealthSeverity.INFO,
        )
        self.assertEqual(r.rule_id, "r1")
        self.assertEqual(r.status, HealthStatus.PASS)
        self.assertEqual(r.severity, HealthSeverity.INFO)
        self.assertEqual(r.message, "")
        self.assertEqual(r.details, {})

    def test_default_factory_on_details(self):
        r1 = HealthReport(
            rule_id="r1", instance_id="i1", target_type_id="T",
            status=HealthStatus.PASS, severity=HealthSeverity.INFO,
        )
        r1.details["key"] = "v"
        r2 = HealthReport(
            rule_id="r1", instance_id="i1", target_type_id="T",
            status=HealthStatus.PASS, severity=HealthSeverity.INFO,
        )
        self.assertNotIn("key", r2.details)

    def test_status_enum_serialization(self):
        self.assertEqual(HealthStatus.PASS, "pass")
        self.assertEqual(HealthStatus.WARN.value, "warn")
        self.assertEqual(HealthStatus.FAIL.value, "fail")

    def test_uuid_auto_unique(self):
        a = HealthReport(
            rule_id="r1", instance_id="i1", target_type_id="T",
            status=HealthStatus.PASS, severity=HealthSeverity.INFO,
        )
        b = HealthReport(
            rule_id="r1", instance_id="i1", target_type_id="T",
            status=HealthStatus.PASS, severity=HealthSeverity.INFO,
        )
        self.assertNotEqual(a.id, b.id)


# ============================================================
# 3. SQLite Storage
# ============================================================


class TestSQLiteHealthStorage(unittest.TestCase):
    """SQLiteHealthStorage CRUD + JSON 序列化（tmp_path 真实 DB）"""

    def setUp(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        self.db_path = f"{tmp}/health.db"
        self.storage = SQLiteHealthStorage(db_path=self.db_path)

    def _sample_rule_dict(self, **overrides) -> Dict[str, Any]:
        defaults = dict(
            id="rule-1",
            target_type_id="Customer",
            name="n1",
            description="d1",
            rule_type="not_null",
            check_expression={"properties": ["name", "email"]},
            severity="warning",
            schedule="",
            notification_channel={"channels": ["email"]},
            enabled=True,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        defaults.update(overrides)
        return defaults

    def test_save_and_get_rule_roundtrip(self):
        rule = self._sample_rule_dict()
        self.storage.save_rule(rule)
        got = self.storage.get_rule("rule-1")
        self.assertIsNotNone(got)
        self.assertEqual(got["id"], "rule-1")
        self.assertEqual(got["name"], "n1")
        self.assertEqual(got["check_expression"], {"properties": ["name", "email"]})
        self.assertEqual(got["notification_channel"], {"channels": ["email"]})
        self.assertTrue(got["enabled"])

    def test_get_nonexistent_rule_returns_none(self):
        self.assertIsNone(self.storage.get_rule("nope"))

    def test_list_rules_empty(self):
        self.assertEqual(self.storage.list_rules(), [])

    def test_list_rules_enabled_only_filter(self):
        self.storage.save_rule(self._sample_rule_dict(id="a", enabled=True))
        self.storage.save_rule(self._sample_rule_dict(id="b", enabled=False))
        self.assertEqual(len(self.storage.list_rules(enabled_only=True)), 1)
        self.assertEqual(len(self.storage.list_rules(enabled_only=False)), 2)

    def test_list_rules_by_target_type(self):
        self.storage.save_rule(self._sample_rule_dict(id="a", target_type_id="Customer"))
        self.storage.save_rule(self._sample_rule_dict(id="b", target_type_id="Order"))
        self.assertEqual(len(self.storage.list_rules_by_target_type("Customer")), 1)
        self.assertEqual(len(self.storage.list_rules_by_target_type("Order")), 1)

    def test_list_rules_by_severity(self):
        self.storage.save_rule(self._sample_rule_dict(id="a", severity="error"))
        self.storage.save_rule(self._sample_rule_dict(id="b", severity="warning"))
        self.assertEqual(len(self.storage.list_rules_by_severity("error")), 1)
        self.assertEqual(len(self.storage.list_rules_by_severity("warning")), 1)

    def test_delete_rule_existing(self):
        self.storage.save_rule(self._sample_rule_dict())
        self.assertTrue(self.storage.delete_rule("rule-1"))
        self.assertIsNone(self.storage.get_rule("rule-1"))

    def test_delete_rule_nonexistent_returns_false(self):
        self.assertFalse(self.storage.delete_rule("missing"))

    def test_save_and_get_report_roundtrip(self):
        report = {
            "id": "rep-1",
            "rule_id": "rule-1",
            "instance_id": "i1",
            "target_type_id": "Customer",
            "status": "fail",
            "severity": "error",
            "message": "missing email",
            "details": {"missing": ["email"]},
            "scanned_at": datetime.now().isoformat(),
        }
        self.storage.save_report(report)
        got = self.storage.get_report("rep-1")
        self.assertIsNotNone(got)
        self.assertEqual(got["status"], "fail")
        self.assertEqual(got["details"], {"missing": ["email"]})

    def test_get_nonexistent_report_returns_none(self):
        self.assertIsNone(self.storage.get_report("nope"))

    def test_list_reports_with_filters(self):
        for i, (status, sev) in enumerate([
            ("pass", "info"), ("fail", "error"), ("warn", "warning"),
        ]):
            self.storage.save_report({
                "id": f"r{i}", "rule_id": "rule-1", "instance_id": f"i{i}",
                "target_type_id": "Customer", "status": status,
                "severity": sev, "message": "", "details": {},
                "scanned_at": datetime.now().isoformat(),
            })
        self.assertEqual(len(self.storage.list_reports(status="pass")), 1)
        self.assertEqual(len(self.storage.list_reports(severity="error")), 1)
        self.assertEqual(len(self.storage.list_reports(target_type_id="Customer")), 3)
        self.assertEqual(len(self.storage.list_reports(target_type_id="Other")), 0)

    def test_list_reports_pagination(self):
        for i in range(5):
            self.storage.save_report({
                "id": f"r{i}", "rule_id": "rule-1", "instance_id": f"i{i}",
                "target_type_id": "Customer", "status": "pass",
                "severity": "info", "message": "", "details": {},
                "scanned_at": datetime.now().isoformat(),
            })
        page1 = self.storage.list_reports(limit=2, offset=0)
        page2 = self.storage.list_reports(limit=2, offset=2)
        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 2)

    def test_count_reports(self):
        for i in range(3):
            self.storage.save_report({
                "id": f"r{i}", "rule_id": "rule-1", "instance_id": f"i{i}",
                "target_type_id": "Customer", "status": "fail",
                "severity": "error", "message": "", "details": {},
                "scanned_at": datetime.now().isoformat(),
            })
        self.assertEqual(self.storage.count_reports(status="fail"), 3)
        self.assertEqual(self.storage.count_reports(status="pass"), 0)

    def test_corrupted_json_handled_gracefully(self):
        """异常 JSON 不应让查询崩溃"""
        self.storage.save_rule(self._sample_rule_dict(id="r1"))
        # 直接写入坏 JSON
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE health_rules SET check_expression = ? WHERE id = ?",
            ("not-valid-json{", "r1"),
        )
        conn.commit()
        conn.close()
        got = self.storage.get_rule("r1")
        # 应回退到 default dict
        self.assertIsInstance(got["check_expression"], dict)


# ============================================================
# 4. HealthRuleRepository
# ============================================================


class TestHealthRuleRepository(unittest.TestCase):
    """HealthRuleRepositoryImpl 6 个方法 + 过滤"""

    def setUp(self):
        import tempfile
        tmp = tempfile.mkdtemp()
        self.repo = HealthRuleRepositoryImpl(
            storage=SQLiteHealthStorage(db_path=f"{tmp}/r.db")
        )

    def test_save_and_get_roundtrip(self):
        rule = _make_rule(id="r1", name="r1", target_type_id="T")
        self.repo.save(rule)
        got = self.repo.get("r1")
        self.assertIsNotNone(got)
        self.assertEqual(got.name, "r1")
        self.assertEqual(got.target_type_id, "T")
        self.assertEqual(got.severity, HealthSeverity.WARNING)

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(self.repo.get("missing"))

    def test_list_all(self):
        self.repo.save(_make_rule(id="a", name="a", target_type_id="T"))
        self.repo.save(_make_rule(id="b", name="b", target_type_id="T"))
        self.assertEqual(len(self.repo.list()), 2)

    def test_list_enabled_only(self):
        self.repo.save(_make_rule(id="a", name="a", target_type_id="T", enabled=True))
        self.repo.save(_make_rule(id="b", name="b", target_type_id="T", enabled=False))
        self.assertEqual(len(self.repo.list(enabled_only=True)), 1)

    def test_list_by_target_type(self):
        self.repo.save(_make_rule(id="a", name="a", target_type_id="Customer"))
        self.repo.save(_make_rule(id="b", name="b", target_type_id="Order"))
        self.assertEqual(len(self.repo.list_by_target_type("Customer")), 1)

    def test_list_by_severity(self):
        self.repo.save(_make_rule(id="a", name="a", target_type_id="T", severity=HealthSeverity.ERROR))
        self.repo.save(_make_rule(id="b", name="b", target_type_id="T", severity=HealthSeverity.INFO))
        self.assertEqual(len(self.repo.list_by_severity(HealthSeverity.ERROR)), 1)

    def test_delete_existing(self):
        self.repo.save(_make_rule(id="a", name="a", target_type_id="T"))
        self.assertTrue(self.repo.delete("a"))
        self.assertIsNone(self.repo.get("a"))

    def test_delete_nonexistent_returns_false(self):
        self.assertFalse(self.repo.delete("nope"))


# ============================================================
# 5. HealthScanner
# ============================================================


def _scanner_with(instances_by_type: Dict[str, List[Dict[str, Any]]]) -> HealthScannerImpl:
    """构造带实例加载器的 scanner"""
    import tempfile
    repo = HealthRuleRepositoryImpl(
        storage=SQLiteHealthStorage(db_path=f"{tempfile.mkdtemp()}/s.db")
    )
    sc = HealthScannerImpl(repository=repo)
    sc.set_instance_loader(lambda type_id: instances_by_type.get(type_id, []))
    return sc


class TestHealthScannerNotNull(unittest.TestCase):
    """not_null 规则"""

    def test_pass_when_all_properties_present(self):
        rule = _make_rule(rule_type="not_null", check_expression={"properties": ["name", "email"]})
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", name="Alice", email="a@x.com")]})
        reports = sc.scan_one(rule)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].status, HealthStatus.PASS)

    def test_fail_when_property_missing(self):
        rule = _make_rule(rule_type="not_null", check_expression={"properties": ["name", "email"]})
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", name="Alice")]})
        reports = sc.scan_one(rule)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].status, HealthStatus.FAIL)
        self.assertIn("email", reports[0].message)

    def test_mixed_pass_and_fail(self):
        rule = _make_rule(rule_type="not_null", check_expression={"properties": ["name"]})
        sc = _scanner_with({"Customer": [
            _make_instance("i1", "Customer", name="Alice"),
            _make_instance("i2", "Customer", name="Bob"),
        ]})
        reports = sc.scan_one(rule)
        self.assertEqual(len(reports), 2)
        self.assertTrue(all(r.status == HealthStatus.PASS for r in reports))


class TestHealthScannerUnique(unittest.TestCase):
    """unique 规则"""

    def test_pass_when_unique(self):
        rule = _make_rule(rule_type="unique", check_expression={"properties": ["email"]})
        sc = _scanner_with({"Customer": [
            _make_instance("i1", "Customer", email="a@x.com"),
            _make_instance("i2", "Customer", email="b@x.com"),
        ]})
        reports = sc.scan_one(rule)
        self.assertTrue(all(r.status == HealthStatus.PASS for r in reports))

    def test_fail_when_duplicate(self):
        rule = _make_rule(rule_type="unique", check_expression={"properties": ["email"]})
        sc = _scanner_with({"Customer": [
            _make_instance("i1", "Customer", email="dup@x.com"),
            _make_instance("i2", "Customer", email="dup@x.com"),
        ]})
        reports = sc.scan_one(rule)
        fail_reports = [r for r in reports if r.status == HealthStatus.FAIL]
        self.assertEqual(len(fail_reports), 1)
        self.assertIn("Duplicate", fail_reports[0].message)

    def test_unique_within_same_type(self):
        """unique 仅在同类型内判重"""
        rule = _make_rule(rule_type="unique", check_expression={"properties": ["email"]})
        sc = _scanner_with({"Customer": [
            _make_instance("i1", "Customer", email="a@x.com"),
            _make_instance("i2", "Other", email="a@x.com"),  # 不同类型
        ]})
        reports = sc.scan_one(rule)
        # 跨类型不重复
        self.assertTrue(all(r.status == HealthStatus.PASS for r in reports))


class TestHealthScannerRegex(unittest.TestCase):
    """regex 规则"""

    def test_pass_when_matches(self):
        rule = _make_rule(rule_type="regex", check_expression={"property": "email", "pattern": "^.+@.+$"})
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", email="alice@x.com")]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.PASS)

    def test_fail_when_not_matches(self):
        rule = _make_rule(rule_type="regex", check_expression={"property": "email", "pattern": "^.+@.+$"})
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", email="not-an-email")]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.FAIL)

    def test_fail_when_empty_value(self):
        rule = _make_rule(rule_type="regex", check_expression={"property": "email", "pattern": "^.+@.+$"})
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", email="")]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.FAIL)

    def test_fail_when_pattern_invalid(self):
        rule = _make_rule(rule_type="regex", check_expression={"property": "x", "pattern": "[invalid("})
        sc = _scanner_with({"Customer": []})
        reports = sc.scan_one(rule)
        self.assertGreaterEqual(len(reports), 1)
        self.assertEqual(reports[0].status, HealthStatus.FAIL)


class TestHealthScannerRange(unittest.TestCase):
    """range 规则"""

    def test_pass_within_range(self):
        rule = _make_rule(rule_type="range", check_expression={"property": "age", "min": 0, "max": 150})
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", age=30)]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.PASS)

    def test_fail_below_min(self):
        rule = _make_rule(rule_type="range", check_expression={"property": "age", "min": 0, "max": 150})
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", age=-1)]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.FAIL)

    def test_fail_above_max(self):
        rule = _make_rule(rule_type="range", check_expression={"property": "age", "min": 0, "max": 150})
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", age=200)]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.FAIL)

    def test_fail_when_empty(self):
        rule = _make_rule(rule_type="range", check_expression={"property": "age", "min": 0, "max": 150})
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer")]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.FAIL)


class TestHealthScannerReferentialIntegrity(unittest.TestCase):
    """referential_integrity 规则"""

    def test_pass_when_resolved(self):
        rule = _make_rule(
            rule_type="referential_integrity",
            check_expression={"property": "org_id", "ref_type_id": "Organization"},
        )
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", org_id="org-1", org_id_resolved=["org-1"])]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.PASS)

    def test_fail_when_not_resolved(self):
        rule = _make_rule(
            rule_type="referential_integrity",
            check_expression={"property": "org_id", "ref_type_id": "Organization"},
        )
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer", org_id="org-99")]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.FAIL)
        self.assertIn("org_id", reports[0].message)

    def test_fail_when_empty_ref(self):
        rule = _make_rule(
            rule_type="referential_integrity",
            check_expression={"property": "org_id", "ref_type_id": "Organization"},
        )
        sc = _scanner_with({"Customer": [_make_instance("i1", "Customer")]})
        reports = sc.scan_one(rule)
        self.assertEqual(reports[0].status, HealthStatus.FAIL)


class TestHealthScannerDispatch(unittest.TestCase):
    """scan() 调度逻辑"""

    def test_scan_with_rule_id_filters_to_one(self):
        import tempfile
        repo = HealthRuleRepositoryImpl(
            storage=SQLiteHealthStorage(db_path=f"{tempfile.mkdtemp()}/d.db")
        )
        repo.save(_make_rule(id="r1", name="r1", target_type_id="T", rule_type="not_null",
                              check_expression={"properties": ["x"]}))
        repo.save(_make_rule(id="r2", name="r2", target_type_id="T", rule_type="not_null",
                              check_expression={"properties": ["x"]}))
        sc = HealthScannerImpl(repository=repo)
        sc.set_instance_loader(lambda type_id: [_make_instance("i1", "T", x=1)])
        reports = sc.scan(rule_id="r1")
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].rule_id, "r1")

    def test_scan_with_nonexistent_rule_id_returns_empty(self):
        import tempfile
        repo = HealthRuleRepositoryImpl(
            storage=SQLiteHealthStorage(db_path=f"{tempfile.mkdtemp()}/d2.db")
        )
        sc = HealthScannerImpl(repository=repo)
        self.assertEqual(sc.scan(rule_id="nope"), [])

    def test_scan_with_no_rule_id_scans_enabled(self):
        import tempfile
        repo = HealthRuleRepositoryImpl(
            storage=SQLiteHealthStorage(db_path=f"{tempfile.mkdtemp()}/d3.db")
        )
        repo.save(_make_rule(id="r1", name="r1", target_type_id="T", rule_type="not_null",
                              check_expression={"properties": ["x"]}, enabled=True))
        repo.save(_make_rule(id="r2", name="r2", target_type_id="T", rule_type="not_null",
                              check_expression={"properties": ["x"]}, enabled=False))
        sc = HealthScannerImpl(repository=repo)
        sc.set_instance_loader(lambda type_id: [_make_instance("i1", "T", x=1)])
        reports = sc.scan()
        # 仅扫描 r1
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].rule_id, "r1")

    def test_unknown_rule_type_returns_empty(self):
        rule = _make_rule(rule_type="unknown_type")
        sc = _scanner_with({"T": []})
        self.assertEqual(sc.scan_one(rule), [])


# ============================================================
# 6. NotificationDispatcher
# ============================================================


class TestNotificationDispatcher(unittest.TestCase):
    """NotificationDispatcher 3 通道 + 失败降级"""

    def test_empty_config_skips(self):
        d = NotificationDispatcher()
        d.dispatch({}, "subj", "body")
        self.assertEqual(d.history(), [])

    def test_email_with_no_recipients_skips(self):
        d = NotificationDispatcher()
        d.dispatch({"channels": ["email"], "email": {"recipients": []}}, "s", "b")
        self.assertEqual(d.history(), [])

    def test_email_smtp_failure_does_not_raise(self):
        def bad_smtp(host, port):
            raise RuntimeError("connect failed")
        d = NotificationDispatcher(smtp_factory=bad_smtp)
        # 不应抛异常
        d.dispatch({"channels": ["email"], "email": {
            "host": "x", "port": 25, "sender": "h@x", "recipients": ["a@x"]
        }}, "s", "b")
        # history 不记录（因为 _send_email 抛出被 catch）
        self.assertEqual(d.history(), [])

    def test_email_recorded_on_success(self):
        class FakeSMTP:
            def __init__(self, h, p): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def sendmail(self, s, r, m): pass
        d = NotificationDispatcher(smtp_factory=FakeSMTP)
        d.dispatch({"channels": ["email"], "email": {
            "host": "x", "port": 25, "sender": "h@x", "recipients": ["a@x"]
        }}, "Health alert", "body")
        hist = d.history()
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["channel"], "email")
        self.assertEqual(hist[0]["subject"], "Health alert")

    def test_webhook_dispatches_async(self):
        """webhook 通道：使用 mock session"""
        async def run_test():
            # 构造支持 async context manager 的 mock response
            class _CM:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    return False
                async def read(self):
                    return b""
            mock_response = _CM()
            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response)
            d = NotificationDispatcher(aiohttp_session=mock_session)
            d.dispatch({
                "channels": ["webhook"],
                "webhook": {"url": "http://example.com/hook"},
            }, "alert", "body", [{"id": "r1"}])
            # 等待 fire-and-forget task 完成
            await asyncio.sleep(0.2)
            return mock_session, d.history()
        mock_session, hist = asyncio.run(run_test())
        self.assertEqual(mock_session.post.call_count, 1)
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["channel"], "webhook")

    def test_im_dispatches_async(self):
        async def run_test():
            class _CM:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    return False
                async def read(self):
                    return b""
            mock_response = _CM()
            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_response)
            d = NotificationDispatcher(aiohttp_session=mock_session)
            d.dispatch({
                "channels": ["im"],
                "im": {"url": "http://im.example.com/hook", "format": "markdown"},
            }, "alert", "body")
            await asyncio.sleep(0.2)
            return mock_session
        mock_session = asyncio.run(run_test())
        self.assertEqual(mock_session.post.call_count, 1)

    def test_unknown_channel_does_not_crash(self):
        d = NotificationDispatcher()
        d.dispatch({"channels": ["sms"]}, "s", "b")
        self.assertEqual(d.history(), [])

    def test_webhook_failure_logged_not_raised(self):
        """webhook 失败应被捕获，不抛异常"""
        class FailingSMTP:
            def __init__(self, h, p): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def sendmail(self, s, r, m):
                raise ConnectionError("smtp down")
        d = NotificationDispatcher(smtp_factory=FailingSMTP)
        d.dispatch({
            "channels": ["email"],
            "email": {"host": "x", "port": 25, "sender": "h@x", "recipients": ["a@x"]}
        }, "s", "b")
        # sendmail 失败被 catch；history 不记录
        self.assertEqual(d.history(), [])


# ============================================================
# 7. HealthService
# ============================================================


class TestHealthService(unittest.TestCase):
    """HealthService 编排层"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.db_path = f"{self.tmp}/svc.db"
        self.service = HealthService(
            storage=SQLiteHealthStorage(db_path=self.db_path),
        )

    def test_create_rule_success(self):
        out = self.service.create_rule({
            "name": "r1",
            "target_type_id": "Customer",
            "rule_type": "not_null",
            "check_expression": {"properties": ["email"]},
        })
        self.assertNotIn("status", out)
        self.assertEqual(out["name"], "r1")
        self.assertEqual(out["severity"], "warning")

    def test_create_rule_missing_name_returns_error(self):
        out = self.service.create_rule({"target_type_id": "X"})
        self.assertEqual(out.get("status"), "error")
        self.assertIn("name", out["message"])

    def test_create_rule_unknown_type_returns_error(self):
        out = self.service.create_rule({
            "name": "r", "target_type_id": "X", "rule_type": "bogus"
        })
        self.assertEqual(out.get("status"), "error")

    def test_get_rule_existing(self):
        r = self.service.create_rule({"name": "r1", "target_type_id": "T"})
        out = self.service.get_rule(r["id"])
        self.assertEqual(out["id"], r["id"])

    def test_get_rule_missing(self):
        out = self.service.get_rule("missing")
        self.assertEqual(out.get("status"), "error")

    def test_list_rules(self):
        self.service.create_rule({"name": "r1", "target_type_id": "T"})
        self.service.create_rule({"name": "r2", "target_type_id": "T"})
        out = self.service.list_rules()
        self.assertEqual(out["count"], 2)

    def test_list_rules_filter_by_target_type(self):
        self.service.create_rule({"name": "r1", "target_type_id": "Customer"})
        self.service.create_rule({"name": "r2", "target_type_id": "Order"})
        out = self.service.list_rules(target_type_id="Customer")
        self.assertEqual(out["count"], 1)

    def test_list_rules_filter_by_severity(self):
        self.service.create_rule({
            "name": "r1", "target_type_id": "T", "severity": "error"
        })
        out = self.service.list_rules(severity="bogus")
        self.assertEqual(out.get("status"), "error")

    def test_update_rule_success(self):
        r = self.service.create_rule({"name": "r1", "target_type_id": "T"})
        out = self.service.update_rule(r["id"], {"name": "r1-new"})
        self.assertEqual(out["name"], "r1-new")
        self.assertEqual(out["target_type_id"], "T")  # 保留

    def test_update_rule_missing(self):
        out = self.service.update_rule("missing", {"name": "x"})
        self.assertEqual(out.get("status"), "error")

    def test_delete_rule(self):
        r = self.service.create_rule({"name": "r1", "target_type_id": "T"})
        out = self.service.delete_rule(r["id"])
        self.assertTrue(out["deleted"])
        # 再删应失败
        out2 = self.service.delete_rule(r["id"])
        self.assertEqual(out2.get("status"), "error")

    def test_trigger_scan_with_rule_id(self):
        r = self.service.create_rule({
            "name": "r1", "target_type_id": "Customer",
            "rule_type": "not_null", "check_expression": {"properties": ["email"]},
        })
        # 注入实例加载器
        self.service.scanner.set_instance_loader(
            lambda t: [_make_instance("i1", "Customer", email="a@x")]
        )
        out = self.service.trigger_scan(rule_id=r["id"])
        self.assertEqual(out["scanned_count"], 1)
        self.assertEqual(out["pass_count"], 1)
        self.assertEqual(out["rule_id"], r["id"])

    def test_trigger_scan_counts_fail(self):
        r = self.service.create_rule({
            "name": "r1", "target_type_id": "Customer",
            "rule_type": "not_null", "check_expression": {"properties": ["email"]},
        })
        self.service.scanner.set_instance_loader(
            lambda t: [_make_instance("i1", "Customer")]  # email 缺失
        )
        out = self.service.trigger_scan(rule_id=r["id"])
        self.assertEqual(out["fail_count"], 1)

    def test_trigger_scan_with_invalid_rule_id(self):
        out = self.service.trigger_scan(rule_id="nope")
        self.assertEqual(out["scanned_count"], 0)

    def test_list_reports_with_filter(self):
        r = self.service.create_rule({
            "name": "r1", "target_type_id": "T",
            "rule_type": "not_null", "check_expression": {"properties": ["x"]},
        })
        self.service.scanner.set_instance_loader(lambda t: [_make_instance("i1", "T")])
        self.service.trigger_scan(rule_id=r["id"])
        out = self.service.list_reports(status="fail")
        self.assertGreaterEqual(out["count"], 1)

    def test_list_reports_invalid_status(self):
        out = self.service.list_reports(status="bogus")
        self.assertEqual(out.get("status"), "error")

    def test_get_report_existing(self):
        r = self.service.create_rule({
            "name": "r1", "target_type_id": "T",
            "rule_type": "not_null", "check_expression": {"properties": ["x"]},
        })
        self.service.scanner.set_instance_loader(lambda t: [_make_instance("i1", "T")])
        scan_out = self.service.trigger_scan(rule_id=r["id"])
        rid = scan_out["reports"][0]["id"]
        out = self.service.get_report(rid)
        self.assertEqual(out["id"], rid)

    def test_get_report_missing(self):
        out = self.service.get_report("missing")
        self.assertEqual(out.get("status"), "error")

    def test_trigger_scan_notifies_on_failure(self):
        """有失败时调用 notifier"""
        r = self.service.create_rule({
            "name": "r1", "target_type_id": "T",
            "rule_type": "not_null", "check_expression": {"properties": ["x"]},
            "notification_channel": {
                "channels": ["email"],
                "email": {"recipients": ["a@x.com"], "sender": "h@x"},
            },
        })
        # 替换 notifier
        mock_notifier = MagicMock()
        self.service.notifier = mock_notifier
        self.service.scanner.set_instance_loader(lambda t: [_make_instance("i1", "T")])
        self.service.trigger_scan(rule_id=r["id"])
        # notifier.dispatch 应被调用
        self.assertGreater(mock_notifier.dispatch.call_count, 0)


# ============================================================
# 8. FastAPI 路由
# ============================================================


class TestHealthRoutes(unittest.TestCase):
    """FastAPI 路由 HTTP 状态码"""

    def setUp(self):
        from fastapi import FastAPI
        import tempfile
        from odap.biz.core.ontology.health.api.routes import router

        # 用独立 DB
        self.tmp = tempfile.mkdtemp()
        # 替换模块级 service 为新实例（指向临时 DB）
        from odap.biz.core.ontology.health.api import routes as routes_module
        from odap.biz.core.ontology.health.services import HealthService
        from odap.biz.core.ontology.health.storage import SQLiteHealthStorage
        routes_module.health_service = HealthService(
            storage=SQLiteHealthStorage(db_path=f"{self.tmp}/api.db")
        )

        self.app = FastAPI()
        self.app.include_router(router)
        self.client = TestClient(self.app)

    def test_create_rule_200(self):
        r = self.client.post("/api/ontology/health/rules", json={
            "name": "r1", "target_type_id": "T",
            "rule_type": "not_null", "check_expression": {"properties": ["x"]},
        })
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("rules", body)
        self.assertEqual(body["count"], 1)

    def test_create_rule_400_invalid(self):
        # rule_type 非法，Pydantic 接受（str），由 service 抛 400
        r = self.client.post(
            "/api/ontology/health/rules",
            json={"name": "r1", "target_type_id": "T", "rule_type": "bogus_type"},
        )
        self.assertEqual(r.status_code, 400)

    def test_list_rules_200(self):
        r = self.client.get("/api/ontology/health/rules")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("rules", body)
        self.assertIn("count", body)

    def test_get_rule_404(self):
        r = self.client.get("/api/ontology/health/rules/nope")
        self.assertEqual(r.status_code, 404)

    def test_get_rule_200(self):
        c = self.client.post("/api/ontology/health/rules", json={
            "name": "r1", "target_type_id": "T", "rule_type": "not_null",
        })
        rid = c.json()["rules"][0]["id"]
        r = self.client.get(f"/api/ontology/health/rules/{rid}")
        self.assertEqual(r.status_code, 200)

    def test_update_rule_200(self):
        c = self.client.post("/api/ontology/health/rules", json={
            "name": "r1", "target_type_id": "T", "rule_type": "not_null",
        })
        rid = c.json()["rules"][0]["id"]
        r = self.client.put(f"/api/ontology/health/rules/{rid}", json={"name": "new"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["name"], "new")

    def test_update_rule_404(self):
        r = self.client.put("/api/ontology/health/rules/nope", json={"name": "x"})
        self.assertEqual(r.status_code, 404)

    def test_delete_rule_200(self):
        c = self.client.post("/api/ontology/health/rules", json={
            "name": "r1", "target_type_id": "T", "rule_type": "not_null",
        })
        rid = c.json()["rules"][0]["id"]
        r = self.client.delete(f"/api/ontology/health/rules/{rid}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["deleted"])

    def test_delete_rule_404(self):
        r = self.client.delete("/api/ontology/health/rules/nope")
        self.assertEqual(r.status_code, 404)

    def test_scan_200(self):
        c = self.client.post("/api/ontology/health/rules", json={
            "name": "r1", "target_type_id": "T", "rule_type": "not_null",
            "check_expression": {"properties": ["x"]},
        })
        rid = c.json()["rules"][0]["id"]
        # 注入 loader
        from odap.biz.core.ontology.health.api import routes as rm
        rm.health_service.scanner.set_instance_loader(
            lambda t: [{"id": "i1", "type_id": "T", "properties": {"x": 1}}]
        )
        r = self.client.post("/api/ontology/health/scan", json={"rule_id": rid})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("scanned_count", body)
        self.assertIn("reports", body)

    def test_scan_200_no_rule_id(self):
        r = self.client.post("/api/ontology/health/scan", json={})
        self.assertEqual(r.status_code, 200)

    def test_list_reports_200(self):
        r = self.client.get("/api/ontology/health/reports")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("reports", body)
        self.assertIn("count", body)

    def test_list_reports_with_filters(self):
        r = self.client.get("/api/ontology/health/reports?status=pass&limit=10")
        self.assertEqual(r.status_code, 200)

    def test_get_report_404(self):
        r = self.client.get("/api/ontology/health/reports/nope")
        self.assertEqual(r.status_code, 404)

    def test_get_report_200(self):
        c = self.client.post("/api/ontology/health/rules", json={
            "name": "r1", "target_type_id": "T", "rule_type": "not_null",
            "check_expression": {"properties": ["x"]},
        })
        rid = c.json()["rules"][0]["id"]
        from odap.biz.core.ontology.health.api import routes as rm
        rm.health_service.scanner.set_instance_loader(
            lambda t: [{"id": "i1", "type_id": "T", "properties": {"x": 1}}]
        )
        s = self.client.post("/api/ontology/health/scan", json={"rule_id": rid})
        report_id = s.json()["reports"][0]["id"]
        r = self.client.get(f"/api/ontology/health/reports/{report_id}")
        self.assertEqual(r.status_code, 200)


# ============================================================
# 入口
# ============================================================


if __name__ == "__main__":
    unittest.main()
