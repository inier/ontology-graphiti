"""
任务管理技能模块单元测试

测试 odap/tools/task_management/task_management.py 中的所有函数：
- reserve_task: 有效/空目标列表
- get_reserved_tasks: 获取所有预留任务
- clear_reserved_tasks: 清除所有预留任务
- get_task_by_id: 存在/不存在的任务
- cancel_task: 存在/不存在的任务
- query_tasks_by_status: 按状态查询任务

Mock 策略：GraphManager 需 mock。

AGENTS.md Rule 9: 新增模块必须同步新增测试文件。
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# TestReserveTask
# ---------------------------------------------------------------------------


class TestReserveTask:
    """测试 reserve_task 函数"""

    @patch("odap.tools.task_management.task_management.manager")
    def test_valid_targets(self, mock_manager):
        """有效目标列表时任务预留成功"""
        mock_manager.reserve_task.return_value = "task-001"

        from odap.tools.task_management.task_management import reserve_task

        result = reserve_task(
            task_name="侦察任务",
            task_type="reconnaissance",
            targets=["target-1", "target-2"],
            priority="high",
            user_role="commander",
        )

        assert result["status"] == "success"
        assert result["task_id"] == "task-001"
        assert "侦察任务" in result["message"]
        assert result["task_data"]["name"] == "侦察任务"
        assert result["task_data"]["type"] == "reconnaissance"
        assert result["task_data"]["priority"] == "high"
        assert result["task_data"]["targets"] == ["target-1", "target-2"]
        mock_manager.reserve_task.assert_called_once()

    @patch("odap.tools.task_management.task_management.manager")
    def test_empty_targets_returns_error(self, mock_manager):
        """空目标列表时返回错误"""
        from odap.tools.task_management.task_management import reserve_task

        result = reserve_task(
            task_name="空任务",
            task_type="reconnaissance",
            targets=[],
        )

        assert result["status"] == "error"
        assert "不能为空" in result["message"]
        mock_manager.reserve_task.assert_not_called()

    @patch("odap.tools.task_management.task_management.manager")
    def test_none_targets_returns_error(self, mock_manager):
        """None 目标列表时返回错误"""
        from odap.tools.task_management.task_management import reserve_task

        result = reserve_task(
            task_name="空任务",
            task_type="reconnaissance",
            targets=None,
        )

        assert result["status"] == "error"
        assert "不能为空" in result["message"]

    @patch("odap.tools.task_management.task_management.manager")
    def test_default_priority(self, mock_manager):
        """默认优先级为 medium"""
        mock_manager.reserve_task.return_value = "task-002"

        from odap.tools.task_management.task_management import reserve_task

        result = reserve_task(
            task_name="普通任务",
            task_type="patrol",
            targets=["target-1"],
        )

        assert result["task_data"]["priority"] == "medium"

    @patch("odap.tools.task_management.task_management.manager")
    def test_task_data_has_created_at(self, mock_manager):
        """任务数据包含创建时间"""
        mock_manager.reserve_task.return_value = "task-003"

        from odap.tools.task_management.task_management import reserve_task

        result = reserve_task(
            task_name="测试任务",
            task_type="attack",
            targets=["target-1"],
        )

        assert "created_at" in result["task_data"]
        assert result["task_data"]["created_at"]  # 非空


# ---------------------------------------------------------------------------
# TestGetReservedTasks
# ---------------------------------------------------------------------------


class TestGetReservedTasks:
    """测试 get_reserved_tasks 函数"""

    @patch("odap.tools.task_management.task_management.manager")
    def test_returns_tasks(self, mock_manager):
        """返回所有预留任务"""
        mock_manager.get_reserved_tasks.return_value = [
            {"id": "task-001", "name": "任务1"},
            {"id": "task-002", "name": "任务2"},
        ]

        from odap.tools.task_management.task_management import get_reserved_tasks

        result = get_reserved_tasks()

        assert result["status"] == "success"
        assert result["total"] == 2
        assert len(result["tasks"]) == 2

    @patch("odap.tools.task_management.task_management.manager")
    def test_empty_tasks(self, mock_manager):
        """无预留任务时返回空列表"""
        mock_manager.get_reserved_tasks.return_value = []

        from odap.tools.task_management.task_management import get_reserved_tasks

        result = get_reserved_tasks()

        assert result["status"] == "success"
        assert result["total"] == 0
        assert result["tasks"] == []


# ---------------------------------------------------------------------------
# TestClearReservedTasks
# ---------------------------------------------------------------------------


class TestClearReservedTasks:
    """测试 clear_reserved_tasks 函数"""

    @patch("odap.tools.task_management.task_management.manager")
    def test_clear_success(self, mock_manager):
        """清除所有预留任务"""
        from odap.tools.task_management.task_management import clear_reserved_tasks

        result = clear_reserved_tasks()

        assert result["status"] == "success"
        assert "已清除" in result["message"]
        mock_manager.clear_reserved_tasks.assert_called_once()


# ---------------------------------------------------------------------------
# TestGetTaskById
# ---------------------------------------------------------------------------


class TestGetTaskById:
    """测试 get_task_by_id 函数"""

    @patch("odap.tools.task_management.task_management.manager")
    def test_existing_task(self, mock_manager):
        """存在的任务返回成功"""
        mock_manager.get_reserved_tasks.return_value = [
            {"id": "task-001", "name": "任务1", "status": "pending"},
            {"id": "task-002", "name": "任务2", "status": "completed"},
        ]

        from odap.tools.task_management.task_management import get_task_by_id

        result = get_task_by_id("task-001")

        assert result["status"] == "success"
        assert result["task"]["id"] == "task-001"
        assert result["task"]["name"] == "任务1"

    @patch("odap.tools.task_management.task_management.manager")
    def test_nonexistent_task(self, mock_manager):
        """不存在的任务返回错误"""
        mock_manager.get_reserved_tasks.return_value = [
            {"id": "task-001", "name": "任务1"},
        ]

        from odap.tools.task_management.task_management import get_task_by_id

        result = get_task_by_id("nonexistent")

        assert result["status"] == "error"
        assert "不存在" in result["message"]


# ---------------------------------------------------------------------------
# TestCancelTask
# ---------------------------------------------------------------------------


class TestCancelTask:
    """测试 cancel_task 函数"""

    @patch("odap.tools.task_management.task_management.manager")
    def test_existing_task(self, mock_manager):
        """取消存在的任务"""
        tasks = [
            {"id": "task-001", "name": "任务1"},
            {"id": "task-002", "name": "任务2"},
        ]
        mock_manager.get_reserved_tasks.return_value = tasks

        from odap.tools.task_management.task_management import cancel_task

        result = cancel_task("task-001")

        assert result["status"] == "success"
        assert "已取消" in result["message"]

    @patch("odap.tools.task_management.task_management.manager")
    def test_nonexistent_task(self, mock_manager):
        """取消不存在的任务返回错误"""
        mock_manager.get_reserved_tasks.return_value = [
            {"id": "task-001", "name": "任务1"},
        ]

        from odap.tools.task_management.task_management import cancel_task

        result = cancel_task("nonexistent")

        assert result["status"] == "error"
        assert "不存在" in result["message"]


# ---------------------------------------------------------------------------
# TestQueryTasksByStatus
# ---------------------------------------------------------------------------


class TestQueryTasksByStatus:
    """测试 query_tasks_by_status 函数"""

    @patch("odap.tools.task_management.task_management.manager")
    def test_filter_by_status(self, mock_manager):
        """按状态过滤任务"""
        mock_manager.get_reserved_tasks.return_value = [
            {"id": "task-001", "name": "任务1", "status": "pending"},
            {"id": "task-002", "name": "任务2", "status": "completed"},
            {"id": "task-003", "name": "任务3", "status": "pending"},
        ]

        from odap.tools.task_management.task_management import query_tasks_by_status

        result = query_tasks_by_status("pending")

        assert result["status"] == "success"
        assert result["total"] == 2
        assert all(t["status"] == "pending" for t in result["tasks"])

    @patch("odap.tools.task_management.task_management.manager")
    def test_no_matching_status(self, mock_manager):
        """无匹配状态时返回空列表"""
        mock_manager.get_reserved_tasks.return_value = [
            {"id": "task-001", "name": "任务1", "status": "pending"},
        ]

        from odap.tools.task_management.task_management import query_tasks_by_status

        result = query_tasks_by_status("completed")

        assert result["status"] == "success"
        assert result["total"] == 0
        assert result["tasks"] == []

    @patch("odap.tools.task_management.task_management.manager")
    def test_empty_tasks(self, mock_manager):
        """无任务时返回空列表"""
        mock_manager.get_reserved_tasks.return_value = []

        from odap.tools.task_management.task_management import query_tasks_by_status

        result = query_tasks_by_status("pending")

        assert result["status"] == "success"
        assert result["total"] == 0
