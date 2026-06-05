from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, List, Optional

from odap.web.api.response_models import DictResponse

from ..services.consensus_engine import ConsensusEngine, ConsensusStrategy, ConflictResolutionStrategy

ConsensusStrategyEnum = ConsensusStrategy
ConflictStrategyEnum = ConflictResolutionStrategy

router = APIRouter(prefix="/api/ontology-memory/consensus", tags=["ontology-memory-consensus"])


class CreateProposalRequest(BaseModel):
    proposal_id: str = Field(..., min_length=1)
    proposer_id: str = Field(..., min_length=1)
    topic: str = Field(..., min_length=1)
    proposed_value: Any
    strategy: ConsensusStrategyEnum = ConsensusStrategyEnum.MAJORITY
    min_votes: int = 1
    deadline: Optional[str] = None


class CastVoteRequest(BaseModel):
    voter_id: str = Field(..., min_length=1)
    vote_value: Any
    weight: float = 1.0
    reason: str = ""


class ResolveConflictRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    values: List[dict] = Field(..., min_length=1)
    strategy: ConflictStrategyEnum = ConflictStrategyEnum.LAST_WRITE_WINS


@router.post("/proposals", response_model=DictResponse)
async def create_proposal(request: CreateProposalRequest):
    try:
        engine = ConsensusEngine.get_instance()
        result = engine.create_proposal(
            proposal_id=request.proposal_id,
            proposer_id=request.proposer_id,
            topic=request.topic,
            proposed_value=request.proposed_value,
            strategy=ConsensusStrategy(request.strategy.value),
            min_votes=request.min_votes,
            deadline=request.deadline,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/vote", response_model=DictResponse)
async def cast_vote(proposal_id: str, request: CastVoteRequest):
    try:
        engine = ConsensusEngine.get_instance()
        result = engine.cast_vote(
            proposal_id=proposal_id,
            voter_id=request.voter_id,
            vote_value=request.vote_value,
            weight=request.weight,
            reason=request.reason,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/resolve", response_model=DictResponse)
async def resolve_proposal(proposal_id: str):
    try:
        engine = ConsensusEngine.get_instance()
        result = engine.resolve_proposal(proposal_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proposals/{proposal_id}", response_model=DictResponse)
async def get_proposal(proposal_id: str):
    try:
        engine = ConsensusEngine.get_instance()
        result = engine.get_proposal(proposal_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proposals", response_model=DictResponse)
async def list_proposals(status: Optional[str] = None):
    try:
        engine = ConsensusEngine.get_instance()
        return engine.list_proposals(status=status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conflicts/resolve", response_model=DictResponse)
async def resolve_conflict(request: ResolveConflictRequest):
    try:
        engine = ConsensusEngine.get_instance()
        result = engine.resolve_conflict(
            topic=request.topic,
            values=request.values,
            strategy=ConflictResolutionStrategy(request.strategy.value),
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
