import pytest
import os
import json
from datetime import datetime


def _make_thought_storage(tmp_path):
    from odap.biz.core.cognition.thought_graph.storage import ThoughtGraphStorage
    db_path = str(tmp_path / "test_thought.db")
    return ThoughtGraphStorage(db_path=db_path)


def _make_thought_node(**overrides):
    from odap.infra.graph.thought_graph import ThoughtNode, ThoughtType, ReasoningMethod
    defaults = {
        "thought_type": ThoughtType.OBSERVATION,
        "content": "test thought content",
        "premises": ["premise1"],
        "conclusion": "test conclusion",
        "confidence": 0.8,
        "reasoning_method": ReasoningMethod.DEDUCTIVE,
        "source_entity_ids": ["entity-1"],
        "source_scenario_id": "scenario-1",
        "agent_id": "agent-1",
    }
    defaults.update(overrides)
    return ThoughtNode(**defaults)


class TestThoughtGraphStorage:
    def test_init_db(self, tmp_path):
        storage = _make_thought_storage(tmp_path)
        assert os.path.exists(storage.db_path)

    def test_thought_crud(self, tmp_path):
        storage = _make_thought_storage(tmp_path)
        thought = _make_thought_node(thought_id="thought-test-001")
        saved = storage.save_thought(thought)
        assert saved.thought_id == "thought-test-001"

        fetched = storage.get_thought("thought-test-001")
        assert fetched is not None
        assert fetched.content == "test thought content"
        assert fetched.thought_type.value == "observation"
        assert fetched.confidence == 0.8
        assert fetched.premises == ["premise1"]
        assert fetched.source_entity_ids == ["entity-1"]

        assert storage.get_thought("nonexistent") is None

        result = storage.delete_thought("thought-test-001")
        assert result is True

        result = storage.delete_thought("thought-test-001")
        assert result is False

        assert storage.get_thought("thought-test-001") is None

    def test_list_thoughts_with_filters(self, tmp_path):
        storage = _make_thought_storage(tmp_path)
        from odap.infra.graph.thought_graph import ThoughtType
        t1 = _make_thought_node(thought_id="t1", thought_type=ThoughtType.OBSERVATION, source_scenario_id="sc-1")
        t2 = _make_thought_node(thought_id="t2", thought_type=ThoughtType.INFERENCE, source_scenario_id="sc-1")
        t3 = _make_thought_node(thought_id="t3", thought_type=ThoughtType.INFERENCE, source_scenario_id="sc-2")
        storage.save_thought(t1)
        storage.save_thought(t2)
        storage.save_thought(t3)

        all_thoughts = storage.list_thoughts()
        assert len(all_thoughts) == 3

        inference_only = storage.list_thoughts(thought_type=ThoughtType.INFERENCE)
        assert len(inference_only) == 2

        sc1_only = storage.list_thoughts(scenario_id="sc-1")
        assert len(sc1_only) == 2

        filtered = storage.list_thoughts(thought_type=ThoughtType.INFERENCE, scenario_id="sc-1")
        assert len(filtered) == 1

    def test_chain_crud(self, tmp_path):
        storage = _make_thought_storage(tmp_path)
        from odap.infra.graph.thought_graph import ReasoningChain
        chain = ReasoningChain(
            chain_id="chain-test-001",
            name="Test Chain",
            description="A test reasoning chain",
            thought_ids=["t1", "t2", "t3"],
            chain_type="sequential",
            scenario_id="sc-1"
        )
        saved = storage.save_chain(chain)
        assert saved.chain_id == "chain-test-001"

        fetched = storage.get_chain("chain-test-001")
        assert fetched is not None
        assert fetched.name == "Test Chain"
        assert fetched.thought_ids == ["t1", "t2", "t3"]

        assert storage.get_chain("nonexistent") is None

        chains = storage.list_chains(scenario_id="sc-1")
        assert len(chains) >= 1

        result = storage.delete_chain("chain-test-001")
        assert result is True

        result = storage.delete_chain("chain-test-001")
        assert result is False

    def test_thought_edges(self, tmp_path):
        storage = _make_thought_storage(tmp_path)
        t1 = _make_thought_node(thought_id="t-edge-1")
        t2 = _make_thought_node(thought_id="t-edge-2")
        storage.save_thought(t1)
        storage.save_thought(t2)

        edge = storage.add_thought_edge("t-edge-1", "t-edge-2", edge_type="leads_to", weight=0.9)
        assert edge["source"] == "t-edge-1"
        assert edge["target"] == "t-edge-2"
        assert edge["edge_type"] == "leads_to"

        edges = storage.get_thought_edges("t-edge-1")
        assert len(edges) >= 1

        edges_both = storage.get_thought_edges("t-edge-1", direction="both")
        assert len(edges_both) >= 1

    def test_delete_thought_removes_edges(self, tmp_path):
        storage = _make_thought_storage(tmp_path)
        t1 = _make_thought_node(thought_id="t-del-1")
        t2 = _make_thought_node(thought_id="t-del-2")
        storage.save_thought(t1)
        storage.save_thought(t2)
        storage.add_thought_edge("t-del-1", "t-del-2")

        storage.delete_thought("t-del-1")
        edges = storage.get_thought_edges("t-del-2")
        assert len(edges) == 0

    def test_json_field_serialization(self, tmp_path):
        storage = _make_thought_storage(tmp_path)
        thought = _make_thought_node(
            thought_id="t-json-1",
            premises=["p1", "p2"],
            source_entity_ids=["e1", "e2"],
            metadata={"key": "value", "nested": {"a": 1}}
        )
        storage.save_thought(thought)
        fetched = storage.get_thought("t-json-1")
        assert fetched.premises == ["p1", "p2"]
        assert fetched.source_entity_ids == ["e1", "e2"]
        assert fetched.metadata["key"] == "value"


