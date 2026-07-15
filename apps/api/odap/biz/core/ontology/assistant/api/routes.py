"""T063 AI assistant API routes.

Endpoints: AG-UI run/resume (SSE), infer-type, suggest-constraints,
suggestions CRUD, health check.
Follows AGENTS.md rules: prefix /api/ontology-assistant, except HTTPException: raise.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional

from odap.biz.core.ontology.assistant.models.schemas import (
    HealthResponse,
    InferTypeRequest,
    RejectSuggestionRequest,
    ResumeRequest,
    RunRequest,
    SuggestConstraintsRequest,
)
from odap.biz.core.ontology.assistant.services.assistant_service import AssistantService
from odap.biz.core.ontology.assistant.services.suggestion_service import SuggestionService
from odap.infra.security.jwt_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ontology-assistant", tags=["ontology-assistant"])
_service = AssistantService()
_suggestion_service = SuggestionService()


def _user_id(user) -> str:
    return user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"


def _audit(action: str, user_id: str, result_status: str, message: str = "", details: dict = None):
    try:
        from odap.infra.security.unified_audit import log_audit

        log_audit(
            action=action,
            resource="ontology_assistant",
            user=user_id,
            service="ontology_assistant",
            result_status=result_status,
            result_message=message,
            details=details or {},
            workspace_id="default",
        )
    except Exception:
        pass


@router.get("/health")
async def health_check(user=Depends(get_current_user)):
    try:
        return _service.health_check()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infer-type")
async def infer_type(req: InferTypeRequest, user=Depends(get_current_user)):
    try:
        return _service.infer_type(req.property_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggest-constraints")
async def suggest_constraints(req: SuggestConstraintsRequest, user=Depends(get_current_user)):
    try:
        return _service.suggest_constraints(req.property_name, req.data_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run(req: RunRequest, user=Depends(get_current_user)):
    uid = _user_id(user)
    try:
        async def event_stream():
            try:
                async for event in _service.run(
                    ontology_id=req.ontology_id,
                    context_type=req.context_type,
                    message=req.message,
                    context_id=req.context_id,
                    session_id=req.session_id,
                    user_id=uid,
                ):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as exc:
                logger.exception("AG-UI run stream error")
                yield f"data: {json.dumps({'type': 'RUN_ERROR', 'message': str(exc)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except HTTPException:
        raise
    except Exception as e:
        _audit("ontology_assistant_run_failed", uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume")
async def resume(req: ResumeRequest, user=Depends(get_current_user)):
    uid = _user_id(user)
    try:
        async def event_stream():
            try:
                async for event in _service.resume(
                    run_id=req.run_id,
                    tool_call_id=req.tool_call_id,
                    response=req.response,
                    suggestion_id=req.suggestion_id,
                    user_id=uid,
                ):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as exc:
                logger.exception("AG-UI resume stream error")
                yield f"data: {json.dumps({'type': 'RUN_ERROR', 'message': str(exc)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except HTTPException:
        raise
    except Exception as e:
        _audit("ontology_assistant_resume_failed", uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def list_suggestions(
    ontology_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    try:
        return _suggestion_service.list_suggestions(ontology_id=ontology_id, status=status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(suggestion_id: str, user=Depends(get_current_user)):
    uid = _user_id(user)
    try:
        result = _suggestion_service.accept_suggestion(suggestion_id, user_id=uid)
        if result.get("status") == "error":
            _audit("ai_suggestion_accept_failed", uid, "failure", result.get("message", ""),
                   details={"suggestion_id": suggestion_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        _audit("ai_suggestion_accept", uid, "success", "Suggestion accepted",
               details={"suggestion_id": suggestion_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("ai_suggestion_accept_failed", uid, "failure", str(e),
               details={"suggestion_id": suggestion_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(
    suggestion_id: str,
    req: RejectSuggestionRequest,
    user=Depends(get_current_user),
):
    uid = _user_id(user)
    try:
        result = _suggestion_service.reject_suggestion(
            suggestion_id, user_id=uid, reason=req.reason
        )
        if result.get("status") == "error":
            _audit("ai_suggestion_reject_failed", uid, "failure", result.get("message", ""),
                   details={"suggestion_id": suggestion_id})
            raise HTTPException(status_code=404, detail=result.get("message"))
        _audit("ai_suggestion_reject", uid, "success", "Suggestion rejected",
               details={"suggestion_id": suggestion_id, "reason": req.reason})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("ai_suggestion_reject_failed", uid, "failure", str(e),
               details={"suggestion_id": suggestion_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/suggestions/{suggestion_id}")
async def delete_suggestion(suggestion_id: str, user=Depends(get_current_user)):
    uid = _user_id(user)
    try:
        result = _suggestion_service.delete_suggestion(suggestion_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
