"""SQLiteExtractionStorage unit tests.

Covers:
- save_task / get_task: round-trip persistence
- get_task: nonexistent returns None
- list_tasks: with ontology_id filter, with status filter
- update_status: simple status change, with result data, nonexistent task
- JSON serialization / deserialization for result field
- Enum value storage and retrieval

Rules (AGENTS.md):
- Uses tmp_path fixture for real SQLite DB (NOT MagicMock for storage layer)
- SQLite storage layer tests use real DB, not MagicMock
"""

import pytest

from odap.biz.data.hyper_extract.models.extraction_task import (
    ExtractionTask,
    ExtractionStatus,
)
from odap.biz.data.hyper_extract.storage.sqlite_extraction_storage import (
    SQLiteExtractionStorage,
)


class TestSQLiteExtractionStorage:
    """Tests for SQLiteExtractionStorage using tmp_path real DB."""

    def test_save_and_get_task(self, tmp_path):
        """Round-trip: save a task then retrieve it by task_id."""
        storage = SQLiteExtractionStorage(db_path=str(tmp_path / "test.db"))
        task = ExtractionTask(text_hash="abc123", ontology_id="ont-1")
        task_id = storage.save_task(task)
        retrieved = storage.get_task(task_id)
        assert retrieved is not None
        assert retrieved.task_id == task_id
        assert retrieved.text_hash == "abc123"
        assert retrieved.ontology_id == "ont-1"
        assert retrieved.status == ExtractionStatus.PENDING

    def test_get_nonexistent_task(self, tmp_path):
        """Getting a nonexistent task_id returns None."""
        storage = SQLiteExtractionStorage(db_path=str(tmp_path / "test.db"))
        result = storage.get_task("nonexistent")
        assert result is None

    def test_list_tasks(self, tmp_path):
        """list_tasks returns all tasks for a given ontology_id."""
        storage = SQLiteExtractionStorage(db_path=str(tmp_path / "test.db"))
        for i in range(5):
            task = ExtractionTask(text_hash=f"hash_{i}", ontology_id="ont-1")
            storage.save_task(task)
        tasks = storage.list_tasks(ontology_id="ont-1")
        assert len(tasks) == 5

    def test_list_tasks_with_status_filter(self, tmp_path):
        """list_tasks filters by status correctly."""
        storage = SQLiteExtractionStorage(db_path=str(tmp_path / "test.db"))
        task1 = ExtractionTask(
            text_hash="h1", ontology_id="ont-1", status=ExtractionStatus.COMPLETED
        )
        task2 = ExtractionTask(
            text_hash="h2", ontology_id="ont-1", status=ExtractionStatus.PENDING
        )
        storage.save_task(task1)
        storage.save_task(task2)
        completed = storage.list_tasks(status=ExtractionStatus.COMPLETED)
        assert len(completed) == 1
        assert completed[0].status == ExtractionStatus.COMPLETED

    def test_update_status(self, tmp_path):
        """update_status changes the task status and returns True."""
        storage = SQLiteExtractionStorage(db_path=str(tmp_path / "test.db"))
        task = ExtractionTask(text_hash="h1", ontology_id="ont-1")
        task_id = storage.save_task(task)
        result = storage.update_status(task_id, ExtractionStatus.PROCESSING)
        assert result is True
        updated = storage.get_task(task_id)
        assert updated.status == ExtractionStatus.PROCESSING

    def test_update_status_with_result(self, tmp_path):
        """update_status stores result JSON alongside the new status."""
        storage = SQLiteExtractionStorage(db_path=str(tmp_path / "test.db"))
        task = ExtractionTask(text_hash="h1", ontology_id="ont-1")
        task_id = storage.save_task(task)
        result_data = {"entities_count": 5, "relations_count": 3}
        storage.update_status(task_id, ExtractionStatus.COMPLETED, result=result_data)
        updated = storage.get_task(task_id)
        assert updated.status == ExtractionStatus.COMPLETED
        assert updated.result["entities_count"] == 5

    def test_update_nonexistent_task(self, tmp_path):
        """update_status for a nonexistent task_id returns False."""
        storage = SQLiteExtractionStorage(db_path=str(tmp_path / "test.db"))
        result = storage.update_status("nonexistent", ExtractionStatus.COMPLETED)
        assert result is False

    def test_json_serialization(self, tmp_path):
        """Complex dict result is serialized/deserialized correctly."""
        storage = SQLiteExtractionStorage(db_path=str(tmp_path / "test.db"))
        task = ExtractionTask(
            text_hash="h1",
            ontology_id="ont-1",
            result={"key": "value", "nested": {"a": 1}},
        )
        task_id = storage.save_task(task)
        retrieved = storage.get_task(task_id)
        assert retrieved.result["key"] == "value"
        assert retrieved.result["nested"]["a"] == 1

    def test_enum_value_storage(self, tmp_path):
        """Enum status is stored as .value string and reconstructed as Enum."""
        storage = SQLiteExtractionStorage(db_path=str(tmp_path / "test.db"))
        task = ExtractionTask(
            text_hash="h1", ontology_id="ont-1", status=ExtractionStatus.FAILED
        )
        task_id = storage.save_task(task)
        retrieved = storage.get_task(task_id)
        assert retrieved.status == ExtractionStatus.FAILED
        assert isinstance(retrieved.status, ExtractionStatus)
