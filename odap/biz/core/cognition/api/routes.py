from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from odap.biz.core.cognition.user_cognition_engine import (
    UserCognitionEngine,
    get_cognition_engine,
    RoleType,
)


class IntentRequest(BaseModel):
    input_text: str
    role: str = "guest"


class IntentResponse(BaseModel):
    intent: Dict[str, Any] = Field(default_factory=dict)
    knowledge_results: List[Dict[str, Any]] = Field(default_factory=list)
    session_id: Optional[str] = None


class ViewResponse(BaseModel):
    view_id: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    layout_config: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)


class NavigateRequest(BaseModel):
    entity_id: str
    direction: str = "outbound"


class NavigateResponse(BaseModel):
    entity_id: str
    navigation_path: List[str] = Field(default_factory=list)
    related_entities: List[Dict[str, Any]] = Field(default_factory=list)
    entity_context: Dict[str, Any] = Field(default_factory=dict)


class ExplainRequest(BaseModel):
    decision_id: str
    context: Dict[str, Any] = Field(default_factory=dict)


class ExplainResponse(BaseModel):
    explanation_id: str
    query: str
    answer: str
    confidence: float
    reasoning_chain: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)


router = APIRouter(prefix="/api/cognition", tags=["cognition"])


@router.post("/intent", response_model=IntentResponse)
async def recognize_intent(request: IntentRequest):
    if not request.input_text:
        raise HTTPException(status_code=400, detail="input_text 不能为空")
    try:
        try:
            role = RoleType(request.role)
        except ValueError:
            role = RoleType.GUEST

        cognition_engine = get_cognition_engine()
        result = cognition_engine.process_query(request.input_text, "anonymous", role)

        return IntentResponse(
            intent=result.get("intent", {}),
            knowledge_results=result.get("knowledge_results", []),
            session_id=result.get("session_id"),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"认知引擎不可用: {str(e)}")


@router.get("/view", response_model=ViewResponse)
async def get_role_view(role: str = Query(...)):
    try:
        try:
            role_type = RoleType(role)
        except ValueError:
            role_type = RoleType.GUEST

        cognition_engine = get_cognition_engine()
        view = cognition_engine.get_role_view(role_type)

        if not view:
            return ViewResponse()

        return ViewResponse(
            view_id=view.get("view_id"),
            role=view.get("role"),
            name=view.get("name"),
            description=view.get("description"),
            capabilities=view.get("capabilities", []),
            layout_config=view.get("layout_config", {}),
            filters=view.get("filters", {}),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"认知引擎不可用: {str(e)}")


@router.post("/navigate", response_model=NavigateResponse)
async def navigate_knowledge(request: NavigateRequest):
    if not request.entity_id:
        raise HTTPException(status_code=400, detail="entity_id 不能为空")
    try:
        cognition_engine = get_cognition_engine()
        result = cognition_engine.navigate_knowledge_graph(request.entity_id, request.direction)

        return NavigateResponse(
            entity_id=result.get("entity_id", request.entity_id),
            navigation_path=result.get("navigation_path", []),
            related_entities=result.get("related_entities", []),
            entity_context=result.get("entity_context", {}),
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"认知引擎不可用: {str(e)}")


@router.post("/explain", response_model=ExplainResponse)
async def explain_decision(request: ExplainRequest):
    if not request.decision_id:
        raise HTTPException(status_code=400, detail="decision_id 不能为空")
    try:
        cognition_engine = get_cognition_engine()
        explanation = cognition_engine.explain_decision(request.decision_id, request.context)

        reasoning_chain = []
        if explanation.reasoning_chain:
            reasoning_chain = [
                {
                    "step_id": s.step_id,
                    "step_type": s.step_type,
                    "description": s.description,
                }
                for s in explanation.reasoning_chain.steps
            ]

        return ExplainResponse(
            explanation_id=explanation.explanation_id,
            query=explanation.query,
            answer=explanation.answer,
            confidence=explanation.confidence,
            reasoning_chain=reasoning_chain,
            sources=explanation.sources,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"认知引擎不可用: {str(e)}")
