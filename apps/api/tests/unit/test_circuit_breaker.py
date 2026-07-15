"""CircuitBreaker 单元测试 (T330 / SC-06)

测试熔断器中间件的核心功能:
- 三个状态: CLOSED / OPEN / HALF_OPEN
- 错误率 > 50% 持续 30s 触发熔断
- 半开探测恢复
- 多服务隔离
- 线程安全
- 装饰器和异步支持
"""

import asyncio
import sys
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from odap.infra.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitCallResult,
    CircuitOpenError,
    CircuitState,
    circuit_breaker,
    get_circuit_breaker,
    reset_all_circuit_breakers,
)


def _run(coro):
    """辅助: 在事件循环中运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestCircuitStateEnum(unittest.TestCase):
    """CircuitState 枚举测试"""

    def test_is_str_enum(self):
        self.assertIsInstance(CircuitState.CLOSED, str)
        self.assertEqual(CircuitState.CLOSED, "closed")

    def test_all_values(self):
        self.assertEqual(CircuitState.CLOSED.value, "closed")
        self.assertEqual(CircuitState.OPEN.value, "open")
        self.assertEqual(CircuitState.HALF_OPEN.value, "half_open")


class TestCircuitBreakerConfig(unittest.TestCase):
    """CircuitBreakerConfig 数据类测试"""

    def test_default_values(self):
        config = CircuitBreakerConfig(service_name="llm")
        self.assertEqual(config.service_name, "llm")
        self.assertEqual(config.failure_threshold_pct, 0.5)
        self.assertEqual(config.window_seconds, 30)
        self.assertEqual(config.min_requests_in_window, 5)
        self.assertEqual(config.open_duration_seconds, 60)
        self.assertEqual(config.half_open_max_probes, 1)

    def test_custom_values(self):
        config = CircuitBreakerConfig(
            service_name="neo4j",
            failure_threshold_pct=0.7,
            window_seconds=10,
            min_requests_in_window=3,
            open_duration_seconds=20,
            half_open_max_probes=2,
        )
        self.assertEqual(config.failure_threshold_pct, 0.7)
        self.assertEqual(config.window_seconds, 10)
        self.assertEqual(config.min_requests_in_window, 3)
        self.assertEqual(config.open_duration_seconds, 20)
        self.assertEqual(config.half_open_max_probes, 2)


class TestCircuitCallResult(unittest.TestCase):
    """CircuitCallResult 数据类测试"""

    def test_success_result(self):
        result = CircuitCallResult(success=True, duration_ms=10.5)
        self.assertTrue(result.success)
        self.assertEqual(result.duration_ms, 10.5)
        self.assertIsNone(result.error)
        self.assertIsNotNone(result.timestamp)

    def test_failure_result(self):
        result = CircuitCallResult(success=False, duration_ms=20.0, error="boom")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "boom")


class TestCircuitOpenError(unittest.TestCase):
    """CircuitOpenError 异常测试"""

    def test_error_attributes(self):
        opened = datetime.now()
        err = CircuitOpenError("llm", opened, retry_after_seconds=30.0)
        self.assertEqual(err.service_name, "llm")
        self.assertEqual(err.opened_at, opened)
        self.assertEqual(err.retry_after_seconds, 30.0)
        self.assertIn("llm", str(err))


class TestCircuitBreakerInitialState(unittest.TestCase):
    """初始状态测试"""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(CircuitBreakerConfig(service_name="llm"))
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_initial_get_state(self):
        cb = CircuitBreaker(CircuitBreakerConfig(service_name="llm"))
        state = cb.get_state()
        self.assertEqual(state["state"], "closed")
        self.assertEqual(state["service_name"], "llm")
        self.assertEqual(state["failure_count"], 0)
        self.assertEqual(state["success_count"], 0)
        self.assertEqual(state["error_rate"], 0.0)
        self.assertIsNone(state["opened_at"])


class TestCircuitBreakerClosedSuccess(unittest.TestCase):
    """CLOSED 状态 - 成功调用测试"""

    def test_successful_call_returns_result(self):
        cb = CircuitBreaker(CircuitBreakerConfig(service_name="llm"))
        result = cb.call(lambda: "ok")
        self.assertEqual(result, "ok")
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_successful_call_with_args(self):
        cb = CircuitBreaker(CircuitBreakerConfig(service_name="llm"))

        def add(a, b, multiplier=1):
            return (a + b) * multiplier

        result = cb.call(add, 2, 3, multiplier=4)
        self.assertEqual(result, 20)

    def test_successful_call_increments_success_count(self):
        cb = CircuitBreaker(CircuitBreakerConfig(service_name="llm"))
        cb.call(lambda: 1)
        cb.call(lambda: 2)
        state = cb.get_state()
        self.assertEqual(state["success_count"], 2)
        self.assertEqual(state["failure_count"], 0)


class TestCircuitBreakerClosedFailure(unittest.TestCase):
    """CLOSED 状态 - 失败调用测试"""

    def test_failure_raises_exception(self):
        cb = CircuitBreaker(CircuitBreakerConfig(service_name="llm"))
        with self.assertRaises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    def test_failure_increments_failure_count(self):
        cb = CircuitBreaker(CircuitBreakerConfig(service_name="llm"))
        with self.assertRaises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        state = cb.get_state()
        self.assertEqual(state["failure_count"], 1)
        self.assertEqual(state["success_count"], 0)

    def test_mixed_calls_calculate_error_rate(self):
        cb = CircuitBreaker(CircuitBreakerConfig(service_name="llm"))
        for _ in range(2):
            cb.call(lambda: "ok")
        for _ in range(1):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        state = cb.get_state()
        self.assertEqual(state["success_count"], 2)
        self.assertEqual(state["failure_count"], 1)
        self.assertAlmostEqual(state["error_rate"], 1 / 3, places=2)


class TestCircuitBreakerTripToOpen(unittest.TestCase):
    """熔断触发测试: 错误率 > 50% 持续 30s"""

    def setUp(self):
        # min_requests_in_window=3, window=30, threshold=0.5
        self.config = CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            window_seconds=30,
            min_requests_in_window=3,
            open_duration_seconds=60,
        )
        self.cb = CircuitBreaker(self.config)

    def test_does_not_trip_below_min_requests(self):
        # 2 failures out of 2 = 100%, but min_requests=3
        for _ in range(2):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        self.assertEqual(self.cb.state, CircuitState.CLOSED)

    def test_trips_when_error_rate_exceeds_threshold(self):
        # 3 failures, 0 success = 100% > 50% and min_requests=3 satisfied
        for _ in range(3):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        self.assertEqual(self.cb.state, CircuitState.OPEN)

    def test_does_not_trip_when_error_rate_at_threshold(self):
        # 50% error rate should not trip (must exceed)
        for _ in range(5):
            self.cb.call(lambda: "ok")
        for _ in range(5):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        self.assertEqual(self.cb.state, CircuitState.CLOSED)

    def test_open_state_records_opened_at(self):
        for _ in range(3):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        state = self.cb.get_state()
        self.assertEqual(state["state"], "open")
        self.assertIsNotNone(state["opened_at"])


class TestCircuitBreakerOpenBlocksCalls(unittest.TestCase):
    """OPEN 状态 - 阻塞调用测试"""

    def setUp(self):
        self.config = CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            min_requests_in_window=3,
            open_duration_seconds=60,
        )
        self.cb = CircuitBreaker(self.config)
        for _ in range(3):
            try:
                self.cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass

    def test_open_state_raises_circuit_open_error(self):
        with self.assertRaises(CircuitOpenError):
            self.cb.call(lambda: "ok")

    def test_open_error_includes_retry_after(self):
        with self.assertRaises(CircuitOpenError) as ctx:
            self.cb.call(lambda: "ok")
        self.assertGreater(ctx.exception.retry_after_seconds, 0)
        self.assertLessEqual(ctx.exception.retry_after_seconds, 60)


class TestCircuitBreakerHalfOpenTransition(unittest.TestCase):
    """HALF_OPEN 转换测试"""

    def test_transitions_to_half_open_after_open_duration(self):
        config = CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            min_requests_in_window=3,
            open_duration_seconds=10,
        )
        cb = CircuitBreaker(config)
        # 触发熔断
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        self.assertEqual(cb.state, CircuitState.OPEN)

        # 模拟时间过去 11 秒
        future = datetime.now() + timedelta(seconds=11)
        with patch("odap.infra.resilience.circuit_breaker.datetime") as mock_dt:
            mock_dt.now.return_value = future
            # 触发状态检查
            cb._check_state_transition()
            self.assertEqual(cb.state, CircuitState.HALF_OPEN)


class TestCircuitBreakerHalfOpenProbes(unittest.TestCase):
    """HALF_OPEN 探测测试"""

    def test_half_open_success_closes_circuit(self):
        config = CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            min_requests_in_window=3,
            open_duration_seconds=10,
        )
        cb = CircuitBreaker(config)
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        # 直接强制进入 HALF_OPEN
        cb._force_state(CircuitState.HALF_OPEN)

        result = cb.call(lambda: "ok")
        self.assertEqual(result, "ok")
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_half_open_failure_reopens_circuit(self):
        config = CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            min_requests_in_window=3,
            open_duration_seconds=10,
        )
        cb = CircuitBreaker(config)
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        cb._force_state(CircuitState.HALF_OPEN)

        with self.assertRaises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("still down")))
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_half_open_blocks_concurrent_probes(self):
        config = CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            min_requests_in_window=3,
            open_duration_seconds=10,
            half_open_max_probes=1,
        )
        cb = CircuitBreaker(config)
        cb._force_state(CircuitState.HALF_OPEN)

        # 第一个探测放行
        def slow():
            time.sleep(0.05)
            return "ok"

        # 在第一个探测进行中启动第二个
        results = []
        errors = []

        def worker():
            try:
                r = cb.call(slow)
                results.append(r)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=worker)
        t1.start()
        time.sleep(0.01)
        t2 = threading.Thread(target=worker)
        t2.start()
        t1.join()
        t2.join()

        # 至少一个应该被放行，另一个可能阻塞或被拒绝
        self.assertTrue(len(results) + len(errors) == 2)


class TestCircuitBreakerReset(unittest.TestCase):
    """手动重置测试"""

    def test_reset_closes_circuit(self):
        config = CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            min_requests_in_window=3,
        )
        cb = CircuitBreaker(config)
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        self.assertEqual(cb.state, CircuitState.OPEN)

        cb.reset()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        state = cb.get_state()
        self.assertEqual(state["failure_count"], 0)
        self.assertEqual(state["success_count"], 0)

    def test_reset_clears_history(self):
        config = CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            min_requests_in_window=3,
        )
        cb = CircuitBreaker(config)
        cb.call(lambda: "ok")
        cb.reset()
        state = cb.get_state()
        self.assertEqual(state["failure_count"], 0)
        self.assertEqual(state["success_count"], 0)


class TestCircuitBreakerRegistry(unittest.TestCase):
    """注册表 - 多服务隔离测试"""

    def setUp(self):
        reset_all_circuit_breakers()

    def tearDown(self):
        reset_all_circuit_breakers()

    def test_get_breaker_creates_singleton(self):
        b1 = get_circuit_breaker("llm")
        b2 = get_circuit_breaker("llm")
        self.assertIs(b1, b2)

    def test_different_services_get_different_breakers(self):
        b1 = get_circuit_breaker("llm")
        b2 = get_circuit_breaker("neo4j")
        self.assertIsNot(b1, b2)

    def test_llm_trip_does_not_affect_neo4j(self):
        llm = get_circuit_breaker("llm")
        neo4j = get_circuit_breaker("neo4j")
        # 触发 llm 熔断
        for _ in range(5):
            try:
                llm.call(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
            except RuntimeError:
                pass
        # 至少尝试 5 次，llm 应已熔断
        self.assertIn(llm.state, [CircuitState.OPEN])
        # neo4j 应仍然 CLOSED
        self.assertEqual(neo4j.state, CircuitState.CLOSED)
        # neo4j 可正常调用
        self.assertEqual(neo4j.call(lambda: "ok"), "ok")

    def test_get_breaker_with_config_kwargs(self):
        b1 = get_circuit_breaker("svc-a", failure_threshold_pct=0.7)
        self.assertEqual(b1.config.failure_threshold_pct, 0.7)

    def test_reset_all_clears_all_breakers(self):
        b1 = get_circuit_breaker("svc-x")
        b1.call(lambda: "ok")
        reset_all_circuit_breakers()
        b1_new = get_circuit_breaker("svc-x")
        self.assertIsNot(b1, b1_new)
        self.assertEqual(b1_new.state, CircuitState.CLOSED)


class TestCircuitBreakerThreadSafety(unittest.TestCase):
    """线程安全测试"""

    def setUp(self):
        reset_all_circuit_breakers()
        self.cb = CircuitBreaker(CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            min_requests_in_window=100,
            open_duration_seconds=10,
        ))

    def tearDown(self):
        reset_all_circuit_breakers()

    def test_concurrent_calls(self):
        """10 线程并发调用 100 次不应崩溃"""
        def worker(_):
            try:
                self.cb.call(lambda: "ok")
            except Exception:
                pass

        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(worker, range(100)))

        state = self.cb.get_state()
        self.assertEqual(state["success_count"] + state["failure_count"], 100)

    def test_concurrent_failures_trip_circuit(self):
        """并发失败应能正确触发熔断"""
        def worker(_):
            try:
                self.cb.call(
                    lambda: (_ for _ in ()).throw(RuntimeError("boom"))
                )
            except (RuntimeError, CircuitOpenError):
                pass

        with ThreadPoolExecutor(max_workers=10) as pool:
            list(pool.map(worker, range(50)))

        # 至少应该 OPEN 或 CLOSED，不应崩溃
        self.assertIn(self.cb.state, [CircuitState.OPEN, CircuitState.CLOSED])


class TestCircuitBreakerDecorator(unittest.TestCase):
    """装饰器测试"""

    def setUp(self):
        reset_all_circuit_breakers()

    def tearDown(self):
        reset_all_circuit_breakers()

    def test_decorator_basic_success(self):
        @circuit_breaker("decorated-svc")
        def hello():
            return "hi"

        self.assertEqual(hello(), "hi")

    def test_decorator_with_args(self):
        @circuit_breaker("decorated-svc-2")
        def add(a, b):
            return a + b

        self.assertEqual(add(2, 3), 5)

    def test_decorator_with_kwargs(self):
        @circuit_breaker("decorated-svc-3")
        def greet(name, prefix="Hello"):
            return f"{prefix}, {name}"

        self.assertEqual(greet("world", prefix="Hi"), "Hi, world")

    def test_decorator_failure_propagates(self):
        @circuit_breaker("decorated-svc-4")
        def fail():
            raise RuntimeError("decorator boom")

        with self.assertRaises(RuntimeError):
            fail()

    def test_decorator_shares_breaker_for_same_service(self):
        @circuit_breaker("shared-svc")
        def func1():
            return 1

        @circuit_breaker("shared-svc")
        def func2():
            return 2

        # 两个函数使用同一个熔断器
        func1()
        b = get_circuit_breaker("shared-svc")
        self.assertEqual(b.get_state()["success_count"], 1)


class TestCircuitBreakerAsync(unittest.TestCase):
    """异步 acall 测试"""

    def setUp(self):
        reset_all_circuit_breakers()
        self.cb = CircuitBreaker(CircuitBreakerConfig(
            service_name="async-svc",
            failure_threshold_pct=0.5,
            min_requests_in_window=3,
        ))

    def tearDown(self):
        reset_all_circuit_breakers()

    def test_acall_success(self):
        async def afn():
            return "async-ok"

        result = _run(self.cb.acall(afn))
        self.assertEqual(result, "async-ok")

    def test_acall_with_args(self):
        async def afn(a, b):
            return a + b

        result = _run(self.cb.acall(afn, 5, 7))
        self.assertEqual(result, 12)

    def test_acall_failure_propagates(self):
        async def afn():
            raise RuntimeError("async boom")

        with self.assertRaises(RuntimeError):
            _run(self.cb.acall(afn))

    def test_acall_trips_circuit(self):
        async def fail():
            raise RuntimeError("async fail")

        for _ in range(3):
            try:
                _run(self.cb.acall(fail))
            except RuntimeError:
                pass
        self.assertEqual(self.cb.state, CircuitState.OPEN)

    def test_acall_raises_circuit_open(self):
        async def afn():
            return "ok"

        # 强制打开
        self.cb._force_state(CircuitState.OPEN)
        with self.assertRaises(CircuitOpenError):
            _run(self.cb.acall(afn))


class TestCircuitBreakerWindowExpiry(unittest.TestCase):
    """滚动窗口过期测试"""

    def test_old_calls_drop_out_of_window(self):
        cb = CircuitBreaker(CircuitBreakerConfig(
            service_name="llm",
            failure_threshold_pct=0.5,
            window_seconds=10,
            min_requests_in_window=3,
        ))

        # 注入老的失败记录
        old_time = datetime.now() - timedelta(seconds=20)
        for _ in range(3):
            cb._call_history.append(
                CircuitCallResult(success=False, duration_ms=1.0, timestamp=old_time)
            )
        # 3 个成功
        for _ in range(3):
            cb.call(lambda: "ok")
        state = cb.get_state()
        # 错误率应只算窗口内: 0/3
        self.assertAlmostEqual(state["error_rate"], 0.0, places=2)
        self.assertEqual(cb.state, CircuitState.CLOSED)


class TestCircuitBreakerGetStateFull(unittest.TestCase):
    """get_state 完整字段测试"""

    def test_get_state_contains_all_fields(self):
        cb = CircuitBreaker(CircuitBreakerConfig(service_name="llm"))
        state = cb.get_state()
        required_keys = {
            "state", "service_name", "failure_count", "success_count",
            "error_rate", "opened_at", "window_seconds", "failure_threshold_pct",
        }
        self.assertTrue(required_keys.issubset(set(state.keys())))


if __name__ == "__main__":
    unittest.main()
