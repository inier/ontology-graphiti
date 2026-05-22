import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.qa.qa_engine_v2 import DialogManager, DialogSession, DialogMessage, DialogState


class TestDialogManagerCreateSession:
    def test_create_session(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        assert session is not None
        assert session.user_id == "user1"
        assert session.session_id.startswith("SESSION-")
        assert session.state == DialogState.NEW
        assert session.messages == []
        assert session.workspace_id is None
        assert session.scenario_id is None
        assert session.created_at is not None
        assert session.updated_at is not None

    def test_create_session_with_workspace_and_scenario(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1", workspace_id="ws1", scenario_id="sc1")
        assert session.workspace_id == "ws1"
        assert session.scenario_id == "sc1"

    def test_create_session_stored_internally(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        assert dm.get_session(session.session_id) is session

    def test_create_multiple_sessions_unique_ids(self):
        dm = DialogManager()
        s1 = dm.create_session(user_id="user1")
        s2 = dm.create_session(user_id="user1")
        assert s1.session_id != s2.session_id


class TestDialogManagerGetSession:
    def test_get_session(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        result = dm.get_session(session.session_id)
        assert result is session
        assert result.session_id == session.session_id
        assert result.user_id == "user1"

    def test_get_session_not_found(self):
        dm = DialogManager()
        result = dm.get_session("SESSION-NONEXIST")
        assert result is None


class TestDialogManagerAddMessage:
    def test_add_message(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        msg = dm.add_message(session.session_id, "user", "Hello")
        assert msg is not None
        assert msg.message_id.startswith("MSG-")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None
        assert msg.metadata == {}

    def test_add_message_appends_to_session(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        dm.add_message(session.session_id, "user", "Hello")
        dm.add_message(session.session_id, "assistant", "Hi there")
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "Hello"
        assert session.messages[1].role == "assistant"
        assert session.messages[1].content == "Hi there"

    def test_add_message_sets_state_to_in_progress(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        assert session.state == DialogState.NEW
        dm.add_message(session.session_id, "user", "Hello")
        assert session.state == DialogState.IN_PROGRESS

    def test_add_message_updates_timestamp(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        old_updated = session.updated_at
        dm.add_message(session.session_id, "user", "Hello")
        assert session.updated_at >= old_updated

    def test_add_message_with_metadata(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        msg = dm.add_message(session.session_id, "assistant", "Answer", metadata={"traces": []})
        assert msg.metadata == {"traces": []}

    def test_add_message_nonexistent_session(self):
        dm = DialogManager()
        msg = dm.add_message("SESSION-NONEXIST", "user", "Hello")
        assert msg is not None
        assert msg.role == "user"
        assert msg.content == "Hello"


class TestDialogManagerGetContext:
    def test_get_context(self):
        dm = DialogManager(context_window=5)
        session = dm.create_session(user_id="user1")
        dm.add_message(session.session_id, "user", "What is X?")
        dm.add_message(session.session_id, "assistant", "X is Y.")
        context = dm.get_context(session.session_id)
        assert "user: What is X?" in context
        assert "assistant: X is Y." in context

    def test_get_context_respects_context_window(self):
        dm = DialogManager(context_window=3)
        session = dm.create_session(user_id="user1")
        dm.add_message(session.session_id, "user", "msg1")
        dm.add_message(session.session_id, "assistant", "ans1")
        dm.add_message(session.session_id, "user", "msg2")
        dm.add_message(session.session_id, "assistant", "ans2")
        dm.add_message(session.session_id, "user", "msg3")
        context = dm.get_context(session.session_id)
        assert "msg1" not in context
        assert "ans1" not in context
        assert "msg2" in context
        assert "ans2" in context
        assert "msg3" in context

    def test_get_context_includes_summary(self):
        dm = DialogManager(max_history=3, context_window=2)
        session = dm.create_session(user_id="user1")
        dm.add_message(session.session_id, "user", "msg1")
        dm.add_message(session.session_id, "assistant", "ans1")
        dm.add_message(session.session_id, "user", "msg2")
        dm.add_message(session.session_id, "assistant", "ans2")
        dm.add_message(session.session_id, "user", "msg3")
        context = dm.get_context(session.session_id)
        assert session.summary in context

    def test_get_context_empty_session(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        context = dm.get_context(session.session_id)
        assert context == ""

    def test_get_context_nonexistent_session(self):
        dm = DialogManager()
        context = dm.get_context("SESSION-NONEXIST")
        assert context == ""


class TestDialogManagerCompleteSession:
    def test_complete_session(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        dm.add_message(session.session_id, "user", "Hello")
        assert session.state == DialogState.IN_PROGRESS
        dm.close_session(session.session_id)
        assert session.state == DialogState.COMPLETED

    def test_complete_session_nonexistent(self):
        dm = DialogManager()
        dm.close_session("SESSION-NONEXIST")


class TestDialogManagerListSessions:
    def test_list_sessions(self):
        dm = DialogManager()
        s1 = dm.create_session(user_id="user1", workspace_id="ws1")
        s2 = dm.create_session(user_id="user2", workspace_id="ws1")
        s3 = dm.create_session(user_id="user1", workspace_id="ws2")
        result = dm.get_sessions_by_workspace("ws1")
        assert len(result) == 2
        assert s1 in result
        assert s2 in result
        assert s3 not in result

    def test_list_sessions_by_scenario(self):
        dm = DialogManager()
        s1 = dm.create_session(user_id="user1", scenario_id="sc1")
        s2 = dm.create_session(user_id="user2", scenario_id="sc2")
        s3 = dm.create_session(user_id="user1", scenario_id="sc1")
        result = dm.get_sessions_by_scenario("sc1")
        assert len(result) == 2
        assert s1 in result
        assert s3 in result
        assert s2 not in result

    def test_list_sessions_empty(self):
        dm = DialogManager()
        result = dm.get_sessions_by_workspace("ws-nonexist")
        assert result == []


class TestDialogManagerDeleteSession:
    def test_delete_session(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        session_id = session.session_id
        assert dm.get_session(session_id) is not None
        with dm._lock:
            del dm._sessions[session_id]
        assert dm.get_session(session_id) is None

    def test_delete_session_context_returns_empty(self):
        dm = DialogManager()
        session = dm.create_session(user_id="user1")
        dm.add_message(session.session_id, "user", "Hello")
        session_id = session.session_id
        with dm._lock:
            del dm._sessions[session_id]
        assert dm.get_context(session_id) == ""


class TestDialogManagerMaxHistory:
    def test_max_history(self):
        dm = DialogManager(max_history=4, context_window=2)
        session = dm.create_session(user_id="user1")
        dm.add_message(session.session_id, "user", "msg1")
        dm.add_message(session.session_id, "assistant", "ans1")
        dm.add_message(session.session_id, "user", "msg2")
        dm.add_message(session.session_id, "assistant", "ans2")
        assert len(session.messages) == 4
        dm.add_message(session.session_id, "user", "msg3")
        assert len(session.messages) <= dm.max_history
        assert len(session.messages) == dm.context_window

    def test_max_history_summarizes(self):
        dm = DialogManager(max_history=4, context_window=2)
        session = dm.create_session(user_id="user1")
        dm.add_message(session.session_id, "user", "msg1")
        dm.add_message(session.session_id, "assistant", "ans1")
        dm.add_message(session.session_id, "user", "msg2")
        dm.add_message(session.session_id, "assistant", "ans2")
        dm.add_message(session.session_id, "user", "msg3")
        assert session.summary != ""
        assert "早期对话摘要" in session.summary

    def test_max_history_keeps_recent_messages(self):
        dm = DialogManager(max_history=4, context_window=2)
        session = dm.create_session(user_id="user1")
        dm.add_message(session.session_id, "user", "msg1")
        dm.add_message(session.session_id, "assistant", "ans1")
        dm.add_message(session.session_id, "user", "msg2")
        dm.add_message(session.session_id, "assistant", "ans2")
        dm.add_message(session.session_id, "user", "msg3")
        assert session.messages[0].content == "ans2"
        assert session.messages[1].content == "msg3"

    def test_max_history_default_value(self):
        dm = DialogManager()
        assert dm.max_history == 10
        assert dm.context_window == 5
