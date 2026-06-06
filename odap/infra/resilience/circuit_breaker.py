"""
熔断器中间件 (Circuit Breaker Middleware)
========================================

T330 / SC-06: 对外部服务 (LLM / Neo4j / OPA) 实现熔断保护。

核心特性:
- 三状态机: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
- 滚动窗口: 错误率 > 50% 持续 30s 触发熔断
- 半开探测: 进入 HALF_OPEN 后放行 1 个探测请求
- 多服务隔离: 每个 service_name 独立熔断器实例
- 线程安全: threading.Lock 保护共享状态
- 装饰器和上下文管理器友好

用法::

    from odap.infra.resilience.circuit_breaker import (
        circuit_breaker, get_circuit_breaker,
    )

    # 方式 1: 装饰器
    @circuit_breaker("llm", failure_threshold_pct=0.5)
    def call_llm(prompt: str):
        ...

    # 方式 2: 直接使用
    cb = get_circuit_breaker("neo4j")
    result = cb.call(some_func, arg1, arg2)

    # 方式 3: 异步
    result = await cb.acall(some_async_func, arg1)
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Awaitable, Callable, Deque, Dict, List, Optional

logger = logging.getLogger("circuit_breaker")


class CircuitState(str, Enum):
    """熔断器状态机"""
    CLOSED = "closed"        # 关闭: 正常放行
    OPEN = "open"            # 打开: 拒绝所有调用
    HALF_OPEN = "half_open"  # 半开: 放行探测请求


class CircuitOpenError(Exception):
    """熔断器打开时抛出"""

    def __init__(
        self,
        service_name: str,
        opened_at: datetime,
        retry_after_seconds: float,
    ):
        self.service_name = service_name
        self.opened_at = opened_at
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Circuit breaker '{service_name}' is OPEN. "
            f"Retry after {retry_after_seconds:.1f}s"
        )


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    service_name: str
    failure_threshold_pct: float = 0.5   # 错误率阈值 (默认 50%)
    window_seconds: int = 30             # 滚动窗口秒数
    min_requests_in_window: int = 5      # 触发计算的最少请求数
    open_duration_seconds: int = 60      # OPEN 状态保持秒数
    half_open_max_probes: int = 1        # HALF_OPEN 放行探测数


@dataclass
class CircuitCallResult:
    """单次调用结果记录"""
    success: bool
    duration_ms: float
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class CircuitBreaker:
    """熔断器 (按服务实例化)

    状态机:
    - CLOSED: 正常放行, 持续统计窗口内错误率
    - OPEN:   拒绝所有调用, 等待 open_duration_seconds 后进入 HALF_OPEN
    - HALF_OPEN: 放行 half_open_max_probes 个探测请求
        - 探测成功 -> CLOSED
        - 探测失败 -> OPEN (重置 opened_at)
    """

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self._state: CircuitState = CircuitState.CLOSED
        self._lock = threading.Lock()
        self._call_history: Deque[CircuitCallResult] = Deque()
        self._opened_at: Optional[datetime] = None
        self._half_open_in_flight: int = 0

    @property
    def state(self) -> CircuitState:
        """当前状态 (线程安全)"""
        with self._lock:
            return self._state

    @property
    def config(self) -> CircuitBreakerConfig:
        return self._config

    @config.setter
    def config(self, value: CircuitBreakerConfig) -> None:
        self._config = value

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """同步执行被保护函数 (线程安全)"""
        self._pre_call_check()
        start = time.monotonic()
        success = False
        error_msg: Optional[str] = None
        try:
            result = func(*args, **kwargs)
            success = True
            return result
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self._finish_call(start, success, error_msg)

    async def acall(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """异步执行被保护函数"""
        self._pre_call_check()
        start = time.monotonic()
        success = False
        error_msg: Optional[str] = None
        try:
            result = await func(*args, **kwargs)
            success = True
            return result
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self._finish_call(start, success, error_msg)

    def _pre_call_check(self) -> None:
        """调用前状态检查: OPEN 拒绝 / HALF_OPEN 限制探测数 (线程安全)"""
        self._check_state_transition()
        with self._lock:
            if self._state == CircuitState.OPEN:
                raise CircuitOpenError(
                    service_name=self.config.service_name,
                    opened_at=self._opened_at or datetime.now(),
                    retry_after_seconds=self._compute_retry_after(),
                )
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_in_flight >= self.config.half_open_max_probes:
                    raise CircuitOpenError(
                        service_name=self.config.service_name,
                        opened_at=self._opened_at or datetime.now(),
                        retry_after_seconds=self._compute_retry_after(),
                    )
                self._half_open_in_flight += 1

    def _finish_call(
        self,
        start: float,
        success: bool,
        error_msg: Optional[str],
    ) -> None:
        """调用结束后记录结果"""
        duration_ms = (time.monotonic() - start) * 1000.0
        result_obj = CircuitCallResult(
            success=success,
            duration_ms=duration_ms,
            error=error_msg,
        )
        self._record_call(result_obj)

    def get_state(self) -> Dict[str, Any]:
        """返回当前状态快照 (线程安全)"""
        with self._lock:
            self._prune_history_locked()
            total = len(self._call_history)
            failures = sum(1 for r in self._call_history if not r.success)
            successes = total - failures
            error_rate = (failures / total) if total > 0 else 0.0
            return {
                "state": self._state.value,
                "service_name": self.config.service_name,
                "failure_count": failures,
                "success_count": successes,
                "error_rate": error_rate,
                "opened_at": self._opened_at.isoformat() if self._opened_at else None,
                "window_seconds": self.config.window_seconds,
                "failure_threshold_pct": self.config.failure_threshold_pct,
                "min_requests_in_window": self.config.min_requests_in_window,
                "open_duration_seconds": self.config.open_duration_seconds,
                "half_open_max_probes": self.config.half_open_max_probes,
            }

    def reset(self) -> None:
        """手动重置熔断器 (线程安全)"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._call_history.clear()
            self._opened_at = None
            self._half_open_in_flight = 0
        logger.info("Circuit breaker '%s' manually reset", self.config.service_name)

    def _record_call(self, result: CircuitCallResult) -> None:
        """记录一次调用结果并可能触发状态转换"""
        with self._lock:
            self._call_history.append(result)
            self._prune_history_locked()
            # 探测请求完成, 释放 in-flight 计数
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_in_flight = max(0, self._half_open_in_flight - 1)
                if result.success:
                    self._state = CircuitState.CLOSED
                    self._opened_at = None
                    self._call_history.clear()
                    logger.info(
                        "Circuit breaker '%s' probe succeeded -> CLOSED",
                        self.config.service_name,
                    )
                else:
                    self._state = CircuitState.OPEN
                    self._opened_at = datetime.now()
                    self._call_history.clear()
                    logger.warning(
                        "Circuit breaker '%s' probe failed -> OPEN",
                        self.config.service_name,
                    )
                return

            # CLOSED 状态: 检查是否应打开
            if self._state == CircuitState.CLOSED and self._should_open_locked():
                self._state = CircuitState.OPEN
                self._opened_at = datetime.now()
                logger.warning(
                    "Circuit breaker '%s' tripped to OPEN",
                    self.config.service_name,
                )

    def _should_open_locked(self) -> bool:
        """检查是否应打开 (仅在持有锁时调用)"""
        total = len(self._call_history)
        if total < self.config.min_requests_in_window:
            return False
        failures = sum(1 for r in self._call_history if not r.success)
        error_rate = failures / total
        return error_rate > self.config.failure_threshold_pct

    def _prune_history_locked(self) -> None:
        """清理窗口外的历史 (仅在持有锁时调用)"""
        cutoff = datetime.now() - timedelta(seconds=self.config.window_seconds)
        while self._call_history and self._call_history[0].timestamp < cutoff:
            self._call_history.popleft()

    def _check_state_transition(self) -> None:
        """检查 OPEN -> HALF_OPEN 状态转换"""
        with self._lock:
            if self._state == CircuitState.OPEN and self._opened_at is not None:
                elapsed = (datetime.now() - self._opened_at).total_seconds()
                if elapsed >= self.config.open_duration_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_in_flight = 0
                    logger.info(
                        "Circuit breaker '%s' OPEN -> HALF_OPEN after %.1fs",
                        self.config.service_name,
                        elapsed,
                    )

    def _compute_retry_after(self) -> float:
        """计算还需等待多少秒才能进入 HALF_OPEN (需持有锁)"""
        if self._opened_at is None:
            return 0.0
        elapsed = (datetime.now() - self._opened_at).total_seconds()
        remaining = self.config.open_duration_seconds - elapsed
        return max(0.0, remaining)

    def _force_state(self, state: CircuitState) -> None:
        """强制设置状态 (仅用于测试)"""
        with self._lock:
            self._state = state
            if state == CircuitState.HALF_OPEN:
                self._half_open_in_flight = 0


