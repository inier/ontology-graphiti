"""
测试工具模块 - Testing Utilities
"""

import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Callable


class MockTimer:
    """模拟计时器"""

    def __init__(self):
        self._start_time = None
        self._elapsed = 0

    def start(self):
        self._start_time = time.perf_counter()

    def stop(self):
        if self._start_time:
            self._elapsed = (time.perf_counter() - self._start_time) * 1000

    @property
    def elapsed_ms(self) -> float:
        return self._elapsed


class TestTracer:
    """测试追踪器"""

    def __init__(self):
        self._spans = []
        self._current_span = None

    def start_span(self, name: str, metadata: Dict[str, Any] = None):
        span = {
            "name": name,
            "trace_id": str(uuid.uuid4()),
            "start_time": time.time(),
            "metadata": metadata or {},
            "events": []
        }
        self._spans.append(span)
        self._current_span = span
        return span

    def end_span(self, span: Dict = None):
        if span is None:
            span = self._current_span
        if span:
            span["end_time"] = time.time()
            span["duration_ms"] = (span["end_time"] - span["start_time"]) * 1000

    def add_event(self, name: str, metadata: Dict = None):
        if self._current_span:
            self._current_span["events"].append({
                "name": name,
                "timestamp": time.time(),
                "metadata": metadata or {}
            })

    def get_traces(self):
        return self._spans

    def clear(self):
        self._spans = []
        self._current_span = None


@contextmanager
def assert_time_limit(max_ms: float):
    """断言执行时间限制"""
    timer = MockTimer()
    timer.start()
    try:
        yield timer
    finally:
        timer.stop()
        elapsed = timer.elapsed_ms
        if elapsed > max_ms:
            raise AssertionError(f"Execution time {elapsed:.2f}ms exceeded limit {max_ms}ms")


class MockSkillOutput:
    """模拟 Skill 输出"""

    def __init__(self, success: bool = True, data: Any = None, error: str = None):
        self.success = success
        self.data = data or {}
        self.error = error
        self.skill_name = "mock_skill"
        self.execution_time_ms = 0


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self._measurements = {}

    def record(self, metric_name: str, value: float):
        if metric_name not in self._measurements:
            self._measurements[metric_name] = []
        self._measurements[metric_name].append(value)

    def get_stats(self, metric_name: str) -> Dict[str, float]:
        values = self._measurements.get(metric_name, [])
        if not values:
            return {}
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p50": self._percentile(values, 50),
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99)
        }

    def _percentile(self, values: list, percentile: int) -> float:
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def clear(self):
        self._measurements = {}


def create_mock_request(
    user_id: str = "test-user",
    role: str = "pilot",
    workspace_id: str = "ws-001",
    scenario_id: str = "scenario-001"
) -> Dict[str, Any]:
    """创建模拟请求"""
    return {
        "request_id": f"req-{uuid.uuid4().hex[:8]}",
        "user_id": user_id,
        "user": {
            "id": user_id,
            "role": role
        },
        "workspace_id": workspace_id,
        "scenario_id": scenario_id,
        "timestamp": time.time()
    }


def create_mock_tool_input(
    tool_name: str,
    parameters: Dict[str, Any] = None
) -> Dict[str, Any]:
    """创建模拟工具输入"""
    return {
        "tool_name": tool_name,
        "parameters": parameters or {},
        "request_id": f"req-{uuid.uuid4().hex[:8]}",
        "timestamp": time.time()
    }
