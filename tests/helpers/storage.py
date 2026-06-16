"""SQLite storage test base utilities.

Provides a base class that handles the common pattern of:
1. Creating a temp DB path
2. Instantiating the storage class
3. Running tests against a real SQLite database

AGENTS.md Rule C: SQLite storage tests use tmp_path real DB, no MagicMock.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional, Type


class StorageTestBase:
    """Base class for SQLite storage tests.

    Subclasses must set:
        storage_class: The storage class to test
        init_kwargs: Additional kwargs to pass to the constructor (optional)

    Usage::

        class TestMyStorage(StorageTestBase):
            storage_class = SQLiteMyStorage

            def test_save_and_get(self, tmp_path):
                storage = self.make_storage(tmp_path)
                storage.save_item({"id": "1", "name": "test"})
                result = storage.get_item("1")
                assert result is not None
                assert result["name"] == "test"
    """

    storage_class: Optional[Type] = None
    init_kwargs: Dict[str, Any] = {}

    def make_storage(self, tmp_path, db_name: str = "test.db", **extra_kwargs):
        """Create a storage instance with a temporary database.

        Args:
            tmp_path: pytest's tmp_path fixture value
            db_name: Database file name (default: test.db)
            **extra_kwargs: Override constructor arguments
        """
        assert self.storage_class is not None, "Subclass must set storage_class"
        db_path = str(tmp_path / db_name)
        kwargs = {**self.init_kwargs, **extra_kwargs}
        return self.storage_class(db_path=db_path, **kwargs)

    @staticmethod
    def read_db(db_path: str, query: str, params: tuple = ()) -> list:
        """Execute a raw SQL query against the test database.

        Useful for verifying storage operations at the SQL level.
        """
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
        finally:
            conn.close()

    @staticmethod
    def count_rows(db_path: str, table: str) -> int:
        """Count rows in a table."""
        rows = StorageTestBase.read_db(db_path, f"SELECT COUNT(*) as cnt FROM {table}")
        return rows[0]["cnt"] if rows else 0
