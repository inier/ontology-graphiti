"""
Hook 系统增强 - Enhanced Hook System
WR-06: Hook 系统增强 (安全沙箱 + 代码签名 + 监控告警)

功能：
- 安全沙箱 - 代码执行隔离
- 代码签名 - Hook 脚本签名验证
- 监控告警 - Hook 执行监控
- 与审计集成
"""

import sys
import os
import json
import time
import hashlib
import hmac
import asyncio
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import threading
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from odap.biz.integration.hook_system.models.hook import Hook, HookType, HookStatus, HookExecution
from odap.biz.integration.hook_system.models.sandbox import SandboxConfig, SandboxResult


class CodeSignatureStatus(Enum):
    """代码签名状态"""
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    NOT_SIGNED = "not_signed"


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class CodeSignature:
    """代码签名"""
    signature_id: str
    hook_id: str
    script_hash: str
    signature: str
    public_key_id: str
    created_at: str
    expires_at: Optional[str] = None
    algorithm: str = "SHA256"


@dataclass
class HookAlert:
    """Hook 告警"""
    alert_id: str
    hook_id: str
    hook_name: str
    level: str
    message: str
    timestamp: str
    context: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False


@dataclass
class HookMetrics:
    """Hook 指标"""
    hook_id: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    timeout_executions: int = 0
    avg_execution_time_ms: float = 0
    max_execution_time_ms: float = 0
    min_execution_time_ms: float = float('inf')
    last_execution_time: Optional[str] = None
    last_error: Optional[str] = None


