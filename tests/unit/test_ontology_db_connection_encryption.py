"""Tests for password encryption in SQLiteOntologyStorage database_connections.

AGENTS.md Rule 9: new modules must have tests.
AGENTS.md Rule C: SQLite storage tests use tmp_path real DB, no MagicMock.
"""
import json
import os

import pytest

# Reset ClassifiedFieldEncryptor singleton between tests to avoid key reuse
from odap.infra.security.encryption import ClassifiedFieldEncryptor


@pytest.fixture(autouse=True)
def _reset_encryptor_singleton():
    """Reset the ClassifiedFieldEncryptor singleton before each test."""
    ClassifiedFieldEncryptor._instance = None
    ClassifiedFieldEncryptor._key = None
    yield
    ClassifiedFieldEncryptor._instance = None
    ClassifiedFieldEncryptor._key = None


@pytest.fixture
def storage(tmp_path):
    """Create a SQLiteOntologyStorage with a temp DB."""
    from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
        SQLiteOntologyStorage,
    )
    db_file = str(tmp_path / "test_ontology_api.db")
    return SQLiteOntologyStorage(db_path=db_file)


def _make_conn(**overrides):
    """Factory for database connection test data."""
    base = {
        "name": "test-conn",
        "db_type": "postgresql",
        "host": "localhost",
        "port": 5432,
        "database": "testdb",
        "username": "admin",
        "password_encrypted": "s3cret!",
        "workspace_id": "ws-001",
    }
    base.update(overrides)
    return base


class TestPasswordEncryption:
    """Verify that passwords are encrypted at rest and decrypted on read."""

    def test_save_encrypts_password_at_rest(self, storage, tmp_path):
        """The raw SQLite file must NOT contain the plaintext password."""
        conn_data = _make_conn(password_encrypted="my_plain_password")
        result = storage.save_database_connection(conn_data)

        # Read-through should return the original plaintext
        assert result["password_encrypted"] == "my_plain_password"

        # But the raw DB file must NOT contain the plaintext
        import sqlite3
        raw_conn = sqlite3.connect(str(tmp_path / "test_ontology_api.db"))
        row = raw_conn.execute(
            "SELECT password_encrypted FROM database_connections WHERE connection_id = ?",
            (result["connection_id"],),
        ).fetchone()
        raw_conn.close()
        stored_value = row[0]
        assert stored_value != "my_plain_password"
        # The stored value should be a JSON string with encrypted/nonce/tag fields
        parsed = json.loads(stored_value)
        assert "encrypted" in parsed
        assert "nonce" in parsed
        assert "tag" in parsed

    def test_get_decrypts_password(self, storage):
        """get_database_connection should return the decrypted plaintext password."""
        conn_data = _make_conn(password_encrypted="decrypt_me")
        saved = storage.save_database_connection(conn_data)

        fetched = storage.get_database_connection(saved["connection_id"])
        assert fetched is not None
        assert fetched["password_encrypted"] == "decrypt_me"

    def test_list_decrypts_passwords(self, storage):
        """list_database_connections should return decrypted plaintext passwords."""
        storage.save_database_connection(_make_conn(name="c1", password_encrypted="pw1"))
        storage.save_database_connection(_make_conn(name="c2", password_encrypted="pw2"))

        results = storage.list_database_connections("ws-001")
        assert len(results) == 2
        passwords = {r["password_encrypted"] for r in results}
        assert passwords == {"pw1", "pw2"}

    def test_empty_password_stored_as_none(self, storage):
        """An empty string password is treated as 'no password' and stored as None."""
        conn_data = _make_conn(password_encrypted="")
        saved = storage.save_database_connection(conn_data)
        # Empty string is falsy, so it is stored as None (no password)
        assert saved.get("password_encrypted") is None

    def test_none_password_stored_as_none(self, storage):
        """A None password should be stored as None (no encryption attempted)."""
        conn_data = _make_conn(password_encrypted=None)
        del conn_data["password_encrypted"]
        saved = storage.save_database_connection(conn_data)
        # password_encrypted should be None in the returned dict
        assert saved.get("password_encrypted") is None

    def test_encrypt_decrypt_helper_roundtrip(self):
        """_encrypt_password and _decrypt_password are inverse operations."""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )
        original = "P@ssw0rd!#$%"
        encrypted = SQLiteOntologyStorage._encrypt_password(original)
        assert encrypted != original
        decrypted = SQLiteOntologyStorage._decrypt_password(encrypted)
        assert decrypted == original

    def test_encrypt_helper_empty_string_passthrough(self):
        """_encrypt_password returns empty string unchanged."""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )
        assert SQLiteOntologyStorage._encrypt_password("") == ""

    def test_decrypt_helper_empty_string_passthrough(self):
        """_decrypt_password returns empty string unchanged."""
        from odap.biz.core.ontology.ontology_api.storage.sqlite_ontology_storage import (
            SQLiteOntologyStorage,
        )
        assert SQLiteOntologyStorage._decrypt_password("") == ""

    def test_get_nonexistent_connection_returns_none(self, storage):
        """get_database_connection returns None for unknown IDs."""
        assert storage.get_database_connection("no-such-id") is None

    def test_list_empty_workspace(self, storage):
        """list_database_connections returns [] for workspace with no connections."""
        assert storage.list_database_connections("empty-ws") == []
