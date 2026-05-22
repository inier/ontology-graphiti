import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.hook_system.hook_manager_v2 import (
    EnhancedHookManager,
    SecuritySandbox,
    HookMonitor,
    CodeSigner,
    CodeSignatureStatus,
    AlertLevel,
    HookAlert,
    HookMetrics,
)
from odap.biz.hook_system.models.hook import Hook, HookType, HookStatus, HookExecution
from odap.biz.hook_system.models.sandbox import SandboxConfig, SandboxResult


class TestEnhancedHookManager:

    @pytest.fixture
    def manager(self):
        return EnhancedHookManager(signing_key="test-secret-key")

    def test_register_hook(self, manager):
        hook = manager.register_hook(
            name="test_hook",
            hook_type=HookType.PRE_EXECUTE,
            script="output = 1 + 1",
            description="A test hook",
            require_signature=True,
        )

        assert hook.name == "test_hook"
        assert hook.hook_type == HookType.PRE_EXECUTE
        assert hook.script == "output = 1 + 1"
        assert hook.description == "A test hook"
        assert hook.status == HookStatus.ACTIVE
        assert hook.id in manager._hooks
        assert manager._hooks[hook.id] is hook
        assert hook.config.get("require_signature") is True
        assert "signature_id" in hook.config
        assert hook.config.get("sandbox_id") == "default"

    def test_register_hook_without_signature(self, manager):
        hook = manager.register_hook(
            name="unsigned_hook",
            hook_type=HookType.POST_EXECUTE,
            script="output = 42",
            require_signature=False,
        )

        assert hook.name == "unsigned_hook"
        assert hook.config.get("require_signature") is None
        assert "signature_id" not in hook.config

    def test_execute_hook(self, manager):
        hook = manager.register_hook(
            name="exec_hook",
            hook_type=HookType.PRE_EXECUTE,
            script="output = str(math.sqrt(16))",
            require_signature=True,
        )

        execution = manager.execute_hook(hook.id, {"x": 16})

        assert execution.hook_id == hook.id
        assert execution.status == "success"
        assert execution.duration_ms >= 0
        assert execution.result is not None
        assert "output" in execution.result

    def test_execute_hook_not_found(self, manager):
        with pytest.raises(ValueError, match="Hook not found"):
            manager.execute_hook("nonexistent_hook_id")

    def test_execute_hook_unsigned_rejected(self, manager):
        hook = manager.register_hook(
            name="unsigned_exec_hook",
            hook_type=HookType.PRE_EXECUTE,
            script="output = 42",
            require_signature=False,
        )
        hook.config["require_signature"] = True

        execution = manager.execute_hook(hook.id)

        assert execution.status == "error"
        assert "Signature verification failed" in execution.error

    def test_list_hooks(self, manager):
        hook1 = manager.register_hook(
            name="hook_a",
            hook_type=HookType.PRE_EXECUTE,
            script="output = 1",
            require_signature=False,
        )
        hook2 = manager.register_hook(
            name="hook_b",
            hook_type=HookType.POST_EXECUTE,
            script="output = 2",
            require_signature=False,
        )
        hook3 = manager.register_hook(
            name="hook_c",
            hook_type=HookType.PRE_EXECUTE,
            script="output = 3",
            require_signature=False,
        )

        all_hooks = manager.list_hooks()
        assert len(all_hooks) == 3

        pre_hooks = manager.list_hooks(filters={"type": "pre_execute"})
        assert len(pre_hooks) == 2
        assert all(h.hook_type == HookType.PRE_EXECUTE for h in pre_hooks)

        post_hooks = manager.list_hooks(filters={"type": "post_execute"})
        assert len(post_hooks) == 1
        assert post_hooks[0].name == "hook_b"

    def test_list_hooks_pagination(self, manager):
        for i in range(5):
            manager.register_hook(
                name=f"page_hook_{i}",
                hook_type=HookType.PRE_EXECUTE,
                script=f"output = {i}",
                require_signature=False,
            )

        page1 = manager.list_hooks(page=1, page_size=2)
        assert len(page1) == 2

        page2 = manager.list_hooks(page=2, page_size=2)
        assert len(page2) == 2

        page3 = manager.list_hooks(page=3, page_size=2)
        assert len(page3) == 1

    def test_unregister_hook_via_delete(self, manager):
        hook = manager.register_hook(
            name="to_remove",
            hook_type=HookType.ON_ERROR,
            script="output = 'error'",
            require_signature=False,
        )

        assert manager.get_hook(hook.id) is not None

        del manager._hooks[hook.id]
        del manager._executions[hook.id]

        assert manager.get_hook(hook.id) is None

    def test_hook_priority(self, manager):
        hook_high = manager.register_hook(
            name="high_priority",
            hook_type=HookType.PRE_EXECUTE,
            script="output = 'high'",
            require_signature=False,
        )
        hook_low = manager.register_hook(
            name="low_priority",
            hook_type=HookType.PRE_EXECUTE,
            script="output = 'low'",
            require_signature=False,
        )
        hook_medium = manager.register_hook(
            name="medium_priority",
            hook_type=HookType.PRE_EXECUTE,
            script="output = 'medium'",
            require_signature=False,
        )

        hook_high.config["priority"] = 1
        hook_low.config["priority"] = 10
        hook_medium.config["priority"] = 5

        hooks = manager.list_hooks()
        sorted_hooks = sorted(hooks, key=lambda h: h.config.get("priority", 999))

        assert sorted_hooks[0].name == "high_priority"
        assert sorted_hooks[1].name == "medium_priority"
        assert sorted_hooks[2].name == "low_priority"

    def test_get_hook(self, manager):
        hook = manager.register_hook(
            name="gettable",
            hook_type=HookType.ON_TIMEOUT,
            script="output = 'timeout'",
            require_signature=False,
        )

        result = manager.get_hook(hook.id)
        assert result is hook
        assert result.name == "gettable"

    def test_get_hook_not_found(self, manager):
        result = manager.get_hook("nonexistent")
        assert result is None

    def test_get_hook_executions(self, manager):
        hook = manager.register_hook(
            name="multi_exec",
            hook_type=HookType.PRE_EXECUTE,
            script="output = str(math.sqrt(4))",
            require_signature=True,
        )

        manager.execute_hook(hook.id)
        manager.execute_hook(hook.id)

        executions = manager.get_hook_executions(hook.id)
        assert len(executions) == 2

    def test_get_hook_metrics(self, manager):
        hook = manager.register_hook(
            name="metrics_hook",
            hook_type=HookType.PRE_EXECUTE,
            script="output = str(math.sqrt(9))",
            require_signature=True,
        )

        manager.execute_hook(hook.id)

        metrics = manager.get_hook_metrics(hook.id)
        assert metrics is not None
        assert metrics.total_executions == 1
        assert metrics.successful_executions == 1

    def test_get_health_report(self, manager):
        hook = manager.register_hook(
            name="health_hook",
            hook_type=HookType.PRE_EXECUTE,
            script="output = str(math.sqrt(25))",
            require_signature=True,
        )
        manager.execute_hook(hook.id)

        report = manager.get_health_report()
        assert report["total_hooks"] == 1
        assert report["active_hooks"] == 1
        assert report["total_executions"] == 1

    def test_create_sandbox(self, manager):
        config = SandboxConfig(
            id="custom-sandbox",
            name="Custom Sandbox",
            max_memory_mb=64,
            max_cpu_percent=25,
            max_execution_time_ms=3000,
            allowed_modules=["math", "json"],
        )

        result = manager.create_sandbox(config)
        assert result.id == "custom-sandbox"

        status = manager.get_sandbox_status("custom-sandbox")
        assert status is not None
        assert status["name"] == "Custom Sandbox"

    def test_sign_and_verify_hook(self, manager):
        hook = manager.register_hook(
            name="signed_hook",
            hook_type=HookType.PRE_EXECUTE,
            script="output = 42",
            require_signature=True,
        )

        status = manager.verify_hook_signature(hook.id)
        assert status == CodeSignatureStatus.VALID

    def test_verify_tampered_hook(self, manager):
        hook = manager.register_hook(
            name="tampered_hook",
            hook_type=HookType.PRE_EXECUTE,
            script="output = 42",
            require_signature=True,
        )

        hook.script = "output = 999"
        status = manager.verify_hook_signature(hook.id)
        assert status == CodeSignatureStatus.INVALID


