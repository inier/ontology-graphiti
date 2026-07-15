"""SQLiteCollectionStorage 单元测试

使用 tmp_path 真实 DB，不使用 MagicMock。
"""

import pytest
from datetime import datetime

from odap.biz.data.web_crawl.models.collection_task import (
    CollectionTask,
    CollectionTaskType,
    CollectionTaskStatus,
)
from odap.biz.data.web_crawl.storage.sqlite_collection_storage import SQLiteCollectionStorage


@pytest.fixture
def storage(tmp_path):
    """创建临时数据库存储"""
    db_path = str(tmp_path / "test_collection.db")
    return SQLiteCollectionStorage(db_path=db_path)


def _make_task(**overrides) -> CollectionTask:
    """工厂函数：创建测试用 CollectionTask"""
    defaults = {
        "task_type": CollectionTaskType.SEARCH,
        "target": "test query",
        "status": CollectionTaskStatus.PENDING,
        "workspace_id": "ws-001",
    }
    defaults.update(overrides)
    return CollectionTask(**defaults)


class TestSQLiteCollectionStorageCRUD:
    """CRUD 全流程测试"""

    def test_save_and_get(self, storage):
        """保存后可以获取"""
        task = _make_task()
        saved = storage.save(task)

        retrieved = storage.get(saved.id)
        assert retrieved is not None
        assert retrieved.id == saved.id
        assert retrieved.task_type == CollectionTaskType.SEARCH
        assert retrieved.target == "test query"
        assert retrieved.status == CollectionTaskStatus.PENDING

    def test_get_not_exist_returns_none(self, storage):
        """获取不存在的任务返回 None"""
        result = storage.get("nonexistent-id")
        assert result is None

    def test_save_upsert(self, storage):
        """重复保存执行 upsert"""
        task = _make_task()
        storage.save(task)

        # 更新状态
        task.status = CollectionTaskStatus.RUNNING
        storage.save(task)

        retrieved = storage.get(task.id)
        assert retrieved.status == CollectionTaskStatus.RUNNING

    def test_delete_existing(self, storage):
        """删除已存在的任务"""
        task = _make_task()
        storage.save(task)

        result = storage.delete(task.id)
        assert result is True
        assert storage.get(task.id) is None

    def test_delete_not_exist_returns_false(self, storage):
        """删除不存在的任务返回 False"""
        result = storage.delete("nonexistent-id")
        assert result is False


class TestSQLiteCollectionStorageList:
    """列表和过滤测试"""

    def test_list_all_tasks(self, storage):
        """列出所有任务"""
        for i in range(5):
            storage.save(_make_task(target=f"query-{i}"))

        tasks = storage.list_tasks()
        assert len(tasks) == 5

    def test_list_filter_by_workspace(self, storage):
        """按工作空间过滤"""
        storage.save(_make_task(workspace_id="ws-001"))
        storage.save(_make_task(workspace_id="ws-002"))
        storage.save(_make_task(workspace_id="ws-001"))

        tasks = storage.list_tasks(workspace_id="ws-001")
        assert len(tasks) == 2

    def test_list_filter_by_task_type(self, storage):
        """按任务类型过滤"""
        storage.save(_make_task(task_type=CollectionTaskType.SEARCH))
        storage.save(_make_task(task_type=CollectionTaskType.CRAWL))

        tasks = storage.list_tasks(task_type="search")
        assert len(tasks) == 1
        assert tasks[0].task_type == CollectionTaskType.SEARCH

    def test_list_filter_by_status(self, storage):
        """按状态过滤"""
        task1 = _make_task(status=CollectionTaskStatus.PENDING)
        task2 = _make_task(status=CollectionTaskStatus.COMPLETED)
        storage.save(task1)
        storage.save(task2)

        tasks = storage.list_tasks(status="completed")
        assert len(tasks) == 1
        assert tasks[0].status == CollectionTaskStatus.COMPLETED

    def test_list_pagination(self, storage):
        """分页测试"""
        for i in range(10):
            storage.save(_make_task(target=f"query-{i}"))

        page1 = storage.list_tasks(page=1, page_size=3)
        page2 = storage.list_tasks(page=2, page_size=3)
        assert len(page1) == 3
        assert len(page2) == 3
        assert page1[0].id != page2[0].id


class TestSQLiteCollectionStorageUpdateStatus:
    """状态更新测试"""

    def test_update_to_completed(self, storage):
        """更新为完成状态"""
        task = _make_task()
        storage.save(task)

        result = storage.update_status(
            task.id,
            CollectionTaskStatus.COMPLETED,
            result={"title": "Test", "content": "Hello"},
        )
        assert result is True

        updated = storage.get(task.id)
        assert updated.status == CollectionTaskStatus.COMPLETED
        assert updated.result == {"title": "Test", "content": "Hello"}
        assert updated.completed_at is not None

    def test_update_to_failed(self, storage):
        """更新为失败状态"""
        task = _make_task()
        storage.save(task)

        storage.update_status(
            task.id,
            CollectionTaskStatus.FAILED,
            error_message="Connection timeout",
        )

        updated = storage.get(task.id)
        assert updated.status == CollectionTaskStatus.FAILED
        assert updated.error_message == "Connection timeout"
        assert updated.completed_at is not None

    def test_update_nonexistent_returns_false(self, storage):
        """更新不存在的任务返回 False"""
        result = storage.update_status("nonexistent", CollectionTaskStatus.RUNNING)
        assert result is False


class TestCollectionTaskModel:
    """CollectionTask 模型测试"""

    def test_default_values(self):
        """默认值测试"""
        task = CollectionTask(
            task_type=CollectionTaskType.SEARCH,
            target="test",
        )
        assert task.id  # 自动生成 UUID
        assert task.status == CollectionTaskStatus.PENDING
        assert task.result is None
        assert task.error_message is None
        assert task.source == "external"
        assert task.confidence == "medium"
        assert task.created_at  # 自动生成时间戳

    def test_enum_values(self):
        """枚举值测试"""
        assert CollectionTaskType.SEARCH.value == "search"
        assert CollectionTaskType.CRAWL.value == "crawl"
        assert CollectionTaskStatus.PENDING.value == "pending"
        assert CollectionTaskStatus.RUNNING.value == "running"
        assert CollectionTaskStatus.COMPLETED.value == "completed"
        assert CollectionTaskStatus.FAILED.value == "failed"

    def test_json_field_serialization(self, storage):
        """JSON 字段序列化/反序列化"""
        task = _make_task(result={"key": "value", "nested": {"a": 1}})
        storage.save(task)

        retrieved = storage.get(task.id)
        assert retrieved.result == {"key": "value", "nested": {"a": 1}}
