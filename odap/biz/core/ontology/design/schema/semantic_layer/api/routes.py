from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from pydantic import BaseModel, Field

from ..intent_parser import IntentParser
from ..query_planner import QueryPlanner
from ..disambiguator import Disambiguator

router = APIRouter(prefix="/api/semantic", tags=["semantic_layer"])


class ParseIntentRequest(BaseModel):
    natural_language: str


class PlanTasksRequest(BaseModel):
    intent: str
    entities: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    sort: Optional[str] = None
    limit: int = 20


class AddSynonymRequest(BaseModel):
    canonical: str
    synonym: str


class AddExpansionRuleRequest(BaseModel):
    pattern: str
    expansion: str


_intent_parser: Optional[IntentParser] = None
_query_planner: Optional[QueryPlanner] = None
_disambiguator: Optional[Disambiguator] = None


def _get_intent_parser() -> IntentParser:
    global _intent_parser
    if _intent_parser is None:
        _intent_parser = IntentParser()
    return _intent_parser


def _get_query_planner() -> QueryPlanner:
    global _query_planner
    if _query_planner is None:
        _query_planner = QueryPlanner()
    return _query_planner


def _get_disambiguator() -> Disambiguator:
    global _disambiguator
    if _disambiguator is None:
        _disambiguator = Disambiguator()
    return _disambiguator


@router.post("/parse-intent")
async def parse_intent(request: ParseIntentRequest,
    user=Depends(get_current_user)):
    if not request.natural_language:
        raise HTTPException(status_code=400, detail="natural_language cannot be empty")
    try:
        parser = _get_intent_parser()
        structured = parser.parse(request.natural_language)
        return structured.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan-tasks")
async def plan_tasks(request: PlanTasksRequest,
    user=Depends(get_current_user)):
    try:
        planner = _get_query_planner()
        structured_query = {
            "intent": request.intent,
            "entities": request.entities,
            "filters": request.filters,
            "sort": request.sort,
            "limit": request.limit,
        }
        return planner.plan(structured_query)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/synonyms")
async def get_synonyms(user=Depends(get_current_user)):
    disambiguator = _get_disambiguator()
    return {"synonyms": disambiguator.get_synonyms()}


@router.post("/synonyms")
async def add_synonym(request: AddSynonymRequest,
    user=Depends(get_current_user)):
    try:
        disambiguator = _get_disambiguator()
        return disambiguator.add_synonym(request.canonical, request.synonym)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expansion-rules")
async def get_expansion_rules(user=Depends(get_current_user)):
    disambiguator = _get_disambiguator()
    return {"rules": disambiguator.get_expansion_rules()}


@router.post("/expansion-rules")
async def add_expansion_rule(request: AddExpansionRuleRequest,
    user=Depends(get_current_user)):
    try:
        disambiguator = _get_disambiguator()
        return disambiguator.add_expansion_rule(request.pattern, request.expansion)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
