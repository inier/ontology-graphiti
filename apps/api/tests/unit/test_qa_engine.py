import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.data.qa.qa_engine import (
    DialogManager, DialogSession, DialogMessage, DialogState,
    QAEngineV2, RAGResult, clarification_reason_to_chinese,
)


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


# ── 追问/澄清机制测试 ──


class TestClarificationReasonToChinese:
    def test_known_reasons(self):
        assert "未检索" in clarification_reason_to_chinese("no_results")
        assert "相关性较低" in clarification_reason_to_chinese("low_score")
        assert "模糊代词" in clarification_reason_to_chinese("ambiguous_pronoun")
        assert "过于简短" in clarification_reason_to_chinese("too_short")

    def test_unknown_reason_passthrough(self):
        assert clarification_reason_to_chinese("something_else") == "something_else"


class TestNeedsClarification:
    """测试 _needs_clarification 辅助方法"""

    def _make_engine(self):
        return QAEngineV2(use_mock=True)

    def test_no_results(self):
        engine = self._make_engine()
        needs, reason, questions = engine._needs_clarification("测试问题", [])
        assert needs is True
        assert reason == "no_results"
        assert len(questions) >= 2

    def test_low_score_results(self):
        engine = self._make_engine()
        low_results = [
            RAGResult(content="xxx", source="s1", score=0.05, metadata={}),
            RAGResult(content="yyy", source="s2", score=0.10, metadata={}),
        ]
        needs, reason, questions = engine._needs_clarification("测试问题", low_results)
        assert needs is True
        assert reason == "low_score"
        assert len(questions) >= 1

    def test_low_score_with_entity_hints(self):
        engine = self._make_engine()
        low_results = [
            RAGResult(content="实体A | 类型:人物", source="s1", score=0.05,
                      metadata={"entity_type": "人物"}),
        ]
        needs, reason, questions = engine._needs_clarification("测试问题", low_results)
        assert needs is True
        assert reason == "low_score"
        # 应包含实体名或类型提示
        has_hint = any("实体A" in q or "人物" in q for q in questions)
        assert has_hint

    def test_high_score_no_clarification(self):
        engine = self._make_engine()
        good_results = [
            RAGResult(content="实体A", source="s1", score=0.8, metadata={}),
        ]
        needs, reason, questions = engine._needs_clarification("实体A是什么", good_results)
        assert needs is False
        assert reason == ""
        assert questions == []

    def test_ambiguous_pronoun_short_query(self):
        engine = self._make_engine()
        good_results = [
            RAGResult(content="实体A", source="s1", score=0.8, metadata={}),
        ]
        needs, reason, questions = engine._needs_clarification("它", good_results)
        assert needs is True
        assert reason == "ambiguous_pronoun"
        assert len(questions) >= 1

    def test_ambiguous_pronoun_with_referent_hints(self):
        engine = self._make_engine()
        good_results = [
            RAGResult(content="实体A | 详情", source="s1", score=0.8, metadata={}),
            RAGResult(content="实体B | 详情", source="s2", score=0.7, metadata={}),
        ]
        needs, reason, questions = engine._needs_clarification("那个", good_results)
        assert needs is True
        assert reason == "ambiguous_pronoun"
        # 应包含指代对象提示
        has_referent = any("实体" in q for q in questions)
        assert has_referent

    def test_ambiguous_pronoun_long_query_no_clarification(self):
        """长问题含代词不触发澄清（有足够上下文）"""
        engine = self._make_engine()
        good_results = [
            RAGResult(content="实体A", source="s1", score=0.8, metadata={}),
        ]
        needs, reason, questions = engine._needs_clarification(
            "请告诉我它的详细信息和关联关系", good_results
        )
        assert needs is False

    def test_too_short_query(self):
        engine = self._make_engine()
        good_results = [
            RAGResult(content="实体A", source="s1", score=0.8,
                      metadata={"entity_type": "人物"}),
        ]
        needs, reason, questions = engine._needs_clarification("??", good_results)
        assert needs is True
        assert reason == "too_short"
        assert len(questions) >= 2

    def test_custom_score_threshold(self):
        engine = self._make_engine()
        medium_results = [
            RAGResult(content="xxx", source="s1", score=0.3, metadata={}),
        ]
        # 默认阈值 0.15，0.3 > 0.15 不触发
        needs, _, _ = engine._needs_clarification("测试问题", medium_results)
        assert needs is False

        # 自定义阈值 0.5，0.3 < 0.5 触发
        needs, reason, _ = engine._needs_clarification("测试问题", medium_results, score_threshold=0.5)
        assert needs is True
        assert reason == "low_score"


