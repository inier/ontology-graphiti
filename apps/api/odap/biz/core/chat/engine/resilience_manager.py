"""Chat Resilience Manager — AI 助手的韧性编排层。

基于现有韧性基础设施（CircuitBreaker, FaultRecovery, HealthMonitor），
为 UnifiedChatService 提供：
1. LLM 调用熔断保护（复用 engine_adapter 的 CircuitBreaker）
2. 工具执行隔离（单个工具失败不影响整个对话）
3. 指数退避重试（带 jitter）
4. 启动健康门控（依赖未就绪时拒绝流量）
5. 可观测性埋点（每次失败/重试/熔断均记录结构化日志）

设计原则：
- 不降级到另一条同样脆弱的路径
- 透明传递：韧性层不改变事件流格式
- 快速失败 > 长时间等待
- 每个依赖有独立的熔断器和重试策略
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("chat_resilience")


# ═══════════════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════════════

class ResilienceEvent(str, Enum):
    """韧性事件类型（用于结构化日志和指标）。"""
    LLM_CALL_STARTED = "llm_call_started"
    LLM_CALL_SUCCEEDED = "llm_call_succeeded"
    LLM_CALL_FAILED = "llm_call_failed"
    LLM_CALL_RETRYING = "llm_call_retrying"
    LLM_CIRCUIT_OPEN = "llm_circuit_open"
    LLM_CIRCUIT_HALF_OPEN = "llm_circuit_half_open"
    LLM_CIRCUIT_CLOSED = "llm_circuit_closed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"
    TOOL_EXECUTION_SKIPPED = "tool_execution_skipped"
    STARTUP_CHECK_PASSED = "startup_check_passed"
    STARTUP_CHECK_FAILED = "startup_check_failed"
    HEALTH_DEGRADED = "health_degraded"
    HEALTH_RECOVERED = "health_recovered"


@dataclass
class ResilienceMetrics:
    """韧性指标计数器。"""
    llm_calls_total: int = 0
    llm_calls_succeeded: int = 0
    llm_calls_failed: int = 0
    llm_retries_total: int = 0
    circuit_open_count: int = 0
    tool_failures_total: int = 0
    tool_skips_total: int = 0
    startup_failures: int = 0

    def snapshot(self) -> Dict[str, int]:
        return {
            "llm_calls_total": self.llm_calls_total,
            "llm_calls_succeeded": self.llm_calls_succeeded,
            "llm_calls_failed": self.llm_calls_failed,
            "llm_retries_total": self.llm_retries_total,
            "circuit_open_count": self.circuit_open_count,
            "tool_failures_total": self.tool_failures_total,
            "tool_skips_total": self.tool_skips_total,
            "startup_failures": self.startup_failures,
        }


# ═══════════════════════════════════════════════════════════════════
# Retry Policy
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RetryPolicy:
    """指数退避重试策略（带 jitter）。"""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    jitter: bool = True
    retryable_exceptions: tuple = (
        ConnectionError, TimeoutError, asyncio.TimeoutError,
    )

    def delay_for_attempt(self, attempt: int) -> float:
        """计算第 N 次重试的延迟时间（指数退避 + 可选 jitter）。"""
        delay = min(
            self.base_delay_seconds * (2 ** attempt),
            self.max_delay_seconds,
        )
        if self.jitter:
            delay = delay * (0.5 + random.random())  # 50%-150% jitter
        return delay

    def is_retryable(self, exception: Exception) -> bool:
        """判断异常是否可重试。"""
        return isinstance(exception, self.retryable_exceptions)


async def retry_with_backoff(
    fn: Callable,
    *args,
    policy: RetryPolicy = None,
    context: str = "",
    **kwargs,
) -> Any:
    """带指数退避的异步重试。

    Args:
        fn: 异步可调用对象
        policy: 重试策略，默认使用 RetryPolicy()
        context: 日志上下文（用于标识是哪个操作）

    Returns:
        fn 的返回值

    Raises:
        最后一次重试的异常（如果所有重试均失败）
    """
    policy = policy or RetryPolicy()
    last_exception = None

    for attempt in range(policy.max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if not policy.is_retryable(e):
                logger.warning(
                    "Retry: %s attempt %d failed with non-retryable error: %s",
                    context, attempt, e,
                )
                raise

            if attempt < policy.max_retries:
                delay = policy.delay_for_attempt(attempt)
                logger.warning(
                    "Retry: %s attempt %d failed: %s, retrying in %.1fs",
                    context, attempt + 1, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Retry: %s all %d attempts exhausted: %s",
                    context, policy.max_retries + 1, e,
                )

    raise last_exception  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════
# Startup Health Gate
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DependencyStatus:
    """单个依赖的健康状态。"""
    name: str
    healthy: bool
    latency_ms: float = 0.0
    error: Optional[str] = None
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StartupHealthGate:
    """启动健康门控 — 关键依赖就绪前拒绝流量。

    不阻止进程启动，但在 health endpoint 中暴露状态，
    反向代理/负载均衡器据此决定是否路由流量。
    """

    def __init__(self, required_dependencies: list[str] = None):
        self._statuses: Dict[str, DependencyStatus] = {}
        self._required = required_dependencies or [
            "openharness", "llm_api", "tool_registry",
        ]
        self._checked = False
        self._all_healthy = False

    async def check_all(self) -> Dict[str, DependencyStatus]:
        """检查所有依赖的健康状态。

        只检查一次（幂等），后续调用返回缓存结果。
        如需重新检查，调用 force_recheck()。
        """
        if self._checked:
            return dict(self._statuses)

        results = {}

        # Check 1: OpenHarness
        results["openharness"] = await self._check_openharness()

        # Check 2: LLM API
        results["llm_api"] = await self._check_llm_api()

        # Check 3: Tool Registry
        results["tool_registry"] = self._check_tool_registry()

        self._statuses = results
        self._checked = True

        # Determine overall health
        missing = [name for name in self._required if not results.get(name, DependencyStatus(name=name, healthy=False)).healthy]
        self._all_healthy = len(missing) == 0

        if self._all_healthy:
            logger.info("StartupHealthGate: all %d dependencies healthy", len(results))
        else:
            logger.warning(
                "StartupHealthGate: %d/%d dependencies healthy, missing: %s",
                len(results) - len(missing), len(results), missing,
            )

        return dict(results)

    async def force_recheck(self) -> Dict[str, DependencyStatus]:
        """强制重新检查所有依赖。"""
        self._checked = False
        return await self.check_all()

    @property
    def is_ready(self) -> bool:
        return self._all_healthy

    @property
    def statuses(self) -> Dict[str, DependencyStatus]:
        return dict(self._statuses)

    # ── Individual checks ──────────────────────────────────────────────

    async def _check_openharness(self) -> DependencyStatus:
        start = time.perf_counter()
        try:
            from odap.infra.openharness.engine_adapter import (
                OHQueryEngineFactory,
                OPENHARNESS_AVAILABLE,
            )
            if not OPENHARNESS_AVAILABLE:
                return DependencyStatus(
                    name="openharness", healthy=False,
                    error="OPENHARNESS_AVAILABLE is False",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
            factory = OHQueryEngineFactory.get_instance()
            return DependencyStatus(
                name="openharness",
                healthy=factory._initialized,
                error=None if factory._initialized else "factory not initialized",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return DependencyStatus(
                name="openharness", healthy=False,
                error=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    async def _check_llm_api(self) -> DependencyStatus:
        start = time.perf_counter()
        try:
            from odap.infra.config_composer import get_config
            api_key = get_config("llm.api_key", "")
            if not api_key:
                return DependencyStatus(
                    name="llm_api", healthy=False,
                    error="llm.api_key not configured",
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
            return DependencyStatus(
                name="llm_api", healthy=True,
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return DependencyStatus(
                name="llm_api", healthy=False, error=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )

    def _check_tool_registry(self) -> DependencyStatus:
        start = time.perf_counter()
        try:
            from odap.biz.core.chat.tools import ALL_TOOLS_EXTENDED
            return DependencyStatus(
                name="tool_registry",
                healthy=len(ALL_TOOLS_EXTENDED) >= 16,
                error=None if len(ALL_TOOLS_EXTENDED) >= 16
                else f"only {len(ALL_TOOLS_EXTENDED)} tools (expected 16+)",
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return DependencyStatus(
                name="tool_registry", healthy=False, error=str(e),
                latency_ms=(time.perf_counter() - start) * 1000,
            )


# ═══════════════════════════════════════════════════════════════════
# Tool Execution Resilience
# ═══════════════════════════════════════════════════════════════════

class ToolExecutionResilience:
    """工具执行韧性 — 单个工具失败不影响整个 Agent Loop。

    在 OH Agent Loop 中，如果 LLM 调用了 3 个工具，其中第 2 个失败，
    默认行为是中断整个循环。此类提供工具级隔离：
    - 捕获工具异常 → 返回错误结果（而非抛出）
    - 记录失败指标
    - 可选：对可重试的工具执行重试
    """

    def __init__(self, metrics: ResilienceMetrics = None):
        self._metrics = metrics or ResilienceMetrics()

    async def execute_safely(
        self,
        tool_name: str,
        execute_fn: Callable,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """安全执行工具 — 失败不抛出，返回结构化错误。

        Returns:
            {"status": "success", "result": ...} 或
            {"status": "error", "message": ..., "tool": ...}
        """
        try:
            result = await execute_fn(*args, **kwargs)
            return {"status": "success", "result": result}
        except Exception as e:
            self._metrics.tool_failures_total += 1
            logger.warning(
                "ToolExecutionResilience: tool '%s' failed (isolated): %s",
                tool_name, e,
            )
            return {
                "status": "error",
                "tool": tool_name,
                "message": str(e),
                "recoverable": isinstance(e, (ConnectionError, TimeoutError)),
            }

    async def execute_with_retry(
        self,
        tool_name: str,
        execute_fn: Callable,
        *args,
        policy: RetryPolicy = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """带重试的安全工具执行。

        对可重试异常（连接超时等）自动重试，不可重试异常直接返回错误。
        """
        try:
            result = await retry_with_backoff(
                execute_fn, *args,
                policy=policy or RetryPolicy(max_retries=2),
                context=f"tool:{tool_name}",
                **kwargs,
            )
            return {"status": "success", "result": result}
        except Exception as e:
            self._metrics.tool_failures_total += 1
            logger.warning(
                "ToolExecutionResilience: tool '%s' failed after retries: %s",
                tool_name, e,
            )
            return {
                "status": "error",
                "tool": tool_name,
                "message": str(e),
            }


# ═══════════════════════════════════════════════════════════════════
# Chat Resilience Manager (orchestrator)
# ═══════════════════════════════════════════════════════════════════

class ChatResilienceManager:
    """AI 助手韧性编排器 — 管理所有韧性组件的生命周期。

    提供：
    - startup_health_gate:  启动时检查依赖，未就绪时暴露 degraded 状态
    - llm_circuit_breaker:  从 engine_adapter 复用，保护 LLM 调用
    - tool_resilience:      工具级隔离，单工具失败不中断对话
    - metrics:              全局指标计数器
    """

    _instance: Optional["ChatResilienceManager"] = None

    def __init__(self):
        self.metrics = ResilienceMetrics()
        self.startup_gate = StartupHealthGate()
        self.tool_resilience = ToolExecutionResilience(self.metrics)
        self._llm_circuit_breaker = None
        self._startup_checked = False

    @classmethod
    def get_instance(cls) -> "ChatResilienceManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Circuit breaker ─────────────────────────────────────────────────

    @property
    def llm_circuit_breaker(self):
        """LLM 调用熔断器（复用 engine_adapter 已创建的同名实例）。"""
        if self._llm_circuit_breaker is None:
            try:
                from odap.infra.resilience.circuit_breaker import get_circuit_breaker
                self._llm_circuit_breaker = get_circuit_breaker(
                    "agent_loop_llm",
                    failure_threshold_pct=0.5,
                )
            except ImportError:
                self._llm_circuit_breaker = None
        return self._llm_circuit_breaker

    # ── Startup validation ──────────────────────────────────────────────

    async def ensure_ready(self) -> bool:
        """确保所有依赖就绪。仅在首次调用时检查（幂等）。

        Returns:
            True 如果所有依赖健康
        """
        if self._startup_checked and self.startup_gate.is_ready:
            return True

        await self.startup_gate.check_all()
        self._startup_checked = True

        if not self.startup_gate.is_ready:
            logger.error(
                "ChatResilienceManager: startup health check FAILED. "
                "The /api/chat/ endpoint will return 503 until resolved."
            )
            self.metrics.startup_failures += 1

        return self.startup_gate.is_ready

    # ── LLM call with circuit protection ────────────────────────────────

    async def call_llm_protected(
        self,
        fn: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """通过熔断器保护调用 LLM。

        如果熔断器打开，直接抛出 CircuitOpenError（不重试）。
        调用方应捕获此异常并返回友好错误。
        """
        self.metrics.llm_calls_total += 1

        cb = self.llm_circuit_breaker
        if cb is None:
            # No circuit breaker available — call directly
            try:
                result = await fn(*args, **kwargs)
                self.metrics.llm_calls_succeeded += 1
                return result
            except Exception:
                self.metrics.llm_calls_failed += 1
                raise

        try:
            from odap.infra.resilience.circuit_breaker import CircuitOpenError

            async def _wrapped():
                return await fn(*args, **kwargs)

            result = await cb.acall(_wrapped)
            self.metrics.llm_calls_succeeded += 1
            return result

        except CircuitOpenError:
            self.metrics.circuit_open_count += 1
            logger.warning("ChatResilienceManager: LLM circuit breaker OPEN — rejecting call")
            raise
        except Exception:
            self.metrics.llm_calls_failed += 1
            raise

    # ── Health summary ──────────────────────────────────────────────────

    def health_summary(self) -> Dict[str, Any]:
        """返回完整的健康状态摘要（供 health endpoint 使用）。"""
        cb_state = "unknown"
        if self.llm_circuit_breaker:
            cb_state = self.llm_circuit_breaker._state.value if hasattr(self.llm_circuit_breaker, '_state') else "unknown"

        return {
            "status": "healthy" if self.startup_gate.is_ready else "degraded",
            "dependencies": {
                name: {
                    "healthy": dep.healthy,
                    "latency_ms": round(dep.latency_ms, 1),
                    "error": dep.error,
                }
                for name, dep in self.startup_gate.statuses.items()
            },
            "circuit_breaker": {
                "llm": cb_state,
            },
            "metrics": self.metrics.snapshot(),
        }


# ── Singleton ──

def get_chat_resilience() -> ChatResilienceManager:
    """获取 ChatResilienceManager 单例。"""
    return ChatResilienceManager.get_instance()
