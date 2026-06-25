import sqlite3

import pytest


@pytest.fixture
def tracker(tmp_path):
    from odap.biz.core.ontology.extraction.impl.provenance_tracker import ProvenanceTracker

    db_path = str(tmp_path / "test_provenance.db")
    return ProvenanceTracker(db_path=db_path)


class TestProvenanceTracker:
    def test_init_creates_db_and_table(self, tmp_path):
        from odap.biz.core.ontology.extraction.impl.provenance_tracker import ProvenanceTracker

        db_path = str(tmp_path / "new_db.db")
        tracker = ProvenanceTracker(db_path=db_path)

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_provenance'"
        ).fetchall()
        conn.close()

        assert len(rows) == 1

    def test_record_extraction_stores_provenance(self, tracker):
        tracker.record_extraction(
            entity_id="ent-1",
            source_doc_id="doc-1",
            chunk_id="chunk-1",
            fragment_id="frag-1",
            method="hyper_extract",
            template_version="v2",
        )

        result = tracker.get_provenance("ent-1")

        assert result is not None
        assert result["entity_id"] == "ent-1"
        assert result["entity_type"] == "object_instance"
        assert result["source_doc_id"] == "doc-1"
        assert result["vector_chunk_id"] == "chunk-1"
        assert result["doc_fragment_id"] == "frag-1"
        assert result["extraction_method"] == "hyper_extract"
        assert result["he_template_version"] == "v2"
        assert result["confidence_score"] is None
        assert result["timestamp"] is not None
        assert result["provenance_id"] is not None
        assert result["session_id"] == ""

    def test_record_extraction_upsert(self, tracker, tmp_path):
        db_path = str(tmp_path / "upsert_test.db")

        conn = sqlite3.connect(db_path)
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
        conn.execute(
            """INSERT INTO extraction_provenance
               (provenance_id, entity_id, entity_type, session_id, source_doc_id,
                vector_chunk_id, doc_fragment_id, extraction_method, he_template_version,
                confidence_score, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("prov-1", "ent-1", "object_instance", "", "doc-1",
             "chunk-1", "frag-1", "hyper_extract", "v1", None, "2025-01-01T00:00:00"),
        )
        conn.commit()
        conn.close()

        from odap.biz.core.ontology.extraction.impl.provenance_tracker import ProvenanceTracker

        tracker_local = ProvenanceTracker(db_path=db_path)
        tracker_local.record_extraction(
            entity_id="ent-1",
            source_doc_id="doc-2",
            chunk_id="chunk-2",
            fragment_id="frag-2",
            method="manual",
            template_version="v2",
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM extraction_provenance WHERE entity_id = ? ORDER BY timestamp",
            ("ent-1",),
        ).fetchall()
        conn.close()

        assert len(rows) == 2
        assert dict(rows[0])["source_doc_id"] == "doc-1"
        assert dict(rows[1])["source_doc_id"] == "doc-2"

    def test_get_provenance_existing_entity(self, tracker):
        tracker.record_extraction(
            entity_id="ent-42",
            source_doc_id="doc-x",
            chunk_id="c1",
            fragment_id="f1",
            method="llm",
            template_version="v3",
        )

        result = tracker.get_provenance("ent-42")

        assert result is not None
        assert result["entity_id"] == "ent-42"
        assert isinstance(result, dict)

    def test_get_provenance_nonexistent_entity(self, tracker):
        result = tracker.get_provenance("does-not-exist")

        assert result is None

    def test_get_entities_by_source_returns_matching(self, tracker):
        tracker.record_extraction(
            entity_id="ent-a", source_doc_id="doc-shared",
            chunk_id="c1", fragment_id="f1",
            method="hyper_extract", template_version="v1",
        )
        tracker.record_extraction(
            entity_id="ent-b", source_doc_id="doc-shared",
            chunk_id="c2", fragment_id="f2",
            method="hyper_extract", template_version="v1",
        )
        tracker.record_extraction(
            entity_id="ent-c", source_doc_id="doc-other",
            chunk_id="c3", fragment_id="f3",
            method="manual", template_version="v2",
        )

        results = tracker.get_entities_by_source("doc-shared")

        assert len(results) == 2
        entity_ids = {r["entity_id"] for r in results}
        assert entity_ids == {"ent-a", "ent-b"}

    def test_get_entities_by_source_no_match(self, tracker):
        tracker.record_extraction(
            entity_id="ent-a", source_doc_id="doc-1",
            chunk_id="c1", fragment_id="f1",
            method="hyper_extract", template_version="v1",
        )

        results = tracker.get_entities_by_source("nonexistent-doc")

        assert results == []

    def test_indexes_created(self, tmp_path):
        from odap.biz.core.ontology.extraction.impl.provenance_tracker import ProvenanceTracker

        db_path = str(tmp_path / "idx_test.db")
        ProvenanceTracker(db_path=db_path)

        conn = sqlite3.connect(db_path)
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='extraction_provenance'"
        ).fetchall()
        conn.close()

        index_names = {row[0] for row in indexes}
        assert "idx_entity_id" in index_names
        assert "idx_source_doc_id" in index_names
        assert "idx_session_id" in index_names
