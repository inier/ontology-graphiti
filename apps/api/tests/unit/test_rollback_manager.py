"""ConstructionRollbackManager / BatchDeleteUndo 单元测试。

守护的核心契约：回滚失败必须显式，不得静默假成功。

此前 BatchDeleteUndo.undo 存在两层幻影——graph_service 中没有 get_graph_manager
工厂函数（GraphManager 通过 __new__ 实现单例），GraphManager 也没有 delete_by_batch；
`if hasattr(gm,'delete_by_batch') else 0` 恒得 0 却仍返回 status="deleted"。
上层 rollback_pipeline / rollback_batch 又只取 deleted_count 不校验 status，
无条件把 record.status 置为 COMPLETED。结果是：本体构建回滚能力实际为零，
而系统报告回滚成功、影响 0 个实体。
"""

import pytest
from unittest.mock import AsyncMock

from odap.biz.core.ontology.construction.rollback.rollback_manager import (
    BatchDeleteUndo,
    ConstructionRollbackManager,
    RollbackLevel,
    RollbackStatus,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """ConstructionRollbackManager 是 __new__ 单例，逐个用例隔离。"""
    ConstructionRollbackManager._instance = None
    yield
    ConstructionRollbackManager._instance = None


@pytest.fixture
def manager():
    """隔离外部依赖（pipeline 存储查询与审计写入），只考察 status 传播。"""
    mgr = ConstructionRollbackManager()
    mgr._get_completed_steps = AsyncMock(return_value=[])
    mgr._record_rollback_audit = AsyncMock()
    mgr._record_step_rollback = AsyncMock()
    return mgr


class TestBatchDeleteUndo:
    @pytest.mark.asyncio
    async def test_reports_failed_instead_of_fake_deleted(self):
        """不得再用 hasattr 兜成 0 并谎报 status='deleted'。"""
        result = await BatchDeleteUndo().undo({"batch_id": "b1"})
        assert result["status"] == "failed"
        assert result["deleted_count"] == 0
        assert "delete_by_batch" in result["error"]

    @pytest.mark.asyncio
    async def test_error_explains_pending_decision(self):
        """失败原因须说明是能力缺口而非运行时故障，便于上层区分。"""
        result = await BatchDeleteUndo().undo({"batch_id": "b1"})
        assert "未实现" in result["error"]


class TestRollbackBatchStatusPropagation:
    @pytest.mark.asyncio
    async def test_fails_when_undo_fails(self, manager):
        """批次回滚不得在 undo 失败时仍记为 COMPLETED。"""
        record = await manager.rollback_batch("b1", reason="test")

        assert record.status == RollbackStatus.FAILED
        assert record.level == RollbackLevel.BATCH
        assert record.entities_affected == 0
        assert "graph_write" not in record.steps_undone
        assert "图谱回滚失败" in record.error

    @pytest.mark.asyncio
    async def test_audit_still_recorded_on_failure(self, manager):
        """失败的回滚同样要落审计，否则运维无从得知回滚未生效。"""
        await manager.rollback_batch("b1")
        manager._record_rollback_audit.assert_awaited_once()


class TestRollbackPipelineStatusPropagation:
    @pytest.mark.asyncio
    async def test_fails_when_graph_write_undo_fails(self, manager):
        manager._get_completed_steps = AsyncMock(return_value=[
            {"step_type": "graph_write", "batch_id": "b1"},
        ])

        record = await manager.rollback_pipeline("run-1")

        assert record.status == RollbackStatus.FAILED
        assert "graph_write" not in record.steps_undone
        assert "b1" in record.error

    @pytest.mark.asyncio
    async def test_completes_when_no_graph_write_step(self, manager):
        """无 graph_write 步骤时回滚应正常完成——确认失败只源自批次删除能力缺口。"""
        manager._get_completed_steps = AsyncMock(return_value=[
            {"step_type": "review"},
            {"step_type": "consistency"},
        ])

        record = await manager.rollback_pipeline("run-2")

        assert record.status == RollbackStatus.COMPLETED
        assert record.error is None
        assert record.steps_undone == ["consistency", "review"]

    @pytest.mark.asyncio
    async def test_snapshot_step_still_undone(self, manager):
        """快照回滚不依赖批次删除能力，应保持可用。"""
        manager._get_completed_steps = AsyncMock(return_value=[
            {"step_type": "snapshot", "snapshot_id": "s1"},
        ])

        record = await manager.rollback_pipeline("run-3")

        assert record.status == RollbackStatus.COMPLETED
        assert "snapshot" in record.steps_undone
