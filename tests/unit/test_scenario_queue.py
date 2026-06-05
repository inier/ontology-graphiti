"""ScenarioQueue 单元测试

测试推演方案排队机制的核心功能。
"""

import asyncio
import pytest


class TestScenarioQueueEnqueue:
    """测试 ScenarioQueue.enqueue 方法"""

    def test_first_scenario_ready(self):
        """第一个方案应直接就绪"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=2)
        result = queue.enqueue("scenario_1", {"name": "test"})
        assert result["status"] == "ready"
        assert result["position"] == 0

    def test_within_max_parallel_ready(self):
        """在 MAX_PARALLEL 内的方案应直接就绪"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=3)
        r1 = queue.enqueue("s1", {})
        r2 = queue.enqueue("s2", {})
        r3 = queue.enqueue("s3", {})
        assert r1["status"] == "ready"
        assert r2["status"] == "ready"
        assert r3["status"] == "ready"

    def test_exceed_max_parallel_queued(self):
        """超过 MAX_PARALLEL 的方案应排队"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=2)
        queue.enqueue("s1", {})
        queue.enqueue("s2", {})
        r3 = queue.enqueue("s3", {})
        assert r3["status"] == "queued"
        assert r3["position"] == 1

    def test_queued_position_increments(self):
        """排队位置应递增"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=1)
        queue.enqueue("s1", {})
        r2 = queue.enqueue("s2", {})
        r3 = queue.enqueue("s3", {})
        assert r2["status"] == "queued"
        assert r2["position"] == 1
        assert r3["status"] == "queued"
        assert r3["position"] == 2

    def test_queued_has_estimated_wait(self):
        """排队方案应有预计等待时间"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=1)
        queue.enqueue("s1", {})
        r2 = queue.enqueue("s2", {})
        assert "estimated_wait" in r2
        assert "s" in r2["estimated_wait"]


class TestScenarioQueueDequeue:
    """测试 ScenarioQueue.dequeue 方法"""

    def test_dequeue_from_empty_returns_none(self):
        """空队列出队应返回 None"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=2)
        result = queue.dequeue()
        assert result is None

    def test_dequeue_returns_first_item(self):
        """出队应返回 FIFO 顺序的第一个"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=1)
        queue.enqueue("s1", {})
        queue.enqueue("s2", {"name": "second"})
        queue.enqueue("s3", {"name": "third"})

        # 先完成 s1 让出位置
        queue.complete("s1", {"status": "completed"})

        # dequeue 应该已经被 complete 触发
        # 手动测试 dequeue
        item = queue.dequeue()
        assert item is not None
        assert item["scenario_id"] == "s3"

    def test_dequeue_updates_positions(self):
        """出队后应更新剩余方案的位置"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=1)
        queue.enqueue("s1", {})
        queue.enqueue("s2", {})
        queue.enqueue("s3", {})
        queue.enqueue("s4", {})

        # s1 在运行，s2 位置1, s3 位置2, s4 位置3
        assert queue.get_position("s2") == 1
        assert queue.get_position("s3") == 2
        assert queue.get_position("s4") == 3

        # 完成 s1，触发 dequeue s2
        queue.complete("s1", {})

        # s3 应该变成位置1, s4 位置2
        assert queue.get_position("s3") == 1
        assert queue.get_position("s4") == 2


class TestScenarioQueueComplete:
    """测试 ScenarioQueue.complete 方法"""

    def test_complete_reduces_running_count(self):
        """完成后运行数应减少"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=2)
        queue.enqueue("s1", {})
        queue.enqueue("s2", {})
        assert queue.running_count == 2

        queue.complete("s1", {"status": "completed"})
        assert queue.running_count == 1

    def test_complete_stores_result(self):
        """完成后应存储结果"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=2)
        queue.enqueue("s1", {})
        result = {"status": "completed", "data": "test"}
        queue.complete("s1", result)

        stored = queue.get_result("s1")
        assert stored is not None
        assert stored["status"] == "completed"
        assert stored["data"] == "test"

    def test_complete_auto_starts_next(self):
        """完成后应自动启动队列中的下一个方案"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=1)
        queue.enqueue("s1", {})
        queue.enqueue("s2", {"name": "second"})

        next_item = queue.complete("s1", {"status": "completed"})
        assert next_item is not None
        assert next_item["scenario_id"] == "s2"

    def test_complete_no_next_returns_none(self):
        """队列为空时完成应返回 None"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=2)
        queue.enqueue("s1", {})

        next_item = queue.complete("s1", {"status": "completed"})
        assert next_item is None


class TestScenarioQueueGetQueueStatus:
    """测试 ScenarioQueue.get_queue_status 方法"""

    def test_empty_queue_status(self):
        """空队列状态"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=10)
        status = queue.get_queue_status()
        assert status["queue_size"] == 0
        assert status["running_count"] == 0
        assert status["max_parallel"] == 10

    def test_status_with_running_and_queued(self):
        """有运行和排队方案的状态"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=2)
        queue.enqueue("s1", {})
        queue.enqueue("s2", {})
        queue.enqueue("s3", {})
        queue.enqueue("s4", {})

        status = queue.get_queue_status()
        assert status["running_count"] == 2
        assert status["queue_size"] == 2
        assert len(status["queued_scenarios"]) == 2


class TestScenarioQueueProperties:
    """测试 ScenarioQueue 属性"""

    def test_queue_size_property(self):
        """queue_size 属性"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=1)
        assert queue.queue_size == 0
        queue.enqueue("s1", {})
        queue.enqueue("s2", {})
        queue.enqueue("s3", {})
        assert queue.queue_size == 2  # s1 在运行，s2 和 s3 在队列

    def test_running_count_property(self):
        """running_count 属性"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=3)
        assert queue.running_count == 0
        queue.enqueue("s1", {})
        assert queue.running_count == 1
        queue.enqueue("s2", {})
        assert queue.running_count == 2


class TestScenarioQueueCompletionEvent:
    """测试 ScenarioQueue 完成事件"""

    def test_get_completion_event(self):
        """应能获取完成事件"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=1)
        event = queue.get_completion_event("s1")
        assert isinstance(event, asyncio.Event)
        assert not event.is_set()

    def test_complete_sets_event(self):
        """完成时应设置事件"""
        from odap.biz.simulation.simulation_sandbox.impl.parallel_runner import ScenarioQueue

        queue = ScenarioQueue(max_parallel=1)
        queue.enqueue("s1", {})
        event = queue.get_completion_event("s1")
        assert not event.is_set()

        queue.complete("s1", {"status": "completed"})
        assert event.is_set()
