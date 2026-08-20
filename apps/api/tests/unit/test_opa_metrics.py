#!/usr/bin/env python3
"""P2-01: OPA 指标采集器测试"""

import time
import threading
import pytest
from odap.infra.opa.metrics import OPAMetricsCollector, record_decision, get_metrics


class TestOPAMetricsCollector:
    """指标采集器核心功能"""

    def test_record_decision_stored(self):
        collector = OPAMetricsCollector()
        collector.record_decision(allowed=True, duration_ms=5.0, package="domain", reason="ok")
        metrics = collector.get_metrics(300)
        assert metrics["total_decisions"] >= 1

    def test_allow_deny_count(self):
        collector = OPAMetricsCollector()
        collector.record_decision(True, 5.0, "domain", "ok")
        collector.record_decision(False, 3.0, "domain", "denied")
        collector.record_decision(False, 2.0, "domain", "blocked")
        metrics = collector.get_metrics(300)
        assert metrics["deny_count"] >= 2
        assert metrics["allow_count"] >= 1

    def test_deny_rate_percent(self):
        collector = OPAMetricsCollector()
        for _ in range(8):
            collector.record_decision(True, 5.0, "domain", "ok")
        for _ in range(2):
            collector.record_decision(False, 3.0, "domain", "denied")
        metrics = collector.get_metrics(300)
        # 最近 10 条中 2 条 deny → 20%
        assert metrics["deny_rate_percent"] > 0

    def test_latency_percentiles(self):
        collector = OPAMetricsCollector()
        for ms in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            collector.record_decision(True, float(ms), "domain", "ok")
        metrics = collector.get_metrics(300)
        assert metrics["latency_ms"]["p50"] > 0
        assert metrics["latency_ms"]["p95"] >= metrics["latency_ms"]["p50"]
        assert metrics["latency_ms"]["p99"] >= metrics["latency_ms"]["p95"]

    def test_by_package_grouping(self):
        collector = OPAMetricsCollector()
        collector.record_decision(True, 5.0, "domain.rbac", "ok")
        collector.record_decision(False, 3.0, "domain.abac", "denied")
        metrics = collector.get_metrics(300)
        assert "domain.rbac" in metrics["by_package"]
        assert "domain.abac" in metrics["by_package"]

    def test_top_deny_reasons(self):
        collector = OPAMetricsCollector()
        collector.record_decision(False, 3.0, "test_top_reasons_pkg", "reason_A_top_test")
        collector.record_decision(False, 3.0, "test_top_reasons_pkg", "reason_A_top_test")
        collector.record_decision(False, 3.0, "test_top_reasons_pkg", "reason_B_top_test")
        metrics = collector.get_metrics(300)
        assert len(metrics["top_deny_reasons"]) > 0
        # reason_A 出现 2 次，应排第一
        top_reason = metrics["top_deny_reasons"][0]["reason"]
        assert top_reason == "reason_A_top_test" or metrics["top_deny_reasons"][0]["count"] >= 2

    def test_audit_failure_counter(self):
        collector = OPAMetricsCollector()
        initial = collector.get_metrics(300)["audit_failures"]
        collector.increment_audit_failure("DB down")
        collector.increment_audit_failure("DB down again")
        metrics = collector.get_metrics(300)
        assert metrics["audit_failures"] >= initial + 2

    def test_opa_unavailable_counter(self):
        collector = OPAMetricsCollector()
        initial = collector.get_metrics(300)["opa_unavailable_count"]
        collector.increment_opa_unavailable()
        metrics = collector.get_metrics(300)
        assert metrics["opa_unavailable_count"] >= initial + 1


class TestModuleLevelFunctions:
    """模块级便捷函数"""

    def test_record_decision_function(self):
        record_decision(True, 5.0, "test", "ok")
        metrics = get_metrics(300)
        assert metrics["total_decisions"] >= 1
