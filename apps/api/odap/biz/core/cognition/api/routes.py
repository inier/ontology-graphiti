from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user

from odap.biz.core.cognition.api.schemas import (
    RecognizeIntentRequest,
    RecognizeIntentResponse,
    NavigateRequest,
    NavigateResponse,
    ExplainRequest,
    ExplainResponse,
    RoleViewResponse,
    UpdateRoleViewRequest,
)
from odap.biz.core.cognition.services.cognition_service import get_cognition_service


router = APIRouter(prefix="/api/cognition", tags=["cognition"])


@router.post("/recognize-intent", response_model=RecognizeIntentResponse)
async def recognize_intent(request: RecognizeIntentRequest,
    user=Depends(get_current_user)):
    if not request.input_text:
        raise HTTPException(status_code=400, detail="input_text cannot be empty")
    try:
        service = get_cognition_service()
        result = service.recognize_intent(
            request.input_text, request.role, request.ontology_facts or None
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "Intent recognition failed"))
        return RecognizeIntentResponse(
            intent_id=result.get("intent_id"),
            primary_intent=result.get("primary_intent"),
            confidence=result.get("confidence", 0.0),
            entities=result.get("entities", []),
            attributes=result.get("attributes", {}),
            alternative_intents=result.get("alternative_intents", []),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cognition engine unavailable: {str(e)}")


@router.post("/navigate", response_model=NavigateResponse)
async def navigate_knowledge(request: NavigateRequest,
    user=Depends(get_current_user)):
    if not request.entity_id:
        raise HTTPException(status_code=400, detail="entity_id cannot be empty")
    try:
        service = get_cognition_service()
        result = service.navigate(request.entity_id, request.direction, request.depth)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "Navigation failed"))
        return NavigateResponse(
            navigation_id=result.get("navigation_id"),
            entity_id=result.get("entity_id", request.entity_id),
            navigation_path=result.get("navigation_path", []),
            related_entities=result.get("related_entities", []),
            entity_context=result.get("entity_context", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cognition engine unavailable: {str(e)}")


@router.post("/explain", response_model=ExplainResponse)
async def explain_decision(request: ExplainRequest,
    user=Depends(get_current_user)):
    if not request.decision_id:
        raise HTTPException(status_code=400, detail="decision_id cannot be empty")
    try:
        service = get_cognition_service()
        result = service.explain(request.decision_id, request.context)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "Explanation failed"))
        return ExplainResponse(
            explanation_id=result.get("explanation_id"),
            decision_id=result.get("decision_id", request.decision_id),
            query=result.get("query", ""),
            answer=result.get("answer", ""),
            confidence=result.get("confidence", 0.0),
            reasoning_chain=result.get("reasoning_chain", []),
            sources=result.get("sources", []),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cognition engine unavailable: {str(e)}")


@router.get("/role-view", response_model=RoleViewResponse)
async def get_role_view(role: str = Query(...),
    user=Depends(get_current_user)):
    try:
        service = get_cognition_service()
        result = service.get_role_view(role)
        if result.get("status") == "error":
            return RoleViewResponse()
        return RoleViewResponse(
            view_id=result.get("view_id"),
            role=result.get("role"),
            name=result.get("name"),
            description=result.get("description"),
            capabilities=result.get("capabilities", []),
            layout_config=result.get("layout_config", {}),
            filters=result.get("filters", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cognition engine unavailable: {str(e)}")


@router.put("/role-view", response_model=RoleViewResponse)
async def update_role_view(request: UpdateRoleViewRequest,
    user=Depends(get_current_user)):
    try:
        service = get_cognition_service()
        config = {
            "capabilities": request.capabilities,
            "layout_config": request.layout_config,
            "filters": request.filters,
        }
        if request.name:
            config["name"] = request.name
        if request.description:
            config["description"] = request.description
        result = service.update_role_view(request.role, config)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "View not found"))
        view = result.get("view", result)
        return RoleViewResponse(
            view_id=view.get("view_id"),
            role=view.get("role"),
            name=view.get("name"),
            description=view.get("description"),
            capabilities=view.get("capabilities", []),
            layout_config=view.get("layout_config", {}),
            filters=view.get("filters", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cognition engine unavailable: {str(e)}")
