"""T059 [TDD] SQLiteAssistantStorage tests.

Tests for AI suggestion + assistant session storage layer.
Uses tmp_path real DB (AGENTS.md rule: no MagicMock for storage).
"""
import json

import pytest


@pytest.fixture
def storage(tmp_path):
    from odap.biz.core.ontology.assistant.storage.sqlite_assistant_storage import (
        SQLiteAssistantStorage,
    )
    db_path = str(tmp_path / "test_assistant.db")
    return SQLiteAssistantStorage(db_path=db_path)


def _make_suggestion(**overrides):
    base = {
        "ontology_id": "ont-001",
        "target_type": "object_type",
        "target_id": "type-user-001",
        "suggestion_category": "add_property",
        "content": {"name": "email", "data_type": "STRING", "required": True},
        "source": "rule_engine",
        "confidence": 1.0,
        "status": "pending",
        "session_id": "sess-001",
    }
    base.update(overrides)
    return base


def _make_session(**overrides):
    base = {
        "ontology_id": "ont-001",
        "user_id": "user-001",
        "context_type": "object_type_editor",
        "context_id": "type-user-001",
        "messages": [],
        "tool_calls": [],
        "hitl_pending": False,
        "status": "active",
    }
    base.update(overrides)
    return base


class TestAISuggestionCRUD:
    def test_save_and_retrieve_suggestion(self, storage):
        sug = _make_suggestion()
        result = storage.save_suggestion(sug)
        assert "suggestion_id" in result
        sid = result["suggestion_id"]
        retrieved = storage.get_suggestion(sid)
        assert retrieved is not None
        assert retrieved["ontology_id"] == "ont-001"
        assert retrieved["suggestion_category"] == "add_property"
        assert retrieved["status"] == "pending"

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_suggestion("nonexistent-id") is None

    def test_list_suggestions_by_ontology(self, storage):
        storage.save_suggestion(_make_suggestion(ontology_id="ont-A"))
        storage.save_suggestion(_make_suggestion(ontology_id="ont-A"))
        storage.save_suggestion(_make_suggestion(ontology_id="ont-B"))
        results = storage.list_suggestions(ontology_id="ont-A")
        assert len(results) == 2

    def test_list_suggestions_by_status(self, storage):
        storage.save_suggestion(_make_suggestion(status="pending"))
        storage.save_suggestion(_make_suggestion(status="accepted"))
        storage.save_suggestion(_make_suggestion(status="pending"))
        pending = storage.list_suggestions(status="pending")
        assert len(pending) == 2
        accepted = storage.list_suggestions(status="accepted")
        assert len(accepted) == 1

    def test_update_suggestion_status(self, storage):
        result = storage.save_suggestion(_make_suggestion())
        sid = result["suggestion_id"]
        updated = storage.update_suggestion_status(sid, "accepted")
        assert updated is True
        retrieved = storage.get_suggestion(sid)
        assert retrieved["status"] == "accepted"
        assert retrieved["resolved_at"] is not None

    def test_update_suggestion_status_with_rejection_reason(self, storage):
        result = storage.save_suggestion(_make_suggestion())
        sid = result["suggestion_id"]
        updated = storage.update_suggestion_status(
            sid, "rejected", rejection_reason="already exists"
        )
        assert updated is True
        retrieved = storage.get_suggestion(sid)
        assert retrieved["status"] == "rejected"
        assert retrieved["rejection_reason"] == "already exists"

    def test_update_nonexistent_returns_false(self, storage):
        assert storage.update_suggestion_status("nonexistent", "accepted") is False

    def test_delete_suggestion(self, storage):
        result = storage.save_suggestion(_make_suggestion())
        sid = result["suggestion_id"]
        assert storage.delete_suggestion(sid) is True
        assert storage.get_suggestion(sid) is None

    def test_delete_nonexistent_returns_false(self, storage):
        assert storage.delete_suggestion("nonexistent") is False

    def test_content_json_serialization(self, storage):
        sug = _make_suggestion(content={"name": "email", "constraints": {"format": "email"}})
        result = storage.save_suggestion(sug)
        sid = result["suggestion_id"]
        retrieved = storage.get_suggestion(sid)
        assert retrieved["content"]["name"] == "email"
        assert retrieved["content"]["constraints"]["format"] == "email"

    def test_upsert_behavior(self, storage):
        sug = _make_suggestion()
        result1 = storage.save_suggestion(sug)
        sid = result1["suggestion_id"]
        sug["suggestion_id"] = sid
        sug["status"] = "accepted"
        result2 = storage.save_suggestion(sug)
        assert result2["suggestion_id"] == sid
        retrieved = storage.get_suggestion(sid)
        assert retrieved["status"] == "accepted"


