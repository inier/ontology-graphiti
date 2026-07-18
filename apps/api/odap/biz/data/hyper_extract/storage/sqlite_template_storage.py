"""SQLite storage for HE template metadata.

Stores template assessment results, custom-generated templates, and usage
statistics in the he_templates table. Also provides a migration helper
to add source_template column to extraction_provenance.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = os.path.join(
    os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data")), "hyper_extract"
)
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "hyper_extract.db")

_DDL_HE_TEMPLATES = """
CREATE TABLE IF NOT EXISTS he_templates (
    id TEXT PRIMARY KEY,
    ontology_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    source TEXT NOT NULL DEFAULT 'preset',
    yaml_path TEXT,
    preset_name TEXT,
    score REAL,
    coverage TEXT,
    usage_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(ontology_id, name)
)
"""

_DDL_HE_TEMPLATES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_he_templates_ontology
ON he_templates(ontology_id)
"""


def ensure_provenance_schema(db_path: str = None) -> None:
    """Add source_template column to extraction_provenance if missing.

    T003: ALTER migration — called during ProvenanceTracker init to ensure
    the source_template column exists for tracking which HE template produced
    each provenance record.
    """
    if db_path is None:
        db_path = os.path.join(
            os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "extraction_provenance.db",
        )

    conn = sqlite3.connect(db_path, timeout=30)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(extraction_provenance)")
        columns = {row[1] for row in cursor.fetchall()}
        if "source_template" not in columns:
            cursor.execute(
                "ALTER TABLE extraction_provenance ADD COLUMN source_template TEXT"
            )
            conn.commit()
            logger.info("Added source_template column to extraction_provenance")
    finally:
        conn.close()


class SqliteTemplateStorage:
    """CRUD storage for HE template metadata in SQLite.

    Follows the same WAL + _get_conn pattern as SQLiteExtractionStorage.
    """

    SQLITE_TIMEOUT = 30

    def __init__(self, db_path: str = None):
        if db_path is None:
            os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=self.SQLITE_TIMEOUT)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        conn = self._get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(_DDL_HE_TEMPLATES)
            cursor.execute(_DDL_HE_TEMPLATES_INDEX)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, record: Dict[str, Any]) -> str:
        """Insert or replace a template record. Returns the record id."""
        import uuid

        record_id = record.get("id") or str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = self._get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO he_templates
                (id, ontology_id, name, description, source, yaml_path,
                 preset_name, score, coverage, usage_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    record["ontology_id"],
                    record["name"],
                    record.get("description"),
                    record.get("source", "preset"),
                    record.get("yaml_path"),
                    record.get("preset_name"),
                    record.get("score"),
                    json.dumps(record["coverage"], ensure_ascii=False)
                    if isinstance(record.get("coverage"), dict)
                    else record.get("coverage"),
                    record.get("usage_count", 0),
                    record.get("created_at", now),
                    now,
                ),
            )
            conn.commit()
            return record_id
        finally:
            conn.close()

    def get_by_id(self, template_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM he_templates WHERE id = ?", (template_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_by_ontology(
        self, ontology_id: str, name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the settled template for an ontology. If name is provided,
        fetch that specific template; otherwise fetch the most recently
        updated one."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            if name:
                row = conn.execute(
                    "SELECT * FROM he_templates WHERE ontology_id = ? AND name = ?",
                    (ontology_id, name),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM he_templates WHERE ontology_id = ? "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (ontology_id,),
                ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_usage_count(self, template_id: str) -> int:
        """Increment usage_count by 1. Returns the new count."""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE he_templates SET usage_count = usage_count + 1, "
                "updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), template_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT usage_count FROM he_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
            return row[0] if row else 0
        finally:
            conn.close()

    def list_by_ontology(self, ontology_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM he_templates WHERE ontology_id = ? "
                "ORDER BY created_at ASC",
                (ontology_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def list_all(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM he_templates ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def delete(self, template_id: str) -> bool:
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM he_templates WHERE id = ?", (template_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
