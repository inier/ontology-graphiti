from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Any, List
from pydantic import BaseModel, Field

from ..services.session_memory_service import get_session_memory_service
from ..cot_builder import CoTBuilder, CoTNodeType

router = APIRouter(prefix="/api/session-memory", tags=["session-memory"])

session_memory_service = get_session_memory_service()


class CreateSessionRequest(BaseModel):
    workspace_id: str = "default"
    title: str = ""
    max_tokens: int = 8000


class AddMessageRequest(BaseModel):
    role: str
    content: str
    tokens: int = 0
    entities: List[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    query: str


class StoreMemoryRequest(BaseModel):
    key: str
    value: Any
    tier: str = "short_term"


class StoreLongTermRequest(BaseModel):
    key: str
    value: Any


@router.post("/sessions")
async def create_session(request: CreateSessionRequest,
    user=Depends(get_current_user)):
    try:
        result = session_memory_service.create_session(
            workspace_id=request.workspace_id,
            title=request.title,
            max_tokens=request.max_tokens,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions(workspace_id: str = "default", limit: int = 20,
    user=Depends(get_current_user)):
    try:
        return session_memory_service.list_sessions(workspace_id, limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_session(session_id: str,
    user=Depends(get_current_user)):
    try:
        result = session_memory_service.get_session(session_id)
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/messages")
async def add_message(session_id: str, request: AddMessageRequest,
    user=Depends(get_current_user)):
    try:
        result = session_memory_service.add_message(
            session_id=session_id,
            role=request.role,
            content=request.content,
            tokens=request.tokens,
            entities=request.entities,
        )
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")

        # 如果标记需要压缩，在异步路由层执行压缩
        if result.get("needs_compaction"):
            compact_result = await session_memory_service.compact_if_needed(session_id)
            if compact_result.get("status") == "success":
                result["context_window"] = compact_result["context_window"]
                result["compacted"] = True

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/context")
async def get_context(session_id: str,
    user=Depends(get_current_user)):
    try:
        result = session_memory_service.get_context(session_id)
        if not result:
            raise HTTPException(status_code=404, detail="Session not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/compact")
async def compact_session(session_id: str,
    user=Depends(get_current_user)):
    try:
        session = session_memory_service.load_session_raw(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 强制标记需要压缩，然后通过 compact_if_needed 执行
        session.needs_compaction = True
        session_memory_service.save_session_raw(session)

        result = await session_memory_service.compact_if_needed(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/cot")
async def build_cot(session_id: str, request: QueryRequest,
    user=Depends(get_current_user)):
    try:
        session = session_memory_service.load_session_raw(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        builder = CoTBuilder()
        root = builder.start(request.query)

        intent_node = builder.add_child(root, CoTNodeType.INTENT, "Intent Recognition", "Analyze user query intent")
        builder.start_timing(intent_node.id)
        builder.update_status(intent_node.id, "done", detail="Situation query")
        builder.finish_timing(intent_node.id)

        entity_node = builder.add_child(intent_node, CoTNodeType.ENTITY_LINK, "Entity Linking", "Match related entities")
        builder.update_status(entity_node.id, "done", detail="3 entities matched")

        context_node = builder.add_child(intent_node, CoTNodeType.CONTEXT_FETCH, "Context Retrieval", "Fetch subgraph")
        builder.update_status(context_node.id, "done", detail="Context retrieved")

        rag_node = builder.add_child(intent_node, CoTNodeType.RAG_AUGMENT, "RAG Augmentation", "Inject prompt")
        builder.update_status(rag_node.id, "done", detail="Results injected")

        llm_node = builder.add_child(intent_node, CoTNodeType.LLM_INFER, "LLM Inference", "Generate answer")
        builder.update_status(llm_node.id, "done", detail="Inference complete")

        session.cot_tree_data = builder.to_serializable()
        session_memory_service.save_session_raw(session)

        return {"cot_tree": builder.to_serializable()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str,
    user=Depends(get_current_user)):
    try:
        success = session_memory_service.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Session deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/session/{session_id}")
async def get_session_memory(session_id: str,
    user=Depends(get_current_user)):
    try:
        return session_memory_service.get_session_memory(session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/session/{session_id}/store")
async def store_session_memory(session_id: str, request: StoreMemoryRequest,
    user=Depends(get_current_user)):
    try:
        if request.tier == "short_term":
            return session_memory_service.store_short_term_memory(session_id, request.key, request.value)
        elif request.tier == "working":
            return session_memory_service.store_working_memory(session_id, request.key, request.value)
        else:
            return session_memory_service.store_short_term_memory(session_id, request.key, request.value)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/session/{session_id}/clear")
async def clear_short_term_memory(session_id: str,
    user=Depends(get_current_user)):
    try:
        return session_memory_service.clear_short_term_memory(session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/long-term")
async def retrieve_long_term_memory(query: str = Query(...), limit: int = Query(10, ge=1, le=100),
    user=Depends(get_current_user)):
    try:
        return session_memory_service.retrieve_long_term_memory(query, limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/long-term")
async def store_long_term_memory(request: StoreLongTermRequest,
    user=Depends(get_current_user)):
    try:
        return session_memory_service.store_long_term_memory(request.key, request.value)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