class TestSecuritySandbox:

    @pytest.fixture
    def sandbox(self):
        sb = SecuritySandbox()
        config = SandboxConfig(
            id="test-sandbox",
            name="Test Sandbox",
            max_memory_mb=128,
            max_cpu_percent=50,
            max_execution_time_ms=5000,
            allowed_modules=["math", "json", "re"],
        )
        sb.create_sandbox(config)
        return sb

    def test_validate_code_safe(self, sandbox):
        code = "output = math.sqrt(16)"
        is_safe, error = sandbox.validate_code(code)
        assert is_safe is True
        assert error is None

    def test_validate_code_blocked_import_os(self, sandbox):
        code = "import os"
        is_safe, error = sandbox.validate_code(code)
        assert is_safe is False
        assert "Blocked pattern" in error

    def test_validate_code_blocked_import_sys(self, sandbox):
        code = "import sys"
        is_safe, error = sandbox.validate_code(code)
        assert is_safe is False

    def test_validate_code_blocked_import_subprocess(self, sandbox):
        code = "import subprocess"
        is_safe, error = sandbox.validate_code(code)
        assert is_safe is False

    def test_validate_code_blocked_open(self, sandbox):
        code = "f = open('file.txt')"
        is_safe, error = sandbox.validate_code(code)
        assert is_safe is False

    def test_validate_code_blocked_exec(self, sandbox):
        code = "exec('print(1)')"
        is_safe, error = sandbox.validate_code(code)
        assert is_safe is False

    def test_validate_code_blocked_eval(self, sandbox):
        code = "eval('1+1')"
        is_safe, error = sandbox.validate_code(code)
        assert is_safe is False

    def test_validate_code_blocked_dunder_import(self, sandbox):
        code = "__import__('os')"
        is_safe, error = sandbox.validate_code(code)
        assert is_safe is False

    def test_validate_code_exceeds_length(self, sandbox):
        code = "x = 1\n" * 10000
        is_safe, error = sandbox.validate_code(code)
        assert is_safe is False
        assert "maximum length" in error

    def test_execute_success(self, sandbox):
        code = "output = str(math.sqrt(16))"
        result = sandbox.execute("test-sandbox", code, {})

        assert result.status == "success"
        assert result.output == "4.0"

    def test_execute_rejected(self, sandbox):
        code = "import os\noutput = os.getcwd()"
        result = sandbox.execute("test-sandbox", code, {})

        assert result.status == "rejected"
        assert result.error is not None

    def test_execute_sandbox_not_found(self, sandbox):
        with pytest.raises(ValueError, match="Sandbox not found"):
            sandbox.execute("nonexistent", "output = 1", {})

    def test_execute_error(self, sandbox):
        code = "output = 1 / 0"
        result = sandbox.execute("test-sandbox", code, {})

        assert result.status == "error"
        assert result.error is not None

    def test_create_sandbox_default_modules(self, sandbox):
        config = SandboxConfig(
            id="auto-modules",
            name="Auto Modules Sandbox",
        )
        result = sandbox.create_sandbox(config)
        assert len(result.allowed_modules) > 0

    def test_destroy_sandbox(self, sandbox):
        assert sandbox.destroy_sandbox("test-sandbox") is True
        assert sandbox.destroy_sandbox("test-sandbox") is False

    def test_get_sandbox_status(self, sandbox):
        status = sandbox.get_sandbox_status("test-sandbox")
        assert status is not None
        assert status["sandbox_id"] == "test-sandbox"
        assert status["name"] == "Test Sandbox"

    def test_get_sandbox_status_not_found(self, sandbox):
        status = sandbox.get_sandbox_status("nonexistent")
        assert status is None