class TestAskClarification:
    """测试 ask() 方法的澄清逻辑"""

    def _make_engine(self):
        engine = QAEngineV2(use_mock=True)
        # Mock RAG pipeline 使其返回空结果
        engine.rag_pipeline.retrieve = MagicMock(return_value=[])
        engine.rag_pipeline.generate_context = MagicMock(return_value="未找到相关信息。")
        return engine

    def test_ask_returns_clarification_when_no_results(self):
        engine = self._make_engine()
        result = engine.ask("模糊问题", user_id="test")
        assert result["dialog_state"] == "waiting_for_clarification"
        assert "clarification_questions" in result
        assert isinstance(result["clarification_questions"], list)
        assert len(result["clarification_questions"]) >= 2
        assert result["clarification_reason"] == "no_results"
        assert result["decision_available"] is False
        assert result["sources"] == []

    def test_ask_clarification_sets_session_state(self):
        engine = self._make_engine()
        result = engine.ask("模糊问题", user_id="test")
        session_id = result["session_id"]
        session = engine.dialog_manager.get_session(session_id)
        assert session.state == DialogState.WAITING_FOR_CLARIFICATION

    def test_ask_clarification_saves_original_query(self):
        engine = self._make_engine()
        result = engine.ask("原始问题", user_id="test")
        session_id = result["session_id"]
        session = engine.dialog_manager.get_session(session_id)
        assert session.context.get("original_query") == "原始问题"

    def test_ask_follow_up_after_clarification_merges_context(self):
        """当会话处于 WAITING_FOR_CLARIFICATION 状态时，追问应合并上下文"""
        engine = self._make_engine()
        # 第一次提问触发澄清
        result1 = engine.ask("原始问题", user_id="test")
        session_id = result1["session_id"]
        assert result1["dialog_state"] == "waiting_for_clarification"

        # 模拟第二次 RAG 返回有效结果
        good_results = [
            RAGResult(content="实体A | 类型:人物", source="s1", score=0.8, metadata={}),
        ]
        engine.rag_pipeline.retrieve = MagicMock(return_value=good_results)
        engine.rag_pipeline.generate_context = MagicMock(return_value="实体A | 类型:人物")

        # 第二次追问（补充信息）
        result2 = engine.ask("补充信息", user_id="test", session_id=session_id)
        # 应正常回答，不再触发澄清
        assert result2["dialog_state"] != "waiting_for_clarification"
        # 会话状态应恢复为 IN_PROGRESS 或 COMPLETED
        session = engine.dialog_manager.get_session(session_id)
        assert session.state != DialogState.WAITING_FOR_CLARIFICATION

    def test_ask_normal_query_no_clarification(self):
        """正常问题（RAG 结果充分）不应触发澄清"""
        engine = QAEngineV2(use_mock=True)
        good_results = [
            RAGResult(content="实体A | 类型:人物", source="s1", score=0.8, metadata={}),
            RAGResult(content="实体B | 类型:事件", source="s2", score=0.7, metadata={}),
        ]
        engine.rag_pipeline.retrieve = MagicMock(return_value=good_results)
        engine.rag_pipeline.generate_context = MagicMock(return_value="实体A | 类型:人物\n实体B | 类型:事件")

        result = engine.ask("实体A是什么", user_id="test")
        assert result["dialog_state"] != "waiting_for_clarification"
        assert "clarification_questions" not in result or result.get("clarification_questions") is None


class TestAskStreamClarification:
    """测试 ask_stream() 方法的澄清逻辑"""

    def _make_engine(self):
        engine = QAEngineV2(use_mock=True)
        engine.rag_pipeline.retrieve = MagicMock(return_value=[])
        engine.rag_pipeline.generate_context = MagicMock(return_value="未找到相关信息。")
        return engine

    @pytest.mark.asyncio
    async def test_stream_yields_clarification_event(self):
        engine = self._make_engine()
        events = []
        async for event in engine.ask_stream("模糊问题", user_id="test"):
            events.append(event)

        # 应包含 clarification 类型事件
        clarification_events = [e for e in events if e["type"] == "clarification"]
        assert len(clarification_events) == 1
        assert "questions" in clarification_events[0]["value"]
        assert "reason" in clarification_events[0]["value"]
        assert clarification_events[0]["value"]["reason"] == "no_results"

    @pytest.mark.asyncio
    async def test_stream_end_event_has_clarification_state(self):
        engine = self._make_engine()
        events = []
        async for event in engine.ask_stream("模糊问题", user_id="test"):
            events.append(event)

        end_events = [e for e in events if e["type"] == "end"]
        assert len(end_events) == 1
        assert end_events[0]["value"]["dialog_state"] == "waiting_for_clarification"

    @pytest.mark.asyncio
    async def test_stream_no_content_when_clarification(self):
        """澄清时不应生成 content 事件"""
        engine = self._make_engine()
        events = []
        async for event in engine.ask_stream("模糊问题", user_id="test"):
            events.append(event)

        content_events = [e for e in events if e["type"] == "content"]
        assert len(content_events) == 0

    @pytest.mark.asyncio
    async def test_stream_normal_query_no_clarification(self):
        """正常问题不应触发澄清事件"""
        engine = QAEngineV2(use_mock=True)
        good_results = [
            RAGResult(content="实体A", source="s1", score=0.8, metadata={}),
        ]
        engine.rag_pipeline.retrieve = MagicMock(return_value=good_results)
        engine.rag_pipeline.generate_context = MagicMock(return_value="实体A")

        events = []
        async for event in engine.ask_stream("实体A是什么", user_id="test"):
            events.append(event)

        clarification_events = [e for e in events if e["type"] == "clarification"]
        assert len(clarification_events) == 0