class TestAIAssistantSessionCRUD:
    def test_save_and_retrieve_session(self, storage):
        sess = _make_session()
        result = storage.save_session(sess)
        assert "session_id" in result
        sid = result["session_id"]
        retrieved = storage.get_session(sid)
        assert retrieved is not None
        assert retrieved["ontology_id"] == "ont-001"
        assert retrieved["context_type"] == "object_type_editor"

    def test_get_nonexistent_session_returns_none(self, storage):
        assert storage.get_session("nonexistent") is None

    def test_list_sessions_by_ontology(self, storage):
        storage.save_session(_make_session(ontology_id="ont-A"))
        storage.save_session(_make_session(ontology_id="ont-A"))
        storage.save_session(_make_session(ontology_id="ont-B"))
        results = storage.list_sessions(ontology_id="ont-A")
        assert len(results) == 2

    def test_update_session_messages(self, storage):
        result = storage.save_session(_make_session())
        sid = result["session_id"]
        new_messages = [{"role": "user", "content": "hello"}]
        updated = storage.update_session(sid, messages=new_messages)
        assert updated is True
        retrieved = storage.get_session(sid)
        assert retrieved["messages"][0]["content"] == "hello"

    def test_update_session_hitl_pending(self, storage):
        result = storage.save_session(_make_session())
        sid = result["session_id"]
        updated = storage.update_session(sid, hitl_pending=True)
        assert updated is True
        retrieved = storage.get_session(sid)
        assert retrieved["hitl_pending"] is True

    def test_delete_session(self, storage):
        result = storage.save_session(_make_session())
        sid = result["session_id"]
        assert storage.delete_session(sid) is True
        assert storage.get_session(sid) is None

    def test_delete_nonexistent_session_returns_false(self, storage):
        assert storage.delete_session("nonexistent") is False

    def test_messages_json_serialization(self, storage):
        sess = _make_session(messages=[{"role": "user", "content": "test"}])
        result = storage.save_session(sess)
        sid = result["session_id"]
        retrieved = storage.get_session(sid)
        assert retrieved["messages"][0]["role"] == "user"
        assert retrieved["messages"][0]["content"] == "test"

    def test_tool_calls_json_serialization(self, storage):
        sess = _make_session(tool_calls=[{"name": "add_property", "id": "tc-001"}])
        result = storage.save_session(sess)
        sid = result["session_id"]
        retrieved = storage.get_session(sid)
        assert retrieved["tool_calls"][0]["name"] == "add_property"

    def test_hitl_pending_boolean_conversion(self, storage):
        sess = _make_session(hitl_pending=True)
        result = storage.save_session(sess)
        sid = result["session_id"]
        retrieved = storage.get_session(sid)
        assert retrieved["hitl_pending"] is True

    def test_upsert_session(self, storage):
        sess = _make_session()
        result1 = storage.save_session(sess)
        sid = result1["session_id"]
        sess["session_id"] = sid
        sess["status"] = "completed"
        result2 = storage.save_session(sess)
        assert result2["session_id"] == sid
        retrieved = storage.get_session(sid)
        assert retrieved["status"] == "completed"


class TestInvalidJSONTolerance:
    def test_corrupted_content_returns_empty_dict(self, storage, tmp_path):
        result = storage.save_suggestion(_make_suggestion())
        sid = result["suggestion_id"]
        import sqlite3
        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE ai_suggestions SET content = 'NOT-JSON' WHERE suggestion_id = ?",
            (sid,),
        )
        conn.commit()
        conn.close()
        retrieved = storage.get_suggestion(sid)
        assert retrieved["content"] == {}

    def test_corrupted_messages_returns_empty_list(self, storage, tmp_path):
        result = storage.save_session(_make_session())
        sid = result["session_id"]
        import sqlite3
        conn = sqlite3.connect(storage.db_path)
        conn.execute(
            "UPDATE ai_assistant_sessions SET messages = 'BROKEN' WHERE session_id = ?",
            (sid,),
        )
        conn.commit()
        conn.close()
        retrieved = storage.get_session(sid)
        assert retrieved["messages"] == []
