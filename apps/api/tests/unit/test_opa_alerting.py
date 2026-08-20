#!/usr/bin/env python3
"""P2-02/06: OPA 告警管理器测试"""

import pytest
from unittest.mock import patch, MagicMock
from odap.infra.opa.alerting import OPAAlertManager, OPAAlert, ALERT_THRESHOLDS


class TestOPAAlertEvaluation:
    """告警条件评估"""

    def _make_mgr(self):
        mgr = OPAAlertManager.__new__(OPAAlertManager)
        mgr._init(check_interval=999, webhook_url=None)
        return mgr

    def test_deny_storm_triggers_critical(self):
        mgr = self._make_mgr()
        metrics = {"deny_count": 60, "latency_ms": {"p95": 0},
                   "audit_failures": 0, "opa_unavailable_count": 0}
        alerts = mgr._evaluate(metrics)
        types = [a.type for a in alerts]
        assert "deny_storm" in types
        assert alerts[types.index("deny_storm")].level == "critical"

    def test_latency_spike_triggers_warning(self):
        mgr = self._make_mgr()
        metrics = {"deny_count": 0, "latency_ms": {"p95": 600},
                   "audit_failures": 0, "opa_unavailable_count": 0}
        alerts = mgr._evaluate(metrics)
        types = [a.type for a in alerts]
        assert "latency_spike" in types
        assert alerts[types.index("latency_spike")].level == "warning"

    def test_audit_failure_triggers_critical(self):
        mgr = self._make_mgr()
        metrics = {"deny_count": 0, "latency_ms": {"p95": 0},
                   "audit_failures": 15, "opa_unavailable_count": 0}
        alerts = mgr._evaluate(metrics)
        types = [a.type for a in alerts]
        assert "audit_failure" in types

    def test_opa_unavailable_triggers_critical(self):
        mgr = self._make_mgr()
        metrics = {"deny_count": 0, "latency_ms": {"p95": 0},
                   "audit_failures": 0, "opa_unavailable_count": 3}
        alerts = mgr._evaluate(metrics)
        types = [a.type for a in alerts]
        assert "opa_unavailable" in types

    def test_no_alert_when_metrics_normal(self):
        mgr = self._make_mgr()
        metrics = {"deny_count": 5, "latency_ms": {"p95": 100},
                   "audit_failures": 2, "opa_unavailable_count": 0}
        alerts = mgr._evaluate(metrics)
        assert len(alerts) == 0


class TestAlertDeduplication:
    """告警去重（同类型 5 分钟内不重复）"""

    def test_dedup_same_type_within_window(self):
        mgr = OPAAlertManager.__new__(OPAAlertManager)
        mgr._init(check_interval=999, webhook_url=None)
        metrics = {"deny_count": 100, "latency_ms": {"p95": 0},
                   "audit_failures": 0, "opa_unavailable_count": 0}
        # 第一次应触发
        alerts1 = mgr._evaluate(metrics)
        assert len(alerts1) > 0
        # 第二次同类型应被去重
        alerts2 = mgr._evaluate(metrics)
        assert len(alerts2) == 0


class TestAlertEmission:
    """告警发送通道"""

    def test_emit_writes_audit_log(self):
        mgr = OPAAlertManager.__new__(OPAAlertManager)
        mgr._init(check_interval=999, webhook_url=None)
        alert = OPAAlert(level="critical", type="test", message="test alert",
                         timestamp="2026-01-01T00:00:00", metrics_snapshot={})
        with patch("odap.infra.security.unified_audit.log_audit") as mock_log:
            mgr._emit(alert)
        assert mock_log.called
