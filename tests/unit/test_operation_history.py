"""操作历史与撤销/重做服务测试"""

import pytest
import os
import json
from datetime import datetime


class TestOperationHistoryService:
    """操作历史服务测试"""

    def _make_service(self, tmp_path):
        from odap.biz.platform.undo.services.operation_history_service import OperationHistoryService
        db_path = str(tmp_path / "test_operation_history.db")
        return OperationHistoryService(db_path=db_path)

    def test_init_db(self, tmp_path):
        """测试数据库初始化"""
        svc = self._make_service(tmp_path)
        assert os.path.exists(svc.db_path)

    def test_record_operation(self, tmp_path):
        """测试记录操作"""
        svc = self._make_service(tmp_path)
        result = svc.record_operation(
            workspace_id="ws-1",
            action_type="create",
            resource_type="workspace",
            resource_id="res-1",
            before_state=None,
            after_state={"name": "test", "status": "active"},
            user_id="user-1",
        )
        assert result["operation_id"]
        assert result["workspace_id"] == "ws-1"
        assert result["action_type"] == "create"
        assert result["resource_type"] == "workspace"

    def test_record_operation_with_states(self, tmp_path):
        """测试记录带前后状态的操作"""
        svc = self._make_service(tmp_path)
        result = svc.record_operation(
            workspace_id="ws-1",
            action_type="update",
            resource_type="scenario",
            resource_id="sc-1",
            before_state={"name": "old", "status": "draft"},
            after_state={"name": "new", "status": "active"},
        )
        assert result["operation_id"]

        # 验证可以读取
        op = svc.get_operation(result["operation_id"])
        assert op is not None
        assert op["before_state"]["name"] == "old"
        assert op["after_state"]["name"] == "new"

    def test_get_history(self, tmp_path):
        """测试获取操作历史"""
        svc = self._make_service(tmp_path)
        for i in range(5):
            svc.record_operation(
                workspace_id="ws-1",
                action_type="create",
                resource_type="entity",
                resource_id=f"ent-{i}",
            )

        result = svc.get_history("ws-1", page=1, page_size=3)
        assert result["total"] == 5
        assert len(result["operations"]) == 3
        assert result["page"] == 1

    def test_get_history_pagination(self, tmp_path):
        """测试分页"""
        svc = self._make_service(tmp_path)
        for i in range(10):
            svc.record_operation(
                workspace_id="ws-1",
                action_type="update",
                resource_type="entity",
                resource_id=f"ent-{i}",
            )

        page1 = svc.get_history("ws-1", page=1, page_size=5)
        page2 = svc.get_history("ws-1", page=2, page_size=5)
        assert len(page1["operations"]) == 5
        assert len(page2["operations"]) == 5
        assert page1["operations"][0]["operation_id"] != page2["operations"][0]["operation_id"]

    def test_get_history_workspace_isolation(self, tmp_path):
        """测试工作空间隔离"""
        svc = self._make_service(tmp_path)
        svc.record_operation(workspace_id="ws-1", action_type="create", resource_type="entity", resource_id="e1")
        svc.record_operation(workspace_id="ws-2", action_type="create", resource_type="entity", resource_id="e2")

        result = svc.get_history("ws-1")
        assert result["total"] == 1
        assert result["operations"][0]["resource_id"] == "e1"

    def test_get_operation_not_found(self, tmp_path):
        """测试获取不存在的操作"""
        svc = self._make_service(tmp_path)
        result = svc.get_operation("nonexistent")
        assert result is None

    def test_mark_undone(self, tmp_path):
        """测试标记为已撤销"""
        svc = self._make_service(tmp_path)
        result = svc.record_operation(
            workspace_id="ws-1",
            action_type="create",
            resource_type="entity",
            resource_id="e1",
        )
        op_id = result["operation_id"]

        # 验证初始状态
        op = svc.get_operation(op_id)
        assert op["undone"] is False

        # 标记为已撤销
        success = svc.mark_undone(op_id)
        assert success is True

        op = svc.get_operation(op_id)
        assert op["undone"] is True

    def test_mark_undone_not_found(self, tmp_path):
        """测试标记不存在的操作"""
        svc = self._make_service(tmp_path)
        success = svc.mark_undone("nonexistent")
        assert success is False

    def test_mark_redone(self, tmp_path):
        """测试标记为已重做"""
        svc = self._make_service(tmp_path)
        result = svc.record_operation(
            workspace_id="ws-1",
            action_type="create",
            resource_type="entity",
            resource_id="e1",
        )
        op_id = result["operation_id"]

        svc.mark_undone(op_id)
        success = svc.mark_redone(op_id)
        assert success is True

        op = svc.get_operation(op_id)
        assert op["undone"] is False

    def test_get_undoable_operations(self, tmp_path):
        """测试获取可撤销操作"""
        svc = self._make_service(tmp_path)
        r1 = svc.record_operation(workspace_id="ws-1", action_type="create", resource_type="entity", resource_id="e1")
        svc.record_operation(workspace_id="ws-1", action_type="create", resource_type="entity", resource_id="e2")

        # 标记第一个为已撤销
        svc.mark_undone(r1["operation_id"])

        undoable = svc.get_undoable_operations("ws-1")
        assert len(undoable) == 1
        assert undoable[0]["resource_id"] == "e2"

    def test_get_redoable_operations(self, tmp_path):
        """测试获取可重做操作"""
        svc = self._make_service(tmp_path)
        r1 = svc.record_operation(workspace_id="ws-1", action_type="create", resource_type="entity", resource_id="e1")
        svc.record_operation(workspace_id="ws-1", action_type="create", resource_type="entity", resource_id="e2")

        svc.mark_undone(r1["operation_id"])

        redoable = svc.get_redoable_operations("ws-1")
        assert len(redoable) == 1
        assert redoable[0]["resource_id"] == "e1"

    def test_cleanup_old_records(self, tmp_path):
        """测试清理过期记录"""
        svc = self._make_service(tmp_path)
        svc.record_operation(workspace_id="ws-1", action_type="create", resource_type="entity", resource_id="e1")

        # 清理0天前的记录（即清理所有）
        deleted = svc.cleanup_old_records(days=0)
        assert deleted >= 1

        result = svc.get_history("ws-1")
        assert result["total"] == 0

    def test_cleanup_preserves_recent(self, tmp_path):
        """测试清理保留近期记录"""
        svc = self._make_service(tmp_path)
        svc.record_operation(workspace_id="ws-1", action_type="create", resource_type="entity", resource_id="e1")

        # 清理365天前的记录（不应删除任何记录）
        deleted = svc.cleanup_old_records(days=365)
        assert deleted == 0

        result = svc.get_history("ws-1")
        assert result["total"] == 1


