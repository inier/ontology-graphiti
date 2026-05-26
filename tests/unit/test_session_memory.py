import pytest
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.platform.session_memory.context_window import ContextWindow, ChatMessage, MessageRole
from odap.biz.platform.session_memory.memory_compactor import MemoryCompactor
from odap.biz.platform.session_memory.cot_builder import CoTBuilder, CoTNodeType
from odap.biz.platform.session_memory.session_store import SessionStore, Session


class TestContextWindow:
    def test_add_message(self):
        cw = ContextWindow(max_tokens=1000)
        msg = ChatMessage(role=MessageRole.USER, content="Hello", tokens=10)
        assert cw.add_message(msg)
        assert len(cw.messages) == 1
        assert cw.used_tokens == 10

    def test_available_tokens(self):
        cw = ContextWindow(max_tokens=1000, system_prompt_tokens=100)
        msg = ChatMessage(role=MessageRole.USER, content="Hello", tokens=50)
        cw.add_message(msg)
        assert cw.available_tokens == 850

    def test_usage_ratio(self):
        cw = ContextWindow(max_tokens=1000, system_prompt_tokens=200)
        msg = ChatMessage(role=MessageRole.USER, content="Hello", tokens=300)
        cw.add_message(msg)
        assert abs(cw.usage_ratio - 0.5) < 0.01

    def test_exceed_capacity(self):
        cw = ContextWindow(max_tokens=100)
        msg = ChatMessage(role=MessageRole.USER, content="Big", tokens=200)
        assert not cw.add_message(msg)

    def test_remove_oldest(self):
        cw = ContextWindow(max_tokens=1000)
        for i in range(5):
            cw.add_message(ChatMessage(role=MessageRole.USER, content=f"Msg {i}", tokens=10))
        removed = cw.remove_oldest(2)
        assert len(removed) == 2
        assert len(cw.messages) == 3

    def test_get_recent(self):
        cw = ContextWindow(max_tokens=1000)
        for i in range(10):
            cw.add_message(ChatMessage(role=MessageRole.USER, content=f"Msg {i}", tokens=10))
        recent = cw.get_recent(4)
        assert len(recent) == 4

    def test_clear(self):
        cw = ContextWindow(max_tokens=1000)
        cw.add_message(ChatMessage(role=MessageRole.USER, content="Hello", tokens=10))
        cw.summary = "Old summary"
        cw.clear()
        assert len(cw.messages) == 0
        assert cw.summary == ""

    def test_to_dict(self):
        cw = ContextWindow(max_tokens=1000, system_prompt_tokens=100)
        cw.add_message(ChatMessage(role=MessageRole.USER, content="Hello", tokens=50))
        d = cw.to_dict()
        assert d["max_tokens"] == 1000
        assert d["used_tokens"] == 50
        assert d["message_count"] == 1


class TestMemoryCompactor:
    def test_should_compact_below_threshold(self):
        cw = ContextWindow(max_tokens=1000)
        cw.add_message(ChatMessage(role=MessageRole.USER, content="Hello", tokens=100))
        compactor = MemoryCompactor()
        assert not compactor.should_compact(cw)

    def test_should_compact_above_threshold(self):
        cw = ContextWindow(max_tokens=1000)
        cw.add_message(ChatMessage(role=MessageRole.USER, content="Big", tokens=800))
        compactor = MemoryCompactor()
        assert compactor.should_compact(cw)

    def test_compact_preserves_recent(self):
        cw = ContextWindow(max_tokens=10000)
        for i in range(10):
            cw.add_message(ChatMessage(role=MessageRole.USER, content=f"Message {i}", tokens=100))

        compactor = MemoryCompactor()
        compacted = asyncio.run(compactor.compact(cw))
        assert len(compacted.messages) == 4
        assert compacted.summary != ""

    def test_compact_no_compact_needed(self):
        cw = ContextWindow(max_tokens=10000)
        cw.add_message(ChatMessage(role=MessageRole.USER, content="Hello", tokens=50))
        compactor = MemoryCompactor()
        compacted = asyncio.run(compactor.compact(cw))
        assert len(compacted.messages) == 1


class TestCoTBuilder:
    def test_start(self):
        builder = CoTBuilder()
        root = builder.start("报告态势")
        assert root.type == CoTNodeType.INTENT
        assert root.status == "done"
        assert "报告态势" in root.detail

    def test_add_child(self):
        builder = CoTBuilder()
        root = builder.start("查询")
        child = builder.add_child(root, CoTNodeType.ENTITY_LINK, "实体链接", "匹配3个实体")
        assert child.parent_id == root.id
        assert child.id in root.children_ids

    def test_update_status(self):
        builder = CoTBuilder()
        root = builder.start("查询")
        builder.update_status(root.id, "running", detail="Processing")
        assert builder.get_node(root.id).status == "running"

    def test_timing(self):
        builder = CoTBuilder()
        root = builder.start("查询")
        child = builder.add_child(root, CoTNodeType.LLM_INFER, "LLM推理")
        builder.start_timing(child.id)
        builder.finish_timing(child.id)
        node = builder.get_node(child.id)
        assert node.timing is not None
        assert node.timing.duration_ms is not None
        assert node.timing.duration_ms >= 0

    def test_path_to_root(self):
        builder = CoTBuilder()
        root = builder.start("查询")
        child1 = builder.add_child(root, CoTNodeType.ENTITY_LINK, "实体链接")
        child2 = builder.add_child(child1, CoTNodeType.RAG_AUGMENT, "RAG增强")
        path = builder.get_path_to_root(child2.id)
        assert len(path) == 3

    def test_to_serializable(self):
        builder = CoTBuilder()
        root = builder.start("查询")
        builder.add_child(root, CoTNodeType.ENTITY_LINK, "实体链接")
        data = builder.to_serializable()
        assert "rootId" in data
        assert "nodes" in data
        assert len(data["nodes"]) == 2


class TestSessionStore:
    @pytest.fixture
    def store(self, tmp_path):
        return SessionStore(db_path=str(tmp_path / "test_sessions.db"))

    def test_save_and_load(self, store):
        session = Session(workspace_id="ws1", title="Test Session")
        session.messages.append(ChatMessage(role=MessageRole.USER, content="Hello", tokens=10))
        sid = store.save_session(session)
        loaded = store.load_session(sid)
        assert loaded is not None
        assert loaded.title == "Test Session"
        assert len(loaded.messages) == 1

    def test_list_sessions(self, store):
        for i in range(3):
            store.save_session(Session(workspace_id="ws1", title=f"Session {i}"))
        summaries = store.list_sessions("ws1")
        assert len(summaries) == 3

    def test_delete_session(self, store):
        session = Session(workspace_id="ws1", title="To Delete")
        sid = store.save_session(session)
        assert store.delete_session(sid)
        summaries = store.list_sessions("ws1")
        assert len(summaries) == 0

    def test_load_nonexistent(self, store):
        assert store.load_session("nonexistent") is None