class TestHookMonitor:

    @pytest.fixture
    def monitor(self):
        return HookMonitor()

    def test_record_execution_success(self, monitor):
        monitor.record_execution("hook-1", "test_hook", success=True, duration_ms=50.0)

        metrics = monitor.get_metrics("hook-1")
        assert metrics is not None
        assert metrics.total_executions == 1
        assert metrics.successful_executions == 1
        assert metrics.failed_executions == 0
        assert metrics.avg_execution_time_ms == 50.0

    def test_record_execution_failure(self, monitor):
        monitor.record_execution("hook-2", "fail_hook", success=False, duration_ms=100.0, error="boom")

        metrics = monitor.get_metrics("hook-2")
        assert metrics is not None
        assert metrics.failed_executions == 1
        assert metrics.last_error == "boom"

    def test_record_execution_timeout(self, monitor):
        monitor.record_execution("hook-3", "timeout_hook", success=False, duration_ms=5000.0, timeout=True)

        metrics = monitor.get_metrics("hook-3")
        assert metrics is not None
        assert metrics.timeout_executions == 1

    def test_metrics_avg_latency(self, monitor):
        monitor.record_execution("hook-4", "latency_hook", success=True, duration_ms=100.0)
        monitor.record_execution("hook-4", "latency_hook", success=True, duration_ms=200.0)

        metrics = monitor.get_metrics("hook-4")
        assert metrics.avg_execution_time_ms == 150.0
        assert metrics.max_execution_time_ms == 200.0
        assert metrics.min_execution_time_ms == 100.0

    def test_alert_on_high_error_rate(self, monitor):
        for i in range(5):
            monitor.record_execution("hook-5", "error_hook", success=False, duration_ms=10.0, error="fail")

        alerts = monitor.get_alerts(level=AlertLevel.CRITICAL.value)
        assert len(alerts) >= 1
        assert any("error rate" in a.message.lower() for a in alerts)

    def test_alert_on_slow_execution(self, monitor):
        for i in range(5):
            monitor.record_execution("hook-6", "slow_hook", success=True, duration_ms=6000.0)

        alerts = monitor.get_alerts(level=AlertLevel.ERROR.value)
        assert len(alerts) >= 1
        assert any("slow execution" in a.message.lower() or "latency" in a.message.lower() for a in alerts)

    def test_no_alert_below_threshold(self, monitor):
        for i in range(4):
            monitor.record_execution("hook-7", "ok_hook", success=True, duration_ms=10.0)

        alerts = monitor.get_alerts()
        assert len(alerts) == 0

    def test_register_alert_callback(self, monitor):
        callback = MagicMock()
        monitor.register_alert_callback(callback)

        for i in range(5):
            monitor.record_execution("hook-8", "cb_hook", success=False, duration_ms=10.0, error="fail")

        assert callback.call_count >= 1

    def test_acknowledge_alert(self, monitor):
        for i in range(5):
            monitor.record_execution("hook-9", "ack_hook", success=False, duration_ms=10.0, error="fail")

        alerts = monitor.get_alerts()
        assert len(alerts) >= 1

        result = monitor.acknowledge_alert(alerts[0].alert_id)
        assert result is True
        assert alerts[0].acknowledged is True

    def test_acknowledge_alert_not_found(self, monitor):
        result = monitor.acknowledge_alert("nonexistent-alert-id")
        assert result is False

    def test_get_alerts_filter_acknowledged(self, monitor):
        for i in range(5):
            monitor.record_execution("hook-10", "filter_hook", success=False, duration_ms=10.0, error="fail")

        unacknowledged = monitor.get_alerts(acknowledged=False)
        assert len(unacknowledged) >= 1

        if unacknowledged:
            monitor.acknowledge_alert(unacknowledged[0].alert_id)

        acknowledged = monitor.get_alerts(acknowledged=True)
        assert len(acknowledged) >= 1

    def test_clear_alerts(self, monitor):
        for i in range(5):
            monitor.record_execution("hook-11", "clear_hook", success=False, duration_ms=10.0, error="fail")

        monitor.clear_alerts()
        alerts = monitor.get_alerts()
        assert len(alerts) == 0

    def test_clear_alerts_by_hook(self, monitor):
        for i in range(5):
            monitor.record_execution("hook-12a", "clear_a", success=False, duration_ms=10.0, error="fail")
        for i in range(5):
            monitor.record_execution("hook-12b", "clear_b", success=False, duration_ms=10.0, error="fail")

        monitor.clear_alerts(hook_id="hook-12a")

        remaining = monitor.get_alerts()
        assert all(a.hook_id != "hook-12a" for a in remaining)

    def test_get_all_metrics(self, monitor):
        monitor.record_execution("hook-13a", "m1", success=True, duration_ms=10.0)
        monitor.record_execution("hook-13b", "m2", success=True, duration_ms=20.0)

        all_metrics = monitor.get_all_metrics()
        assert len(all_metrics) == 2

    def test_get_metrics_not_found(self, monitor):
        result = monitor.get_metrics("nonexistent")
        assert result is None
