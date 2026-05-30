import pytest
from datetime import datetime

from odap.biz.platform.ontology_memory.shared_workspace.services.consensus_engine import (
    ConsensusEngine, ConsensusStrategy, ConflictResolutionStrategy,
    ConsensusProposal, Vote,
)


class TestConsensusStrategy:
    def test_strategy_values(self):
        assert ConsensusStrategy.MAJORITY.value == "majority"
        assert ConsensusStrategy.UNANIMOUS.value == "unanimous"
        assert ConsensusStrategy.WEIGHTED.value == "weighted"
        assert ConsensusStrategy.SUPERMAJORITY.value == "supermajority"

    def test_conflict_strategy_values(self):
        assert ConflictResolutionStrategy.LAST_WRITE_WINS.value == "last_write_wins"
        assert ConflictResolutionStrategy.FIRST_WRITE_WINS.value == "first_write_wins"
        assert ConflictResolutionStrategy.HIGHEST_PRIORITY.value == "highest_priority"
        assert ConflictResolutionStrategy.MERGE.value == "merge"


class TestConsensusEngine:
    def setup_method(self):
        ConsensusEngine.reset_instance()

    def teardown_method(self):
        ConsensusEngine.reset_instance()

    def test_create_proposal(self):
        engine = ConsensusEngine()
        result = engine.create_proposal("p1", "user1", "topic1", "value1")
        assert result["status"] == "success"
        assert result["proposal_id"] == "p1"

    def test_get_proposal(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1")
        result = engine.get_proposal("p1")
        assert result["status"] == "success"
        assert result["topic"] == "topic1"
        assert result["proposer_id"] == "user1"

    def test_get_proposal_not_found(self):
        engine = ConsensusEngine()
        result = engine.get_proposal("nonexistent")
        assert result["status"] == "error"

    def test_cast_vote(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1", min_votes=3)
        result = engine.cast_vote("p1", "voter1", True)
        assert result["status"] == "success"
        assert result["votes_count"] == 1

    def test_cast_vote_proposal_not_found(self):
        engine = ConsensusEngine()
        result = engine.cast_vote("nonexistent", "voter1", True)
        assert result["status"] == "error"

    def test_cast_vote_already_voted(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1", min_votes=5)
        engine.cast_vote("p1", "voter1", True)
        result = engine.cast_vote("p1", "voter1", True)
        assert result["status"] == "error"
        assert "Already voted" in result["message"]

    def test_majority_approval(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1",
                               strategy=ConsensusStrategy.MAJORITY, min_votes=3)
        engine.cast_vote("p1", "v1", True)
        engine.cast_vote("p1", "v2", True)
        result = engine.cast_vote("p1", "v3", False)
        proposal = engine.get_proposal("p1")
        assert proposal["status_field"] == "approved"

    def test_majority_rejection(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1",
                               strategy=ConsensusStrategy.MAJORITY, min_votes=3)
        engine.cast_vote("p1", "v1", False)
        engine.cast_vote("p1", "v2", False)
        engine.cast_vote("p1", "v3", True)
        proposal = engine.get_proposal("p1")
        assert proposal["status_field"] == "rejected"

    def test_unanimous_approval(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1",
                               strategy=ConsensusStrategy.UNANIMOUS, min_votes=2)
        engine.cast_vote("p1", "v1", True)
        engine.cast_vote("p1", "v2", "yes")
        proposal = engine.get_proposal("p1")
        assert proposal["status_field"] == "approved"

    def test_unanimous_rejection(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1",
                               strategy=ConsensusStrategy.UNANIMOUS, min_votes=2)
        engine.cast_vote("p1", "v1", True)
        engine.cast_vote("p1", "v2", False)
        proposal = engine.get_proposal("p1")
        assert proposal["status_field"] == "rejected"

    def test_weighted_approval(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1",
                               strategy=ConsensusStrategy.WEIGHTED, min_votes=2)
        engine.cast_vote("p1", "v1", True, weight=3.0)
        engine.cast_vote("p1", "v2", False, weight=1.0)
        proposal = engine.get_proposal("p1")
        assert proposal["status_field"] == "approved"

    def test_supermajority_approval(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1",
                               strategy=ConsensusStrategy.SUPERMAJORITY, min_votes=3)
        engine.cast_vote("p1", "v1", True)
        engine.cast_vote("p1", "v2", True)
        engine.cast_vote("p1", "v3", True)
        proposal = engine.get_proposal("p1")
        assert proposal["status_field"] == "approved"

    def test_supermajority_rejection(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1",
                               strategy=ConsensusStrategy.SUPERMAJORITY, min_votes=3)
        engine.cast_vote("p1", "v1", True)
        engine.cast_vote("p1", "v2", False)
        engine.cast_vote("p1", "v3", False)
        proposal = engine.get_proposal("p1")
        assert proposal["status_field"] == "rejected"

    def test_list_proposals(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1")
        engine.create_proposal("p2", "user2", "topic2", "value2")
        result = engine.list_proposals()
        assert result["status"] == "success"
        assert len(result["proposals"]) == 2

    def test_list_proposals_by_status(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1", min_votes=1)
        engine.cast_vote("p1", "v1", True)
        engine.create_proposal("p2", "user2", "topic2", "value2", min_votes=5)
        result = engine.list_proposals(status="pending")
        assert result["status"] == "success"
        assert len(result["proposals"]) == 1
        assert result["proposals"][0]["proposal_id"] == "p2"

    def test_resolve_proposal_already_resolved(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1", min_votes=1)
        engine.cast_vote("p1", "v1", True)
        result = engine.resolve_proposal("p1")
        assert result["status"] == "already_resolved"

    def test_resolve_proposal_not_found(self):
        engine = ConsensusEngine()
        result = engine.resolve_proposal("nonexistent")
        assert result["status"] == "error"

    def test_cast_vote_on_resolved_proposal(self):
        engine = ConsensusEngine()
        engine.create_proposal("p1", "user1", "topic1", "value1", min_votes=1)
        engine.cast_vote("p1", "v1", True)
        result = engine.cast_vote("p1", "v2", True)
        assert result["status"] == "error"
        assert "already resolved" in result["message"]


class TestConflictResolution:
    def setup_method(self):
        ConsensusEngine.reset_instance()

    def teardown_method(self):
        ConsensusEngine.reset_instance()

    def test_last_write_wins(self):
        engine = ConsensusEngine()
        values = [
            {"data": "old", "timestamp": "2025-01-01T00:00:00"},
            {"data": "new", "timestamp": "2025-06-01T00:00:00"},
        ]
        result = engine.resolve_conflict("topic1", values, ConflictResolutionStrategy.LAST_WRITE_WINS)
        assert result["status"] == "success"
        assert result["resolved_value"]["data"] == "new"

    def test_first_write_wins(self):
        engine = ConsensusEngine()
        values = [
            {"data": "old", "timestamp": "2025-01-01T00:00:00"},
            {"data": "new", "timestamp": "2025-06-01T00:00:00"},
        ]
        result = engine.resolve_conflict("topic1", values, ConflictResolutionStrategy.FIRST_WRITE_WINS)
        assert result["status"] == "success"
        assert result["resolved_value"]["data"] == "old"

    def test_highest_priority(self):
        engine = ConsensusEngine()
        values = [
            {"data": "low", "priority": 1},
            {"data": "high", "priority": 10},
        ]
        result = engine.resolve_conflict("topic1", values, ConflictResolutionStrategy.HIGHEST_PRIORITY)
        assert result["status"] == "success"
        assert result["resolved_value"]["data"] == "high"

    def test_merge_strategy(self):
        engine = ConsensusEngine()
        values = [
            {"data": {"a": 1}, "timestamp": "2025-01-01T00:00:00"},
            {"data": {"b": 2}, "timestamp": "2025-06-01T00:00:00"},
        ]
        result = engine.resolve_conflict("topic1", values, ConflictResolutionStrategy.MERGE)
        assert result["status"] == "success"
        assert result["resolved_value"]["data"] == {"a": 1, "b": 2}

    def test_empty_values(self):
        engine = ConsensusEngine()
        result = engine.resolve_conflict("topic1", [])
        assert result["status"] == "error"

    def test_conflicting_count(self):
        engine = ConsensusEngine()
        values = [
            {"data": "v1", "timestamp": "2025-01-01T00:00:00"},
            {"data": "v2", "timestamp": "2025-06-01T00:00:00"},
            {"data": "v3", "timestamp": "2025-03-01T00:00:00"},
        ]
        result = engine.resolve_conflict("topic1", values, ConflictResolutionStrategy.LAST_WRITE_WINS)
        assert result["conflicting_count"] == 3