# ============== Registry (多服务单例) ==============

_circuit_breakers: Dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_circuit_breaker(
    service_name: str,
    **config_kwargs: Any,
) -> CircuitBreaker:
    """获取或创建指定服务的熔断器 (线程安全单例)"""
    with _breakers_lock:
        if service_name not in _circuit_breakers:
            config = CircuitBreakerConfig(service_name=service_name, **config_kwargs)
            _circuit_breakers[service_name] = CircuitBreaker(config)
        return _circuit_breakers[service_name]


def reset_all_circuit_breakers() -> None:
    """重置所有熔断器 (主要用于测试)"""
    with _breakers_lock:
        for cb in _circuit_breakers.values():
            cb.reset()
        _circuit_breakers.clear()


# ============== Decorator ==============

def circuit_breaker(
    service_name: str,
    **config_kwargs: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器: 对函数应用熔断保护

    用法::

        @circuit_breaker("llm")
        def call_llm(prompt):
            ...

        @circuit_breaker("neo4j", failure_threshold_pct=0.7)
        async def query_neo4j(cypher):
            ...
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cb = get_circuit_breaker(service_name, **config_kwargs)

        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await cb.acall(func, *args, **kwargs)
            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return cb.call(func, *args, **kwargs)
        return sync_wrapper

    return decorator
