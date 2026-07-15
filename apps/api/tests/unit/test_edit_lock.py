"""EditLockService 单元测试

覆盖：CRUD 全流程、超时释放、并发访问、心跳刷新
"""

import os
import time
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch


# 延迟导入避免模块级依赖问题
@pytest.fixture
def edit_lock_service(tmp_path):
    """创建使用临时数据库的 EditLockService"""
    from odap.biz.core.ontology.design.services.edit_lock_service import EditLockService
    db_path = str(tmp_path / "edit_locks_test.db")
    return EditLockService(db_path=db_path)


class TestEditLockServiceAcquire:
    """测试锁获取"""

    def test_acquire_lock_success(self, edit_lock_service):
        """成功获取锁"""
        result = edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        assert result["status"] == "ok"
        assert result["ontology_id"] == "ont-1"
        assert result["user_id"] == "user-a"
        assert result["session_id"] == "session-1"
        assert result["acquired_at"] is not None
        assert result["last_heartbeat"] is not None

    def test_acquire_lock_same_session_reacquire(self, edit_lock_service):
        """同一会话重新获取锁应刷新心跳"""
        r1 = edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        r2 = edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        assert r2["status"] == "ok"
        assert r2["session_id"] == "session-1"

    def test_acquire_lock_conflict_other_user(self, edit_lock_service):
        """被其他用户持有时获取锁失败"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        result = edit_lock_service.acquire_lock("ont-1", "user-b", "session-2")
        assert result["status"] == "error"
        assert result["locked_by"] == "user-a"

    def test_acquire_lock_conflict_other_session_same_user(self, edit_lock_service):
        """同一用户不同会话也视为冲突"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        result = edit_lock_service.acquire_lock("ont-1", "user-a", "session-2")
        assert result["status"] == "error"
        assert result["locked_by"] == "user-a"


class TestEditLockServiceRelease:
    """测试锁释放"""

    def test_release_lock_success(self, edit_lock_service):
        """成功释放锁"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        result = edit_lock_service.release_lock("ont-1", "session-1")
        assert result["status"] == "ok"

    def test_release_lock_not_exists(self, edit_lock_service):
        """释放不存在的锁返回 ok"""
        result = edit_lock_service.release_lock("ont-nonexist", "session-1")
        assert result["status"] == "ok"

    def test_release_lock_wrong_session(self, edit_lock_service):
        """其他会话无法释放锁"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        result = edit_lock_service.release_lock("ont-1", "session-2")
        assert result["status"] == "error"
        assert "不属于当前会话" in result["message"]

    def test_release_lock_then_reacquire(self, edit_lock_service):
        """释放后其他用户可以获取锁"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        edit_lock_service.release_lock("ont-1", "session-1")
        result = edit_lock_service.acquire_lock("ont-1", "user-b", "session-2")
        assert result["status"] == "ok"
        assert result["user_id"] == "user-b"


class TestEditLockServiceRefresh:
    """测试锁心跳刷新"""

    def test_refresh_lock_success(self, edit_lock_service):
        """成功刷新锁心跳"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        result = edit_lock_service.refresh_lock("ont-1", "session-1")
        assert result["status"] == "ok"
        assert result["last_heartbeat"] is not None

    def test_refresh_lock_not_exists(self, edit_lock_service):
        """刷新不存在的锁返回错误"""
        result = edit_lock_service.refresh_lock("ont-nonexist", "session-1")
        assert result["status"] == "error"
        assert "不存在" in result["message"]

    def test_refresh_lock_wrong_session(self, edit_lock_service):
        """其他会话无法刷新锁"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        result = edit_lock_service.refresh_lock("ont-1", "session-2")
        assert result["status"] == "error"
        assert "不属于当前会话" in result["message"]


class TestEditLockServiceGetStatus:
    """测试锁状态查询"""

    def test_get_lock_status_locked(self, edit_lock_service):
        """查询已锁定的本体"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        status = edit_lock_service.get_lock_status("ont-1")
        assert status is not None
        assert status["user_id"] == "user-a"
        assert status["session_id"] == "session-1"

    def test_get_lock_status_unlocked(self, edit_lock_service):
        """查询未锁定的本体"""
        status = edit_lock_service.get_lock_status("ont-nonexist")
        assert status is None

    def test_get_lock_status_after_release(self, edit_lock_service):
        """释放后查询返回 None"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        edit_lock_service.release_lock("ont-1", "session-1")
        status = edit_lock_service.get_lock_status("ont-1")
        assert status is None


class TestEditLockServiceTimeout:
    """测试锁超时自动释放"""

    def test_expired_lock_auto_released(self, edit_lock_service):
        """超时锁在 get_lock_status 时自动清理"""
        # 获取锁
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")

        # 手动修改 last_heartbeat 为 60 秒前（超过 30 秒超时）
        import sqlite3
        conn = sqlite3.connect(edit_lock_service.db_path)
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        conn.execute(
            "UPDATE edit_locks SET last_heartbeat = ? WHERE ontology_id = ?",
            (old_time, "ont-1"),
        )
        conn.commit()
        conn.close()

        # 查询状态应返回 None（已超时清理）
        status = edit_lock_service.get_lock_status("ont-1")
        assert status is None

    def test_expired_lock_can_be_acquired(self, edit_lock_service):
        """超时锁被清理后其他用户可以获取"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")

        # 手动让锁超时
        import sqlite3
        conn = sqlite3.connect(edit_lock_service.db_path)
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        conn.execute(
            "UPDATE edit_locks SET last_heartbeat = ? WHERE ontology_id = ?",
            (old_time, "ont-1"),
        )
        conn.commit()
        conn.close()

        # 其他用户可以获取锁
        result = edit_lock_service.acquire_lock("ont-1", "user-b", "session-2")
        assert result["status"] == "ok"
        assert result["user_id"] == "user-b"


class TestEditLockServiceForceRelease:
    """测试强制释放锁"""

    def test_force_release_lock(self, edit_lock_service):
        """强制释放锁"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        result = edit_lock_service.force_release_lock("ont-1")
        assert result["status"] == "ok"
        status = edit_lock_service.get_lock_status("ont-1")
        assert status is None

    def test_force_release_nonexistent(self, edit_lock_service):
        """强制释放不存在的锁也返回 ok"""
        result = edit_lock_service.force_release_lock("ont-nonexist")
        assert result["status"] == "ok"


class TestEditLockServiceConcurrent:
    """测试并发访问场景"""

    def test_multiple_ontologies_independent_locks(self, edit_lock_service):
        """不同本体的锁互不影响"""
        r1 = edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        r2 = edit_lock_service.acquire_lock("ont-2", "user-a", "session-1")
        assert r1["status"] == "ok"
        assert r2["status"] == "ok"

        # 释放 ont-1 不影响 ont-2
        edit_lock_service.release_lock("ont-1", "session-1")
        assert edit_lock_service.get_lock_status("ont-2") is not None
        assert edit_lock_service.get_lock_status("ont-1") is None

    def test_lock_release_then_other_user_acquires(self, edit_lock_service):
        """锁释放后其他用户可以立即获取"""
        edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        edit_lock_service.release_lock("ont-1", "session-1")

        # user-b 获取锁
        result = edit_lock_service.acquire_lock("ont-1", "user-b", "session-2")
        assert result["status"] == "ok"

        # user-a 无法再获取
        result2 = edit_lock_service.acquire_lock("ont-1", "user-a", "session-1")
        assert result2["status"] == "error"
        assert result2["locked_by"] == "user-b"
