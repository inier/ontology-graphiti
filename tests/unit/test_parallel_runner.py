"""ParallelRunner + ScenarioQueue 单元测试"""

import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import (
    ScenarioQueue,
    ParallelRunner,
    MAX_PARALLEL,
)


class TestScenarioQueueBasic(unittest.TestCase):
    """ScenarioQueue 基础测试"""

    def test_initial_state(self):
        q = ScenarioQueue(max_parallel=5)
        self.assertEqual(q.queue_size, 0)
        self.assertEqual(q.running_count, 0)

    def test_enqueue_ready(self):
        q = ScenarioQueue(max_parallel=5)
        result = q.enqueue("s1", {"data": "test"})
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["position"], 0)
        self.assertEqual(q.running_count, 1)

    def test_enqueue_queued_when_full(self):
        q = ScenarioQueue(max_parallel=2)
        q.enqueue("s1", {})
        q.enqueue("s2", {})
        result = q.enqueue("s3", {})
        self.assertEqual(result["status"], "queued")
        self.assertEqual(result["position"], 1)

    def test_dequeue_empty(self):
        q = ScenarioQueue(max_parallel=5)
        result = q.dequeue()
        self.assertIsNone(result)


class TestScenarioQueueFIFO(unittest.TestCase):
    """FIFO 顺序测试"""

    def test_fifo_order(self):
        q = ScenarioQueue(max_parallel=1)
        q.enqueue("s1", {"order": 1})
        q.enqueue("s2", {"order": 2})
        q.enqueue("s3", {"order": 3})

        # 完成第一个，取出第二个
        next_item = q.complete("s1", {"result": "ok"})
        self.assertIsNotNone(next_item)
        self.assertEqual(next_item["scenario_id"], "s2")

        # 完成第二个，取出第三个
        next_item = q.complete("s2", {"result": "ok"})
        self.assertIsNotNone(next_item)
        self.assertEqual(next_item["scenario_id"], "s3")

    def test_dequeue_updates_positions(self):
        q = ScenarioQueue(max_parallel=1)
        q.enqueue("s1", {})
        q.enqueue("s2", {})
        q.enqueue("s3", {})

        # s1 is running, s2 is position 1, s3 is position 2
        self.assertEqual(q.get_position("s2"), 1)
        self.assertEqual(q.get_position("s3"), 2)

        # After s1 completes, s2 starts, s3 moves to position 1
        q.complete("s1", {})
        self.assertEqual(q.get_position("s3"), 1)


class TestScenarioQueueComplete(unittest.TestCase):
    """完成与结果测试"""

    def test_complete_stores_result(self):
        q = ScenarioQueue(max_parallel=5)
        q.enqueue("s1", {})
        q.complete("s1", {"status": "completed", "data": "test"})
        result = q.get_result("s1")
        self.assertEqual(result["status"], "completed")

    def test_complete_not_found_returns_none(self):
        q = ScenarioQueue(max_parallel=5)
        result = q.get_result("nonexistent")
        self.assertIsNone(result)

    def test_complete_decrements_running(self):
        q = ScenarioQueue(max_parallel=5)
        q.enqueue("s1", {})
        self.assertEqual(q.running_count, 1)
        q.complete("s1", {})
        self.assertEqual(q.running_count, 0)


class TestScenarioQueueStatus(unittest.TestCase):
    """队列状态测试"""

    def test_get_queue_status(self):
        q = ScenarioQueue(max_parallel=2)
        q.enqueue("s1", {})
        q.enqueue("s2", {})
        q.enqueue("s3", {})

        status = q.get_queue_status()
        self.assertEqual(status["queue_size"], 1)
        self.assertEqual(status["running_count"], 2)
        self.assertEqual(status["max_parallel"], 2)

    def test_get_position(self):
        q = ScenarioQueue(max_parallel=1)
        q.enqueue("s1", {})
        q.enqueue("s2", {})
        self.assertEqual(q.get_position("s2"), 1)

    def test_get_position_not_queued(self):
        q = ScenarioQueue(max_parallel=5)
        self.assertEqual(q.get_position("nonexistent"), 0)


class TestScenarioQueueMaxParallel(unittest.TestCase):
    """最大并行数测试"""

    def test_max_parallel_default(self):
        self.assertEqual(MAX_PARALLEL, 10)

    def test_custom_max_parallel(self):
        q = ScenarioQueue(max_parallel=3)
        self.assertEqual(q._max_parallel, 3)

    def test_queue_overflow(self):
        q = ScenarioQueue(max_parallel=2)
        results = []
        for i in range(5):
            results.append(q.enqueue(f"s{i}", {}))
        ready_count = sum(1 for r in results if r["status"] == "ready")
        queued_count = sum(1 for r in results if r["status"] == "queued")
        self.assertEqual(ready_count, 2)
        self.assertEqual(queued_count, 3)


class TestScenarioQueueCompletionEvent(unittest.TestCase):
    """完成事件测试"""

    def test_get_completion_event(self):
        q = ScenarioQueue(max_parallel=5)
        event = q.get_completion_event("s1")
        self.assertIsInstance(event, asyncio.Event)
        self.assertFalse(event.is_set())

    def test_completion_event_set_on_complete(self):
        q = ScenarioQueue(max_parallel=5)
        q.enqueue("s1", {})
        event = q.get_completion_event("s1")
        q.complete("s1", {"result": "ok"})
        self.assertTrue(event.is_set())


class TestParallelRunnerInit(unittest.TestCase):
    """ParallelRunner 初始化测试"""

    def test_singleton(self):
        # 重置单例
        ParallelRunner._instance = None
        runner1 = ParallelRunner()
        runner2 = ParallelRunner()
        self.assertIs(runner1, runner2)
        ParallelRunner._instance = None


class TestParallelRunnerGetComparison(unittest.TestCase):
    """比较结果查询测试"""

    def setUp(self):
        ParallelRunner._instance = None
        self.runner = ParallelRunner()

    def tearDown(self):
        ParallelRunner._instance = None

    def test_get_comparison_not_found(self):
        result = self.runner.get_comparison("nonexistent")
        self.assertEqual(result["status"], "error")

    def test_get_comparison_cached(self):
        self.runner._comparison_cache["run-1"] = {"status": "completed", "results": []}
        result = self.runner.get_comparison("run-1")
        self.assertEqual(result["status"], "completed")


class TestParallelRunnerGetQueueStatus(unittest.TestCase):
    """队列状态查询测试"""

    def setUp(self):
        ParallelRunner._instance = None
        self.runner = ParallelRunner()

    def tearDown(self):
        ParallelRunner._instance = None

    def test_get_queue_status(self):
        status = self.runner.get_queue_status()
        self.assertIn("queue_size", status)
        self.assertIn("running_count", status)
        self.assertIn("max_parallel", status)


class TestParallelRunnerCompareByIds(unittest.TestCase):
    """按 ID 比较测试"""

    def setUp(self):
        ParallelRunner._instance = None
        self.runner = ParallelRunner()

    def tearDown(self):
        ParallelRunner._instance = None

    def test_compare_by_ids_no_valid(self):
        result = self.runner.compare_by_ids(["nonexistent"])
        self.assertEqual(result["status"], "error")

    def test_compare_by_ids_with_cached(self):
        self.runner._comparison_cache["run-1"] = {
            "status": "completed",
            "results": [{"scenario_id": "s1", "status": "completed", "metric_changes": []}],
        }
        result = self.runner.compare_by_ids(["run-1"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["total_results"], 1)


if __name__ == "__main__":
    unittest.main()