class TestUndoService:
    """撤销/重做服务测试"""

    def _make_service(self, tmp_path):
        from odap.biz.platform.undo.services.operation_history_service import OperationHistoryService
        from odap.biz.platform.undo.services.undo_service import UndoService
        db_path = str(tmp_path / "test_undo.db")
        history = OperationHistoryService(db_path=db_path)
        return UndoService(history_service=history)

    def test_undo_not_found(self, tmp_path):
        """测试撤销不存在的操作"""
        svc = self._make_service(tmp_path)
        result = svc.undo("nonexistent")
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_undo_no_before_state(self, tmp_path):
        """测试撤销没有 before_state 的操作"""
        svc = self._make_service(tmp_path)
        record = svc.history.record_operation(
            workspace_id="ws-1",
            action_type="create",
            resource_type="entity",
            resource_id="e1",
            before_state=None,
            after_state={"name": "test"},
        )
        result = svc.undo(record["operation_id"])
        assert result["status"] == "error"
        assert "no before_state" in result["message"]

    def test_undo_already_undone(self, tmp_path):
        """测试撤销已撤销的操作"""
        svc = self._make_service(tmp_path)
        record = svc.history.record_operation(
            workspace_id="ws-1",
            action_type="update",
            resource_type="entity",
            resource_id="e1",
            before_state={"name": "old"},
            after_state={"name": "new"},
        )
        svc.undo(record["operation_id"])
        result = svc.undo(record["operation_id"])
        assert result["status"] == "error"
        assert "already undone" in result["message"]

    def test_redo_not_undone(self, tmp_path):
        """测试重做未撤销的操作"""
        svc = self._make_service(tmp_path)
        record = svc.history.record_operation(
            workspace_id="ws-1",
            action_type="update",
            resource_type="entity",
            resource_id="e1",
            before_state={"name": "old"},
            after_state={"name": "new"},
        )
        result = svc.redo(record["operation_id"])
        assert result["status"] == "error"
        assert "not undone" in result["message"]

    def test_get_undoable_operations(self, tmp_path):
        """测试获取可撤销操作"""
        svc = self._make_service(tmp_path)
        svc.history.record_operation(
            workspace_id="ws-1",
            action_type="create",
            resource_type="entity",
            resource_id="e1",
            before_state={},
            after_state={"name": "test"},
        )
        result = svc.get_undoable_operations("ws-1")
        assert result["status"] == "success"
        assert result["count"] == 1

    def test_get_redoable_operations(self, tmp_path):
        """测试获取可重做操作"""
        svc = self._make_service(tmp_path)
        record = svc.history.record_operation(
            workspace_id="ws-1",
            action_type="create",
            resource_type="entity",
            resource_id="e1",
            before_state={},
            after_state={"name": "test"},
        )
        svc.undo(record["operation_id"])
        result = svc.get_redoable_operations("ws-1")
        assert result["status"] == "success"
        assert result["count"] == 1
