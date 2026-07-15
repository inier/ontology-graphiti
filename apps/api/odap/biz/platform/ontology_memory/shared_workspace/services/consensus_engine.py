from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ConsensusStrategy(str, Enum):
    MAJORITY = "majority"
    UNANIMOUS = "unanimous"
    WEIGHTED = "weighted"
    SUPERMAJORITY = "supermajority"


class ConflictResolutionStrategy(str, Enum):
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    HIGHEST_PRIORITY = "highest_priority"
    MERGE = "merge"


@dataclass
class Vote:
    voter_id: str
    vote_value: Any
    weight: float = 1.0
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConsensusProposal:
    proposal_id: str
    proposer_id: str
    topic: str
    proposed_value: Any
    strategy: ConsensusStrategy
    votes: List[Vote] = field(default_factory=list)
    status: str = "pending"
    result: Any = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    deadline: Optional[str] = None
    min_votes: int = 1


class ConsensusEngine:
    _instance: Optional["ConsensusEngine"] = None

    @classmethod
    def get_instance(cls) -> "ConsensusEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    def __init__(self):
        self._proposals: Dict[str, ConsensusProposal] = {}

    def create_proposal(self, proposal_id: str, proposer_id: str, topic: str,
                         proposed_value: Any,
                         strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY,
                         min_votes: int = 1,
                         deadline: Optional[str] = None) -> Dict[str, Any]:
        proposal = ConsensusProposal(
            proposal_id=proposal_id, proposer_id=proposer_id,
            topic=topic, proposed_value=proposed_value,
            strategy=strategy, min_votes=min_votes, deadline=deadline,
        )
        self._proposals[proposal_id] = proposal
        return {"status": "success", "proposal_id": proposal_id, "strategy": strategy.value}

    def cast_vote(self, proposal_id: str, voter_id: str, vote_value: Any,
                   weight: float = 1.0, reason: str = "") -> Dict[str, Any]:
        if proposal_id not in self._proposals:
            return {"status": "error", "message": "Proposal not found"}
        proposal = self._proposals[proposal_id]
        if proposal.status != "pending":
            return {"status": "error", "message": "Proposal already resolved"}
        for existing in proposal.votes:
            if existing.voter_id == voter_id:
                return {"status": "error", "message": "Already voted"}
        vote = Vote(voter_id=voter_id, vote_value=vote_value, weight=weight, reason=reason)
        proposal.votes.append(vote)
        if len(proposal.votes) >= proposal.min_votes:
            self._try_resolve(proposal_id)
        return {"status": "success", "proposal_id": proposal_id, "votes_count": len(proposal.votes)}

    def resolve_proposal(self, proposal_id: str) -> Dict[str, Any]:
        if proposal_id not in self._proposals:
            return {"status": "error", "message": "Proposal not found"}
        return self._try_resolve(proposal_id)

    def get_proposal(self, proposal_id: str) -> Dict[str, Any]:
        if proposal_id not in self._proposals:
            return {"status": "error", "message": "Proposal not found"}
        p = self._proposals[proposal_id]
        return {
            "status": "success", "proposal_id": p.proposal_id,
            "proposer_id": p.proposer_id, "topic": p.topic,
            "proposed_value": p.proposed_value,
            "strategy": p.strategy.value,
            "votes": [
                {"voter_id": v.voter_id, "vote_value": v.vote_value,
                 "weight": v.weight, "reason": v.reason}
                for v in p.votes
            ],
            "status_field": p.status, "result": p.result, "min_votes": p.min_votes,
        }

    def list_proposals(self, status: Optional[str] = None) -> Dict[str, Any]:
        proposals = list(self._proposals.values())
        if status:
            proposals = [p for p in proposals if p.status == status]
        return {
            "status": "success", "proposals": [
                {"proposal_id": p.proposal_id, "topic": p.topic,
                 "status": p.status, "votes_count": len(p.votes)}
                for p in proposals
            ],
        }

    def resolve_conflict(self, topic: str, values: List[Dict[str, Any]],
                          strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITE_WINS) -> Dict[str, Any]:
        if not values:
            return {"status": "error", "message": "No values to resolve"}
        if strategy == ConflictResolutionStrategy.LAST_WRITE_WINS:
            resolved = max(values, key=lambda v: v.get("timestamp", ""))
        elif strategy == ConflictResolutionStrategy.FIRST_WRITE_WINS:
            resolved = min(values, key=lambda v: v.get("timestamp", ""))
        elif strategy == ConflictResolutionStrategy.HIGHEST_PRIORITY:
            resolved = max(values, key=lambda v: v.get("priority", 0))
        elif strategy == ConflictResolutionStrategy.MERGE:
            merged = {}
            for v in sorted(values, key=lambda x: x.get("timestamp", "")):
                merged.update(v.get("data", {}))
            resolved = {"data": merged, "timestamp": datetime.now().isoformat()}
        else:
            resolved = values[0]
        return {
            "status": "success", "topic": topic,
            "strategy": strategy.value, "resolved_value": resolved,
            "conflicting_count": len(values),
        }

    def _try_resolve(self, proposal_id: str) -> Dict[str, Any]:
        proposal = self._proposals[proposal_id]
        if proposal.status != "pending":
            return {"status": "already_resolved", "result": proposal.result}
        strategy = proposal.strategy
        votes = proposal.votes
        if not votes:
            return {"status": "pending", "message": "No votes yet"}
        if strategy == ConsensusStrategy.MAJORITY:
            yes_count = sum(1 for v in votes if v.vote_value in (True, "yes", "approve"))
            if yes_count > len(votes) / 2:
                proposal.status = "approved"
                proposal.result = proposal.proposed_value
            elif len(votes) - yes_count > len(votes) / 2:
                proposal.status = "rejected"
                proposal.result = None
        elif strategy == ConsensusStrategy.UNANIMOUS:
            if all(v.vote_value in (True, "yes", "approve") for v in votes):
                proposal.status = "approved"
                proposal.result = proposal.proposed_value
            elif any(v.vote_value in (False, "no", "reject") for v in votes):
                proposal.status = "rejected"
                proposal.result = None
        elif strategy == ConsensusStrategy.WEIGHTED:
            weighted_yes = sum(v.weight for v in votes if v.vote_value in (True, "yes", "approve"))
            weighted_no = sum(v.weight for v in votes if v.vote_value in (False, "no", "reject"))
            if weighted_yes > weighted_no:
                proposal.status = "approved"
                proposal.result = proposal.proposed_value
            elif weighted_no > weighted_yes:
                proposal.status = "rejected"
                proposal.result = None
        elif strategy == ConsensusStrategy.SUPERMAJORITY:
            yes_count = sum(1 for v in votes if v.vote_value in (True, "yes", "approve"))
            if yes_count >= len(votes) * 2 / 3:
                proposal.status = "approved"
                proposal.result = proposal.proposed_value
            elif len(votes) - yes_count >= len(votes) * 2 / 3:
                proposal.status = "rejected"
                proposal.result = None
        if proposal.status == "pending" and proposal.deadline:
            try:
                if datetime.now().isoformat() > proposal.deadline:
                    proposal.status = "expired"
                    proposal.result = None
            except Exception:
                pass
        return {
            "status": "success", "proposal_id": proposal_id,
            "consensus_status": proposal.status, "result": proposal.result,
        }
