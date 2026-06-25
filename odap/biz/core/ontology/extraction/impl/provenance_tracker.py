import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.extraction.interfaces.extraction_interfaces import ProvenanceTrackerInterface

logger = logging.getLogger(__name__)


class ProvenanceTracker(ProvenanceTrackerInterface):
    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(
            os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
            "extraction_provenance.db",
        )
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
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
                confidence_score REAL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_id ON extraction_provenance(entity_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source_doc_id ON extraction_provenance(source_doc_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON extraction_provenance(session_id)")
        conn.commit()
        conn.close()

    def record_extraction(self, entity_id: str, source_doc_id: str, chunk_id: str,
                          fragment_id: str, method: str, template_version: str) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT OR REPLACE INTO extraction_provenance
               (provenance_id, entity_id, entity_type, session_id, source_doc_id,
                vector_chunk_id, doc_fragment_id, extraction_method, he_template_version,
                confidence_score, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), entity_id, "object_instance", "", source_doc_id,
             chunk_id, fragment_id, method, template_version, None, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_provenance(self, entity_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM extraction_provenance WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def get_entities_by_source(self, source_doc_id: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM extraction_provenance WHERE source_doc_id = ?", (source_doc_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
