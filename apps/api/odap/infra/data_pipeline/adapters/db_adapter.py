import uuid
import logging
from typing import Dict, Any, Iterator

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
        elif self._driver == "postgresql":
            return self._connect_postgresql()
        elif self._driver == "mysql":
            return self._connect_mysql()
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

    def _connect_postgresql(self) -> bool:
        try:
            import psycopg2  # noqa: F401 — optional dependency
            db_path = self.connection_string
            self._connection = psycopg2.connect(db_path)
            self._connected = True
            logger.info("DBAdapter connected to PostgreSQL")
            return True
        except ImportError:
            logger.error("DBAdapter: psycopg2 is not installed; install it to use PostgreSQL connections")
            return False
        except Exception as e:
            logger.error(f"DBAdapter PostgreSQL connect failed: {e}")
            return False

    def _connect_mysql(self) -> bool:
        try:
            import pymysql  # noqa: F401 — optional dependency
            db_path = self.connection_string
            self._connection = pymysql.connect(**self._parse_mysql_dsn(db_path))
            self._connected = True
            logger.info("DBAdapter connected to MySQL")
            return True
        except ImportError:
            logger.error("DBAdapter: pymysql is not installed; install it to use MySQL connections")
            return False
        except Exception as e:
            logger.error(f"DBAdapter MySQL connect failed: {e}")
            return False

    @staticmethod
    def _parse_mysql_dsn(dsn: str) -> Dict[str, Any]:
        """Parse a mysql://user:pass@host:port/db DSN into pymysql kwargs."""
        # Minimal DSN parser — supports mysql://user:password@host:port/database
        try:
            stripped = dsn.replace("mysql://", "")
            credentials, host_rest = stripped.rsplit("@", 1)
            if ":" in credentials:
                user, password = credentials.split(":", 1)
            else:
                user, password = credentials, ""
            if "/" in host_rest:
                host_port, database = host_rest.rsplit("/", 1)
            else:
                host_port, database = host_rest, ""
            if ":" in host_port:
                host, port = host_port.split(":", 1)
                port = int(port)
            else:
                host, port = host_port, 3306
            return {"host": host, "port": port, "user": user, "password": password, "database": database}
        except Exception as e:
            logger.debug("Connection info fallback: %s", e)
            return {"host": "localhost", "port": 3306}

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
                logger.error(f"DBAdapter SQLite query failed: {e}")
                return

        # PostgreSQL / MySQL: execute via driver connection
        if self._driver in ("postgresql", "mysql") and self._connection:
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
                        metadata={"query": query, "driver": self._driver},
                    )
                    count += 1
                cursor.close()
                return
            except Exception as e:
                logger.error(f"DBAdapter {self._driver} query failed: {e}")
                return

        # Driver not connected or unsupported — no data, no mock
        logger.warning(
            "DBAdapter: no active connection for driver '%s', returning empty result",
            self._driver,
        )

    def close(self):
        if self._connection:
            try:
                self._connection.close()
            except Exception as e:
                logger.debug("Connection close error: %s", e)
        self._connection = None
        self._connected = False
        logger.info("DBAdapter disconnected")
