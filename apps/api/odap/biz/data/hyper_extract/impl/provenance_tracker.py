"""ProvenanceTracker — extraction provenance records with source_template.

Migrated from odap/biz/core/ontology/extraction/impl/provenance_tracker.py
with the addition of `source_template` field per data-model.md.

Rules (AGENTS.md):
- SQLite: connect/close per operation (no connection pool)
- ALTER TABLE migration for existing databases (adds source_template column)
- Backward compatible: source_template defaults to "" when not provided
"""

import logging
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProvenanceTracker:
    """Records and queries extraction provenance with source_template tracking.

    Schema (extraction_provenance):
        provenance_id   TEXT PRIMARY KEY
        entity_id       TEXT NOT NULL
        entity_type     TEXT NOT NULL
        session_id      TEXT NOT NULL
        source_doc_id   TEXT NOT NULL
        vector_chunk_id TEXT
        doc_fragment_id TEXT
        extraction_method TEXT NOT NULL
        he_template_version TEXT
        source_template TEXT              -- NEW: source template name
        confidence_score REAL
        timestamp       TEXT NOT NULL
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "extraction_provenance.db",
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extraction_provenance (
                provenance_id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                session_id TEXT NOT NULL,
                source_doc_id TEXT NOT NULL,
                vector_chunk_id TEXT,
                doc_fragment_id TEXT,
                extraction_method TEXT NOT NULL,
                he_template_version TEXT,
                source_template TEXT,
                confidence_score REAL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entity_id ON extraction_provenance(entity_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_source_doc_id ON extraction_provenance(source_doc_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_session_id ON extraction_provenance(session_id)"
        )
        # Migration: add source_template column if upgrading from old schema
        self._migrate_add_source_template(conn)
        conn.commit()
        conn.close()

    @staticmethod
    def _migrate_add_source_template(conn: sqlite3.Connection):
        """Idempotent migration: add source_template column if missing."""
        cursor = conn.execute("PRAGMA table_info(extraction_provenance)")
        columns = {row[1] for row in cursor.fetchall()}
        if "source_template" not in columns:
            conn.execute(
                "ALTER TABLE extraction_provenance ADD COLUMN source_template TEXT"
            )
            logger.info("extraction_provenance: added source_template column")

    def record_extraction(
        self,
        entity_id: str,
        source_doc_id: str,
        chunk_id: str,
        fragment_id: str,
        method: str,
        template_version: str,
        source_template: str = "",
        entity_type: str = "object_instance",
        session_id: str = "",
        confidence_score: Optional[float] = None,
    ) -> None:
        """Record a single extraction provenance entry.

        Args:
            entity_id: Extracted entity ID.
            source_doc_id: Source document ID.
            chunk_id: Vector chunk ID.
            fragment_id: Document fragment ID.
            method: Extraction method (e.g. "he", "schema_level").
            template_version: HE template version (legacy field).
            source_template: Source template name (e.g. "general/base_graph").
            entity_type: Entity type category.
            session_id: Extraction session ID.
            confidence_score: Optional confidence score (0-1).
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO extraction_provenance
               (provenance_id, entity_id, entity_type, session_id, source_doc_id,
                vector_chunk_id, doc_fragment_id, extraction_method, he_template_version,
                source_template, confidence_score, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                entity_id,
                entity_type,
                session_id,
                source_doc_id,
                chunk_id,
                fragment_id,
                method,
                template_version,
                source_template,
                confidence_score,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def get_provenance(self, entity_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM extraction_provenance WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_entities_by_source(self, source_doc_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM extraction_provenance WHERE source_doc_id = ?",
            (source_doc_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_entities_by_template(self, source_template: str) -> List[Dict[str, Any]]:
        """Query provenance entries by source_template (new capability)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM extraction_provenance WHERE source_template = ?",
            (source_template,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
