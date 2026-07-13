"""Unit tests for SqliteTemplateStorage and ensure_provenance_schema.

Uses tmp_path fixture for real SQLite DB (no mocks).
Covers: save, get_by_id, get_by_ontology, update_usage_count,
list_all, list_by_ontology, delete, UNIQUE constraint,
ensure_provenance_schema migration.
"""

import sqlite3
import os
import pytest

from odap.biz.data.hyper_extract.storage.sqlite_template_storage import (
    SqliteTemplateStorage,
    ensure_provenance_schema,
)


@pytest.fixture
def storage(tmp_path):
    """Create a SqliteTemplateStorage with a tmp_path DB."""
    db_path = str(tmp_path / "test_templates.db")
    return SqliteTemplateStorage(db_path=db_path)


@pytest.fixture
def sample_record():
    return {
        "ontology_id": "ont-001",
        "name": "graph",
        "description": "General graph template",
        "source": "preset",
        "yaml_path": None,
        "preset_name": "general/graph",
        "score": 0.85,
        "coverage": {"entities": True, "relations": True},
    }


class TestSqliteTemplateStorageSave:
    def test_save_inserts_new_record(self, storage, sample_record):
        record_id = storage.save(sample_record)
        assert record_id is not None

        fetched = storage.get_by_id(record_id)
        assert fetched is not None
        assert fetched["ontology_id"] == "ont-001"
        assert fetched["name"] == "graph"
        assert fetched["score"] == 0.85
        assert fetched["usage_count"] == 0

    def test_save_replaces_existing_by_id(self, storage, sample_record):
        record_id = storage.save(sample_record)

        sample_record["id"] = record_id
        sample_record["score"] = 0.95
        storage.save(sample_record)

        fetched = storage.get_by_id(record_id)
        assert fetched["score"] == 0.95

    def test_save_generates_uuid_if_no_id(self, storage, sample_record):
        record_id = storage.save(sample_record)
        assert record_id  # non-empty string
        assert len(record_id) >= 32  # UUID length


class TestSqliteTemplateStorageGet:
    def test_get_by_id_returns_none_for_missing(self, storage):
        assert storage.get_by_id("nonexistent") is None

    def test_get_by_ontology_returns_latest(self, storage, sample_record):
        storage.save(sample_record)

        sample_record["name"] = "custom_v2"
        sample_record["score"] = 0.90
        storage.save(sample_record)

        result = storage.get_by_ontology("ont-001")
        assert result is not None
        assert result["name"] == "custom_v2"

    def test_get_by_ontology_with_name(self, storage, sample_record):
        storage.save(sample_record)

        sample_record["name"] = "other"
        storage.save(sample_record)

        result = storage.get_by_ontology("ont-001", name="graph")
        assert result is not None
        assert result["name"] == "graph"

    def test_get_by_ontology_returns_none_for_missing(self, storage):
        assert storage.get_by_ontology("nonexistent") is None


class TestSqliteTemplateStorageUpdateUsageCount:
    def test_update_usage_count_increments(self, storage, sample_record):
        record_id = storage.save(sample_record)

        count1 = storage.update_usage_count(record_id)
        assert count1 == 1

        count2 = storage.update_usage_count(record_id)
        assert count2 == 2

        fetched = storage.get_by_id(record_id)
        assert fetched["usage_count"] == 2

    def test_update_usage_count_returns_zero_for_missing(self, storage):
        count = storage.update_usage_count("nonexistent")
        assert count == 0


class TestSqliteTemplateStorageList:
    def test_list_all_returns_all_records(self, storage, sample_record):
        storage.save(sample_record)

        sample_record["name"] = "custom_v2"
        sample_record["ontology_id"] = "ont-002"
        storage.save(sample_record)

        all_records = storage.list_all()
        assert len(all_records) == 2

    def test_list_by_ontology(self, storage, sample_record):
        storage.save(sample_record)

        sample_record["name"] = "other"
        storage.save(sample_record)

        sample_record["name"] = "diff"
        sample_record["ontology_id"] = "ont-002"
        storage.save(sample_record)

        results = storage.list_by_ontology("ont-001")
        assert len(results) == 2


class TestSqliteTemplateStorageDelete:
    def test_delete_removes_record(self, storage, sample_record):
        record_id = storage.save(sample_record)
        assert storage.delete(record_id) is True
        assert storage.get_by_id(record_id) is None

    def test_delete_returns_false_for_missing(self, storage):
        assert storage.delete("nonexistent") is False


class TestSqliteTemplateStorageUniqueConstraint:
    def test_unique_ontology_id_name_allows_different_names(self, storage, sample_record):
        storage.save(sample_record)

        sample_record["name"] = "different"
        storage.save(sample_record)

        results = storage.list_by_ontology("ont-001")
        assert len(results) == 2

    def test_unique_ontology_id_name_replaces_on_same_name(self, storage, sample_record):
        """INSERT OR REPLACE should update when same (ontology_id, name)."""
        storage.save(sample_record)

        sample_record["score"] = 0.99
        storage.save(sample_record)

        results = storage.list_by_ontology("ont-001")
        assert len(results) == 1
        assert results[0]["score"] == 0.99


class TestEnsureProvenanceSchema:
    def test_adds_source_template_column(self, tmp_path):
        """ensure_provenance_schema adds source_template if missing."""
        db_path = str(tmp_path / "test_provenance.db")

        # Create extraction_provenance table without source_template
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE extraction_provenance (
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
        conn.commit()
        conn.close()

        # Run migration
        ensure_provenance_schema(db_path)

        # Verify column was added
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(extraction_provenance)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "source_template" in columns

    def test_idempotent_when_column_exists(self, tmp_path):
        """ensure_provenance_schema should not fail if column already exists."""
        db_path = str(tmp_path / "test_provenance2.db")

        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE extraction_provenance (
                provenance_id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                session_id TEXT NOT NULL,
                source_doc_id TEXT NOT NULL,
                extraction_method TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source_template TEXT
            )
        """)
        conn.commit()
        conn.close()

        # Should not raise
        ensure_provenance_schema(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(extraction_provenance)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        assert "source_template" in columns
