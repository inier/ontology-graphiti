"""ImportExportManager 单元测试"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from odap.biz.platform.workspace.impl.import_export import ImportExportManager
from odap.biz.platform.workspace.models.import_export import (
    ImportExportRecord,
    ImportExportStatus,
)
from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage


class TestImportExportManagerExport(unittest.TestCase):
    """导出功能测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_workspace.db"
        self.storage = SQLiteStorage(db_path=db_path)
        self.mgr = ImportExportManager()
        self.mgr.storage = self.storage

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_export_workspace_completed(self):
        record = self.mgr.export_workspace("ws-1")
        self.assertEqual(record.status, ImportExportStatus.COMPLETED)
        self.assertEqual(record.operation, "export")
        self.assertEqual(record.workspace_id, "ws-1")

    def test_export_workspace_has_duration(self):
        record = self.mgr.export_workspace("ws-1")
        self.assertIsNotNone(record.duration_seconds)
        self.assertGreater(record.duration_seconds, 0)

    def test_export_workspace_file_size(self):
        record = self.mgr.export_workspace("ws-1")
        self.assertIsNotNone(record.file_size)

    def test_export_workspace_created_by(self):
        record = self.mgr.export_workspace("ws-1", created_by="admin")
        self.assertEqual(record.created_by, "admin")


class TestImportExportManagerImport(unittest.TestCase):
    """导入功能测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_workspace.db"
        self.storage = SQLiteStorage(db_path=db_path)
        self.mgr = ImportExportManager()
        self.mgr.storage = self.storage

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_import_workspace_completed(self):
        record = self.mgr.import_workspace("/path/to/import.zip")
        self.assertEqual(record.status, ImportExportStatus.COMPLETED)
        self.assertEqual(record.operation, "import")

    def test_import_workspace_has_source(self):
        record = self.mgr.import_workspace("/path/to/import.zip")
        self.assertEqual(record.source, "/path/to/import.zip")

    def test_import_workspace_has_duration(self):
        record = self.mgr.import_workspace("/path/to/import.zip")
        self.assertIsNotNone(record.duration_seconds)

    def test_import_workspace_created_by(self):
        record = self.mgr.import_workspace("/path/to/file", created_by="user1")
        self.assertEqual(record.created_by, "user1")


class TestImportExportManagerRecords(unittest.TestCase):
    """记录查询测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_workspace.db"
        self.storage = SQLiteStorage(db_path=db_path)
        self.mgr = ImportExportManager()
        self.mgr.storage = self.storage
        self.export_record = self.mgr.export_workspace("ws-1")
        self.import_record = self.mgr.import_workspace("/path/to/file")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_get_import_export_record(self):
        record = self.mgr.get_import_export_record(self.export_record.id)
        self.assertIsNotNone(record)
        self.assertEqual(record.operation, "export")

    def test_get_import_export_record_not_found(self):
        record = self.mgr.get_import_export_record("nonexistent")
        self.assertIsNone(record)

    def test_list_import_export_records(self):
        records = self.mgr.list_import_export_records()
        self.assertGreaterEqual(len(records), 2)

    def test_list_records_filter_by_operation(self):
        records = self.mgr.list_import_export_records(operation="export")
        for r in records:
            self.assertEqual(r.operation, "export")

    def test_list_records_filter_by_workspace(self):
        records = self.mgr.list_import_export_records(workspace_id="ws-1")
        for r in records:
            self.assertEqual(r.workspace_id, "ws-1")


class TestImportExportManagerCancel(unittest.TestCase):
    """取消操作测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_workspace.db"
        self.storage = SQLiteStorage(db_path=db_path)
        self.mgr = ImportExportManager()
        self.mgr.storage = self.storage

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_cancel_completed_returns_false(self):
        record = self.mgr.export_workspace("ws-1")
        # 已完成的记录不能取消
        result = self.mgr.cancel_import_export(record.id)
        self.assertFalse(result)

    def test_cancel_not_found_returns_false(self):
        result = self.mgr.cancel_import_export("nonexistent")
        self.assertFalse(result)


class TestImportExportManagerProgress(unittest.TestCase):
    """进度查询测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_workspace.db"
        self.storage = SQLiteStorage(db_path=db_path)
        self.mgr = ImportExportManager()
        self.mgr.storage = self.storage

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_get_progress(self):
        record = self.mgr.export_workspace("ws-1")
        progress = self.mgr.get_import_export_progress(record.id)
        self.assertEqual(progress["status"], "completed")
        self.assertEqual(progress["operation"], "export")

    def test_get_progress_not_found(self):
        progress = self.mgr.get_import_export_progress("nonexistent")
        self.assertEqual(progress["status"], "error")


class TestImportExportManagerValidate(unittest.TestCase):
    """导入文件验证测试"""

    def setUp(self):
        import tempfile
        self.tmp_dir = tempfile.mkdtemp()
        db_path = f"{self.tmp_dir}/test_workspace.db"
        self.storage = SQLiteStorage(db_path=db_path)
        self.mgr = ImportExportManager()
        self.mgr.storage = self.storage

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_validate_import_file(self):
        result = self.mgr.validate_import_file("/path/to/file.zip")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["file_format"], "zip")

    def test_validate_import_file_returns_path(self):
        result = self.mgr.validate_import_file("/path/to/file.zip")
        self.assertEqual(result["file_path"], "/path/to/file.zip")


if __name__ == "__main__":
    unittest.main()