class SecuritySandbox:
    """
    安全沙箱
    提供安全的代码执行环境
    """

    def __init__(self):
        self._sandboxes: Dict[str, SandboxConfig] = {}
        self._allowed_modules = {
            "math", "random", "datetime", "time", "json", "re",
            "collections", "itertools", "functools", "typing"
        }
        self._blocked_patterns = [
            r"import\s+os",
            r"import\s+sys",
            r"import\s+subprocess",
            r"import\s+socket",
            r"open\s*\(",
            r"exec\s*\(",
            r"eval\s*\(",
            r"__import__",
            r"eval\s*<",
            r"compile\s*\(",
        ]

    def create_sandbox(self, config: SandboxConfig) -> SandboxConfig:
        """创建沙箱"""
        if not config.allowed_modules:
            config.allowed_modules = list(self._allowed_modules)
        self._sandboxes[config.id] = config
        return config

    def validate_code(self, code: str) -> tuple[bool, Optional[str]]:
        """
        验证代码安全性

        Returns:
            (is_safe, error_message)
        """
        for pattern in self._blocked_patterns:
            if re.search(pattern, code):
                return False, f"Blocked pattern detected: {pattern}"

        if len(code) > 50000:
            return False, "Code exceeds maximum length"

        return True, None

    def execute(self, sandbox_id: str, code: str, context: Dict = None,
                timeout_ms: int = 5000) -> SandboxResult:
        """
        在沙箱中执行代码

        Args:
            sandbox_id: 沙箱 ID
            code: 要执行的代码
            context: 执行上下文
            timeout_ms: 超时时间

        Returns:
            SandboxResult
        """
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            raise ValueError(f"Sandbox not found: {sandbox_id}")

        result = SandboxResult(sandbox_config_id=sandbox_id)
        start_time = time.perf_counter()

        is_safe, error = self.validate_code(code)
        if not is_safe:
            result.status = "rejected"
            result.error = error
            result.execution_time_ms = int((time.perf_counter() - start_time) * 1000)
            return result

        try:
            local_vars = context or {}
            exec_globals = {m: __import__(m) for m in sandbox.allowed_modules if m in self._allowed_modules}

            exec(code, exec_globals, local_vars)

            result.status = "success"
            result.output = str(local_vars.get("output", ""))
            result.memory_used_mb = 0
            result.cpu_used_percent = 0

        except TimeoutError:
            result.status = "timeout"
            result.error = f"Execution timeout after {timeout_ms}ms"
        except Exception as e:
            result.status = "error"
            result.error = str(e)

        result.execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        return result

    async def execute_async(self, sandbox_id: str, code: str, context: Dict = None,
                           timeout_ms: int = 5000) -> SandboxResult:
        """异步执行"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.execute, sandbox_id, code, context, timeout_ms
        )

    def destroy_sandbox(self, sandbox_id: str) -> bool:
        """销毁沙箱"""
        if sandbox_id in self._sandboxes:
            del self._sandboxes[sandbox_id]
            return True
        return False

    def get_sandbox_status(self, sandbox_id: str) -> Optional[Dict[str, Any]]:
        """获取沙箱状态"""
        sandbox = self._sandboxes.get(sandbox_id)
        if not sandbox:
            return None
        return {
            "sandbox_id": sandbox.id,
            "name": sandbox.name,
            "max_memory_mb": sandbox.max_memory_mb,
            "max_cpu_percent": sandbox.max_cpu_percent,
            "max_execution_time_ms": sandbox.max_execution_time_ms,
            "allowed_modules": sandbox.allowed_modules,
            "network_enabled": sandbox.network_enabled,
            "filesystem_enabled": sandbox.filesystem_enabled
        }


class CodeSigner:
    """
    代码签名器
    用于验证 Hook 脚本的完整性和来源
    """

    def __init__(self, secret_key: str = None):
        self._secret_key = secret_key or os.getenv("HOOK_SIGNING_KEY", "default-secret-key")
        self._signatures: Dict[str, CodeSignature] = {}
        self._public_keys: Dict[str, str] = {}

    def generate_signature(self, hook_id: str, script: str,
                          expires_at: Optional[str] = None) -> CodeSignature:
        """
        生成代码签名

        Args:
            hook_id: Hook ID
            script: 脚本内容
            expires_at: 过期时间

        Returns:
            CodeSignature
        """
        script_hash = hashlib.sha256(script.encode()).hexdigest()

        message = f"{hook_id}:{script_hash}"
        signature = hmac.new(
            self._secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        public_key_id = f"key-{hook_id[:8]}"

        sig = CodeSignature(
            signature_id=str(uuid.uuid4()),
            hook_id=hook_id,
            script_hash=script_hash,
            signature=signature,
            public_key_id=public_key_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=expires_at
        )

        self._signatures[hook_id] = sig
        return sig

    def verify_signature(self, hook_id: str, script: str) -> CodeSignatureStatus:
        """
        验证代码签名

        Args:
            hook_id: Hook ID
            script: 脚本内容

        Returns:
            CodeSignatureStatus
        """
        sig = self._signatures.get(hook_id)
        if not sig:
            return CodeSignatureStatus.NOT_SIGNED

        if sig.expires_at:
            expires = datetime.fromisoformat(sig.expires_at.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) > expires:
                return CodeSignatureStatus.EXPIRED

        script_hash = hashlib.sha256(script.encode()).hexdigest()
        if script_hash != sig.script_hash:
            return CodeSignatureStatus.INVALID

        message = f"{hook_id}:{script_hash}"
        expected_sig = hmac.new(
            self._secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(sig.signature, expected_sig):
            return CodeSignatureStatus.INVALID

        return CodeSignatureStatus.VALID

    def get_signature(self, hook_id: str) -> Optional[CodeSignature]:
        """获取签名"""
        return self._signatures.get(hook_id)

    def revoke_signature(self, hook_id: str) -> bool:
        """撤销签名"""
        if hook_id in self._signatures:
            del self._signatures[hook_id]
            return True
        return False


class HookMonitor:
    """
    Hook 监控器
    监控 Hook 执行并生成告警
    """

    def __init__(self):
        self._metrics: Dict[str, HookMetrics] = {}
        self._alerts: List[HookAlert] = []
        self._alert_callbacks: List[Callable] = []
        self._lock = threading.RLock()
        self._alert_thresholds = {
            "error_rate_warning": 0.1,
            "error_rate_critical": 0.3,
            "avg_latency_warning_ms": 1000,
            "avg_latency_critical_ms": 5000,
            "timeout_rate_warning": 0.05,
            "timeout_rate_critical": 0.15,
        }

    def record_execution(self, hook_id: str, hook_name: str, success: bool,
                        duration_ms: float, error: str = None, timeout: bool = False):
        """记录执行"""
        with self._lock:
            if hook_id not in self._metrics:
                self._metrics[hook_id] = HookMetrics(hook_id=hook_id)

            metrics = self._metrics[hook_id]
            metrics.total_executions += 1

            if timeout:
                metrics.timeout_executions += 1
            elif success:
                metrics.successful_executions += 1
            else:
                metrics.failed_executions += 1
                metrics.last_error = error

            if duration_ms > 0:
                metrics.avg_execution_time_ms = (
                    (metrics.avg_execution_time_ms * (metrics.total_executions - 1) + duration_ms)
                    / metrics.total_executions
                )
                metrics.max_execution_time_ms = max(metrics.max_execution_time_ms, duration_ms)
                metrics.min_execution_time_ms = min(metrics.min_execution_time_ms, duration_ms)

            metrics.last_execution_time = datetime.now(timezone.utc).isoformat()

            self._check_alerts(hook_id, hook_name, metrics)

    def _check_alerts(self, hook_id: str, hook_name: str, metrics: HookMetrics):
        """检查是否需要告警"""
        if metrics.total_executions < 5:
            return

        error_rate = metrics.failed_executions / metrics.total_executions
        timeout_rate = metrics.timeout_executions / metrics.total_executions

        if error_rate >= self._alert_thresholds["error_rate_critical"]:
            self._create_alert(hook_id, hook_name, AlertLevel.CRITICAL,
                             f"High error rate: {error_rate:.1%}", {
                                 "error_rate": error_rate,
                                 "failed_count": metrics.failed_executions
                             })
        elif error_rate >= self._alert_thresholds["error_rate_warning"]:
            self._create_alert(hook_id, hook_name, AlertLevel.WARNING,
                             f"Elevated error rate: {error_rate:.1%}", {
                                 "error_rate": error_rate
                             })

        if timeout_rate >= self._alert_thresholds["timeout_rate_critical"]:
            self._create_alert(hook_id, hook_name, AlertLevel.ERROR,
                             f"High timeout rate: {timeout_rate:.1%}", {
                                 "timeout_rate": timeout_rate
                             })

        if metrics.avg_execution_time_ms >= self._alert_thresholds["avg_latency_critical_ms"]:
            self._create_alert(hook_id, hook_name, AlertLevel.ERROR,
                             f"Slow execution: {metrics.avg_execution_time_ms:.0f}ms avg", {
                                 "avg_latency_ms": metrics.avg_execution_time_ms
                             })
        elif metrics.avg_execution_time_ms >= self._alert_thresholds["avg_latency_warning_ms"]:
            self._create_alert(hook_id, hook_name, AlertLevel.WARNING,
                             f"Elevated latency: {metrics.avg_execution_time_ms:.0f}ms avg", {
                                 "avg_latency_ms": metrics.avg_execution_time_ms
                             })

    def _create_alert(self, hook_id: str, hook_name: str, level: AlertLevel,
                     message: str, context: Dict):
        """创建告警"""
        alert = HookAlert(
            alert_id=str(uuid.uuid4()),
            hook_id=hook_id,
            hook_name=hook_name,
            level=level.value,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=context
        )
        self._alerts.append(alert)

        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass

    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self._alert_callbacks.append(callback)

    def get_metrics(self, hook_id: str) -> Optional[HookMetrics]:
        """获取指标"""
        return self._metrics.get(hook_id)

    def get_all_metrics(self) -> List[HookMetrics]:
        """获取所有指标"""
        return list(self._metrics.values())

    def get_alerts(self, level: str = None, acknowledged: bool = None) -> List[HookAlert]:
        """获取告警"""
        alerts = self._alerts
        if level:
            alerts = [a for a in alerts if a.level == level]
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def clear_alerts(self, hook_id: str = None):
        """清除告警"""
        if hook_id:
            self._alerts = [a for a in self._alerts if a.hook_id != hook_id]
        else:
            self._alerts = []


class EnhancedHookManager:
    """
    增强的 Hook 管理器
    集成安全沙箱、代码签名、监控告警和审计功能
    """

    def __init__(self, signing_key: str = None):
        self._hooks: Dict[str, Hook] = {}
        self._executions: Dict[str, List[HookExecution]] = {}
        self._sandbox = SecuritySandbox()
        self._signer = CodeSigner(signing_key)
        self._monitor = HookMonitor()
        self._default_sandbox_id = None
        self._audit_enabled = True
        self._lock = threading.RLock()

        self._setup_default_sandbox()
        self._setup_alert_integration()

    def _setup_default_sandbox(self):
        """设置默认沙箱"""
        config = SandboxConfig(
            id="default",
            name="Default Hook Sandbox",
            max_memory_mb=128,
            max_cpu_percent=50,
            max_execution_time_ms=5000,
            allowed_modules=["math", "random", "datetime", "time", "json", "re"],
            blocked_modules=["os", "sys", "subprocess", "socket"],
            network_enabled=False,
            filesystem_enabled=False
        )
        self._sandbox.create_sandbox(config)
        self._default_sandbox_id = config.id

    def _setup_alert_integration(self):
        """设置告警集成"""
        def alert_callback(alert: HookAlert):
            if self._audit_enabled:
                try:
                    self._log_to_audit(alert)
                except Exception:
                    pass

        self._monitor.register_alert_callback(alert_callback)

    def _log_to_audit(self, alert: HookAlert):
        """记录到审计日志"""
        try:
            from odap.infra.security.audit_logger_v2 import get_audit_logger
            audit = get_audit_logger()
            if audit:
                audit.log(
                    action=f"hook_alert_{alert.level}",
                    resource_type="hook",
                    resource_id=alert.hook_id,
                    details=alert.context
                )
        except Exception:
            pass

    def register_hook(self, name: str, hook_type: HookType, script: str,
                     description: str = "", language: str = "python",
                     require_signature: bool = True, sandbox_id: str = None) -> Hook:
        """
        注册 Hook

        Args:
            name: Hook 名称
            hook_type: Hook 类型
            script: 脚本内容
            description: 描述
            language: 语言
            require_signature: 是否需要签名
            sandbox_id: 沙箱 ID

        Returns:
            Hook
        """
        with self._lock:
            hook = Hook(
                name=name,
                hook_type=hook_type,
                script=script,
                description=description,
                language=language
            )

            if require_signature:
                sig = self._signer.generate_signature(hook.id, script)
                hook.config["signature_id"] = sig.signature_id
                hook.config["require_signature"] = True

            hook.config["sandbox_id"] = sandbox_id or self._default_sandbox_id

            self._hooks[hook.id] = hook
            self._executions[hook.id] = []

            return hook

    def update_hook(self, hook_id: str, updates: Dict[str, Any]) -> Hook:
        """更新 Hook"""
        with self._lock:
            hook = self._hooks.get(hook_id)
            if not hook:
                raise ValueError(f"Hook not found: {hook_id}")

            if "script" in updates:
                new_script = updates["script"]
                if hook.config.get("require_signature"):
                    sig = self._signer.generate_signature(hook_id, new_script)
                    updates["config"] = hook.config.copy()
                    updates["config"]["signature_id"] = sig.signature_id

            for key, value in updates.items():
                if hasattr(hook, key):
                    setattr(hook, key, value)

            hook.updated_at = datetime.now()
            return hook

    def sign_hook(self, hook_id: str) -> CodeSignature:
        """为 Hook 生成签名"""
        hook = self._hooks.get(hook_id)
        if not hook:
            raise ValueError(f"Hook not found: {hook_id}")

        return self._signer.generate_signature(hook_id, hook.script)

    def verify_hook_signature(self, hook_id: str) -> CodeSignatureStatus:
        """验证 Hook 签名"""
        hook = self._hooks.get(hook_id)
        if not hook:
            raise ValueError(f"Hook not found: {hook_id}")

        return self._signer.verify_signature(hook_id, hook.script)

    def execute_hook(self, hook_id: str, context: Dict[str, Any] = None) -> HookExecution:
        """
        执行 Hook

        Args:
            hook_id: Hook ID
            context: 执行上下文

        Returns:
            HookExecution
        """
        hook = self._hooks.get(hook_id)
        if not hook:
            raise ValueError(f"Hook not found: {hook_id}")

        execution = HookExecution(hook_id=hook_id)
        start_time = time.perf_counter()

        if hook.config.get("require_signature", False):
            status = self.verify_hook_signature(hook_id)
            if status != CodeSignatureStatus.VALID:
                execution.status = "error"
                execution.error = f"Signature verification failed: {status.value}"
                execution.duration_ms = int((time.perf_counter() - start_time) * 1000)
                return execution

        sandbox_id = hook.config.get("sandbox_id", self._default_sandbox_id)

        try:
            result = self._sandbox.execute(
                sandbox_id, hook.script, context, hook.timeout_ms
            )

            execution.status = result.status
            execution.duration_ms = result.execution_time_ms

            if result.status == "success":
                execution.result = {"output": result.output}
            else:
                execution.error = result.error

        except Exception as e:
            execution.status = "error"
            execution.error = str(e)
            execution.duration_ms = int((time.perf_counter() - start_time) * 1000)

        self._monitor.record_execution(
            hook_id, hook.name,
            execution.status == "success",
            execution.duration_ms,
            execution.error,
            execution.status == "timeout"
        )

        if hook_id in self._executions:
            self._executions[hook_id].append(execution)

        return execution

    def get_hook(self, hook_id: str) -> Optional[Hook]:
        """获取 Hook"""
        return self._hooks.get(hook_id)

    def list_hooks(self, filters: Dict[str, Any] = None,
                  page: int = 1, page_size: int = 10) -> List[Hook]:
        """列出 Hooks"""
        filters = filters or {}
        hooks = list(self._hooks.values())

        if "type" in filters:
            hooks = [h for h in hooks if h.hook_type.value == filters["type"]]
        if "status" in filters:
            hooks = [h for h in hooks if h.status.value == filters["status"]]

        start = (page - 1) * page_size
        end = start + page_size
        return hooks[start:end]

    def get_hook_executions(self, hook_id: str, limit: int = 10) -> List[HookExecution]:
        """获取 Hook 执行记录"""
        executions = self._executions.get(hook_id, [])
        return executions[-limit:]

    def get_hook_metrics(self, hook_id: str) -> Optional[HookMetrics]:
        """获取 Hook 指标"""
        return self._monitor.get_metrics(hook_id)

    def get_all_metrics(self) -> List[HookMetrics]:
        """获取所有 Hook 指标"""
        return self._monitor.get_all_metrics()

    def get_alerts(self, level: str = None) -> List[HookAlert]:
        """获取告警"""
        return self._monitor.get_alerts(level=level)

    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        return self._monitor.acknowledge_alert(alert_id)

    def get_sandbox_status(self, sandbox_id: str = None) -> Optional[Dict[str, Any]]:
        """获取沙箱状态"""
        return self._sandbox.get_sandbox_status(sandbox_id or self._default_sandbox_id)

    def create_sandbox(self, config: SandboxConfig) -> SandboxConfig:
        """创建沙箱"""
        return self._sandbox.create_sandbox(config)

    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        metrics = self.get_all_metrics()
        alerts = self.get_alerts()

        total_hooks = len(self._hooks)
        active_hooks = sum(1 for h in self._hooks.values() if h.status == HookStatus.ACTIVE)

        total_executions = sum(m.total_executions for m in metrics)
        total_success = sum(m.successful_executions for m in metrics)
        total_failed = sum(m.failed_executions for m in metrics)

        return {
            "total_hooks": total_hooks,
            "active_hooks": active_hooks,
            "total_executions": total_executions,
            "successful_executions": total_success,
            "failed_executions": total_failed,
            "success_rate": (total_success / total_executions * 100) if total_executions > 0 else 0,
            "unacknowledged_alerts": len([a for a in alerts if not a.acknowledged]),
            "critical_alerts": len([a for a in alerts if a.level == AlertLevel.CRITICAL.value]),
            "hooks": [
                {
                    "hook_id": m.hook_id,
                    "total_executions": m.total_executions,
                    "success_rate": (m.successful_executions / m.total_executions * 100)
                                   if m.total_executions > 0 else 0,
                    "avg_latency_ms": m.avg_execution_time_ms
                }
                for m in metrics
            ]
        }


_global_hook_manager: Optional[EnhancedHookManager] = None


def get_hook_manager(signing_key: str = None) -> EnhancedHookManager:
    """获取全局 Hook 管理器"""
    global _global_hook_manager
    if _global_hook_manager is None:
        _global_hook_manager = EnhancedHookManager(signing_key)
    return _global_hook_manager


if __name__ == "__main__":
    manager = get_hook_manager()

    print("=" * 60)
    print("Hook 系统增强测试")
    print("=" * 60)

    print("\n1. 创建沙箱:")
    sandbox_config = SandboxConfig(
        id="test-sandbox",
        name="Test Sandbox",
        max_memory_mb=64,
        max_cpu_percent=25,
        max_execution_time_ms=3000,
        allowed_modules=["math", "random", "json"]
    )
    manager.create_sandbox(sandbox_config)
    print(f"   沙箱已创建: {sandbox_config.id}")

    print("\n2. 注册 Hook:")
    hook = manager.register_hook(
        name="test_hook",
        hook_type=HookType.PRE_EXECUTE,
        script="result = math.sqrt(x)",
        description="测试 Hook",
        require_signature=True
    )
    print(f"   Hook 已注册: {hook.name} (ID: {hook.id})")

    print("\n3. 签名验证:")
    status = manager.verify_hook_signature(hook.id)
    print(f"   签名状态: {status.value}")

    print("\n4. 执行 Hook:")
    execution = manager.execute_hook(hook.id, {"x": 16})
    print(f"   执行状态: {execution.status}")
    print(f"   执行时间: {execution.duration_ms}ms")

    print("\n5. Hook 指标:")
    metrics = manager.get_hook_metrics(hook.id)
    if metrics:
        print(f"   总执行数: {metrics.total_executions}")
        print(f"   成功数: {metrics.successful_executions}")
        print(f"   平均延迟: {metrics.avg_execution_time_ms:.2f}ms")

    print("\n6. 健康报告:")
    report = manager.get_health_report()
    print(f"   总 Hook 数: {report['total_hooks']}")
    print(f"   活跃 Hook 数: {report['active_hooks']}")
    print(f"   总执行数: {report['total_executions']}")

    print("\n" + "=" * 60)
    print("Hook 系统增强测试完成")
    print("=" * 60)