class TestThoughtGraphService:
    def _make_service(self, tmp_path):
        from odap.biz.core.cognition.thought_graph.storage import ThoughtGraphStorage
        from odap.infra.graph.thought_graph import ThoughtGraphService
        storage = ThoughtGraphStorage(db_path=str(tmp_path / "test_svc.db"))
        ThoughtGraphService._instance = None
        return ThoughtGraphService(storage=storage)

    def test_add_thought(self, tmp_path):
        svc = self._make_service(tmp_path)
        result = svc.add_thought(
            thought_type="observation",
            content="observed something",
            confidence=0.9,
            reasoning_method="deductive"
        )
        assert result["status"] == "success"
        assert result["thought_type"] == "observation"
        assert result["confidence"] == 0.9

    def test_get_thought(self, tmp_path):
        svc = self._make_service(tmp_path)
        created = svc.add_thought(thought_type="inference", content="inferred something")
        thought_id = created["thought_id"]

        result = svc.get_thought(thought_id)
        assert result["status"] == "success"
        assert result["content"] == "inferred something"

        result = svc.get_thought("nonexistent")
        assert result["status"] == "error"

    def test_list_thoughts(self, tmp_path):
        svc = self._make_service(tmp_path)
        svc.add_thought(thought_type="observation", content="obs 1")
        svc.add_thought(thought_type="inference", content="inf 1")

        result = svc.list_thoughts()
        assert result["status"] == "success"
        assert result["count"] == 2

    def test_delete_thought(self, tmp_path):
        svc = self._make_service(tmp_path)
        created = svc.add_thought(thought_type="hypothesis", content="hyp 1")
        result = svc.delete_thought(created["thought_id"])
        assert result["status"] == "success"

        result = svc.delete_thought("nonexistent")
        assert result["status"] == "error"

    def test_create_reasoning_chain(self, tmp_path):
        svc = self._make_service(tmp_path)
        t1 = svc.add_thought(thought_type="observation", content="obs")
        t2 = svc.add_thought(thought_type="inference", content="inf")
        result = svc.create_reasoning_chain(
            name="Test Chain",
            thought_ids=[t1["thought_id"], t2["thought_id"]],
            scenario_id="sc-1"
        )
        assert result["status"] == "success"
        assert result["thought_count"] == 2

    def test_get_chain(self, tmp_path):
        svc = self._make_service(tmp_path)
        t1 = svc.add_thought(thought_type="observation", content="obs")
        created = svc.create_reasoning_chain(name="Chain", thought_ids=[t1["thought_id"]])
        chain_id = created["chain_id"]

        result = svc.get_chain(chain_id)
        assert result["status"] == "success"
        assert result["name"] == "Chain"

        result = svc.get_chain("nonexistent")
        assert result["status"] == "error"

    def test_list_chains(self, tmp_path):
        svc = self._make_service(tmp_path)
        svc.create_reasoning_chain(name="Chain 1")
        svc.create_reasoning_chain(name="Chain 2")
        result = svc.list_chains()
        assert result["status"] == "success"
        assert result["count"] == 2

    def test_delete_chain(self, tmp_path):
        svc = self._make_service(tmp_path)
        created = svc.create_reasoning_chain(name="Chain")
        result = svc.delete_chain(created["chain_id"])
        assert result["status"] == "success"

        result = svc.delete_chain("nonexistent")
        assert result["status"] == "error"

    def test_link_thoughts(self, tmp_path):
        svc = self._make_service(tmp_path)
        t1 = svc.add_thought(thought_type="observation", content="obs")
        t2 = svc.add_thought(thought_type="inference", content="inf")
        result = svc.link_thoughts(t1["thought_id"], t2["thought_id"], edge_type="supports", weight=0.8)
        assert result["status"] == "success"
        assert result["edge_type"] == "supports"

    def test_get_thought_graph(self, tmp_path):
        svc = self._make_service(tmp_path)
        t1 = svc.add_thought(thought_type="observation", content="obs")
        t2 = svc.add_thought(thought_type="inference", content="inf")
        svc.link_thoughts(t1["thought_id"], t2["thought_id"])

        result = svc.get_thought_graph(t1["thought_id"], depth=2)
        assert result["status"] == "success"
        assert len(result["nodes"]) >= 1
        assert len(result["edges"]) >= 1

    def test_enum_type_conversion(self, tmp_path):
        svc = self._make_service(tmp_path)
        from odap.infra.graph.thought_graph import ThoughtType, ReasoningMethod
        result = svc.add_thought(
            thought_type=ThoughtType.DECISION,
            content="decided",
            reasoning_method=ReasoningMethod.ABDUCTIVE
        )
        assert result["thought_type"] == "decision"

        fetched = svc.get_thought(result["thought_id"])
        assert fetched["reasoning_method"] == "abductive"


class TestThoughtModels:
    def test_thought_type_enum(self):
        from odap.infra.graph.thought_graph import ThoughtType
        assert ThoughtType.OBSERVATION.value == "observation"
        assert ThoughtType.INFERENCE.value == "inference"
        assert ThoughtType("hypothesis") == ThoughtType.HYPOTHESIS

    def test_reasoning_method_enum(self):
        from odap.infra.graph.thought_graph import ReasoningMethod
        assert ReasoningMethod.DEDUCTIVE.value == "deductive"
        assert ReasoningMethod("abductive") == ReasoningMethod.ABDUCTIVE

    def test_thought_node_defaults(self):
        from odap.infra.graph.thought_graph import ThoughtNode
        node = ThoughtNode()
        assert node.thought_id.startswith("thought-")
        assert node.confidence == 0.5
        assert node.premises == []
        assert node.source_entity_ids == []
        assert node.metadata == {}

    def test_reasoning_chain_defaults(self):
        from odap.infra.graph.thought_graph import ReasoningChain
        chain = ReasoningChain()
        assert chain.chain_id.startswith("chain-")
        assert chain.thought_ids == []
        assert chain.chain_type == "sequential"
