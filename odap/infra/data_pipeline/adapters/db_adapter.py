import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Iterator, Optional

from ..data_pipeline import DataSourceConnector, DataRecord, DataFormat

logger = logging.getLogger(__name__)


class DBAdapter(DataSourceConnector):
    SUPPORTED_DRIVERS = {"sqlite", "postgresql", "mysql"}

    def __init__(self, connection_string: str, source_id: str = "database"):
        self.connection_string = connection_string
        self.source_id = source_id
        self._connected = False
        self._driver = self._detect_driver()
        self._connection = None

    def _detect_driver(self) -> str:
        lower = self.connection_string.lower()
        if lower.startswith("sqlite"):
            return "sqlite"
        elif lower.startswith("postgres"):
            return "postgresql"
        elif lower.startswith("mysql"):
            return "mysql"
        return "unknown"

    def connect(self) -> bool:
        if self._driver == "sqlite":
            return self._connect_sqlite()
        elif self._driver in ("postgresql", "mysql"):
            logger.info(f"DBAdapter: {self._driver} driver detected, using mock connection")
            self._connected = True
            return True
        else:
            logger.error(f"DBAdapter: unsupported driver in connection string: {self.connection_string}")
            return False

    def _connect_sqlite(self) -> bool:
        try:
            import sqlite3
            db_path = self.connection_string.replace("sqlite:///", "").replace("sqlite://", "")
            self._connection = sqlite3.connect(db_path)
            self._connected = True
            logger.info(f"DBAdapter connected to SQLite: {db_path}")
            return True
        except Exception as e:
            logger.error(f"DBAdapter SQLite connect failed: {e}")
            return False

    def read(self, **kwargs) -> Iterator[DataRecord]:
        if not self._connected:
            self.connect()
        if not self._connected:
            return

        query = kwargs.get("query", "SELECT 1")
        limit = kwargs.get("limit", 0)
        count = 0

        if self._driver == "sqlite" and self._connection:
            try:
                cursor = self._connection.cursor()
                cursor.execute(query)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                for row in cursor.fetchall():
                    if limit and count >= limit:
                        break
                    record_dict = dict(zip(columns, row))
                    yield DataRecord(
                        id=str(uuid.uuid4())[:12],
                        source_id=self.source_id,
                        content=record_dict,
                        format=DataFormat.JSON,
                        metadata={"query": query, "driver": "sqlite"},
                    )
                    count += 1
                cursor.close()
                return
            except Exception as e:
                logger.warning(f"DBAdapter SQLite query failed: {e}, using mock")

        yield DataRecord(
            id=str(uuid.uuid4())[:12],
            source_id=self.source_id,
            content={"query": query, "result": "mock", "driver": self._driver},
            format=DataFormat.JSON,
            metadata={"query": query, "driver": self._driver, "mock": True},
        )

    def close(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
        self._connection = None
        self._connected = False
        logger.info("DBAdapter disconnected")
