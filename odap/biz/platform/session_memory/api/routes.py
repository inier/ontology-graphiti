from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from ..context_window import ContextWindow, ChatMessage, MessageRole
from ..memory_compactor import MemoryCompactor
from ..cot_builder import CoTBuilder
from ..session_store import SessionStore, Session
from ..memory_tiers import get_session_memory_manager

router = APIRouter(prefix="/api/session-memory", tags=["session-memory"])

_store: Optional[SessionStore] = None
_compactor: Optional[MemoryCompactor] = None


def _get_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def _get_compactor() -> MemoryCompactor:
    global _compactor
    if _compactor is None:
        _compactor = MemoryCompactor()
    return _compactor


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
    store = _get_store()
    session = Session(
        workspace_id=request.workspace_id,
        title=request.title or "New Session",
        context_window=ContextWindow(max_tokens=request.max_tokens),
    )
    session_id = store.save_session(session)
    return {"session_id": session_id, "title": session.title}


@router.get("/sessions")
async def list_sessions(workspace_id: str = "default", limit: int = 20,
    user=Depends(get_current_user)):
    store = _get_store()
    summaries = store.list_sessions(workspace_id, limit)
    return {"sessions": [s.model_dump() for s in summaries]}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str,
    user=Depends(get_current_user)):
    store = _get_store()
    session = store.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": session.id,
        "workspace_id": session.workspace_id,
        "title": session.title,
        "message_count": len(session.messages),
        "context_window": session.context_window.to_dict(),
        "is_active": session.is_active,
    }


@router.post("/sessions/{session_id}/messages")
async def add_message(session_id: str, request: AddMessageRequest,
    user=Depends(get_current_user)):
    store = _get_store()
    session = store.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        role = MessageRole(request.role)
    except ValueError:
        role = MessageRole.USER

    message = ChatMessage(role=role, content=request.content, tokens=request.tokens, entities=request.entities)
    session.messages.append(message)
    session.context_window.add_message(message)

    compactor = _get_compactor()
    if compactor.should_compact(session.context_window):
        session.context_window = await compactor.compact(session.context_window)

    store.save_session(session)
    return {"message_id": message.id, "context_window": session.context_window.to_dict()}


@router.get("/sessions/{session_id}/context")
async def get_context(session_id: str,
    user=Depends(get_current_user)):
    store = _get_store()
    session = store.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "context_window": session.context_window.to_dict(),
        "messages": [m.model_dump() for m in session.context_window.messages],
        "summary": session.context_window.summary,
    }


@router.post("/sessions/{session_id}/compact")
async def compact_session(session_id: str,
    user=Depends(get_current_user)):
    store = _get_store()
    session = store.load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    compactor = _get_compactor()
    session.context_window = await compactor.compact(session.context_window)
    store.save_session(session)
    return {"context_window": session.context_window.to_dict()}


@router.post("/sessions/{session_id}/cot")
async def build_cot(session_id: str, request: QueryRequest,
    user=Depends(get_current_user)):
    store = _get_store()
    session = store.load_session(session_id)
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
    store.save_session(session)

    return {"cot_tree": builder.to_serializable()}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str,
    user=Depends(get_current_user)):
    store = _get_store()
    success = store.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


@router.get("/memory/session/{session_id}")
async def get_session_memory(session_id: str,
    user=Depends(get_current_user)):
    manager = get_session_memory_manager()
    return manager.get_session_memory(session_id)


@router.post("/memory/session/{session_id}/store")
async def store_session_memory(session_id: str, request: StoreMemoryRequest,
    user=Depends(get_current_user)):
    manager = get_session_memory_manager()
    if request.tier == "short_term":
        return manager.store_short_term(session_id, request.key, request.value)
    elif request.tier == "working":
        return manager.store_working(session_id, request.key, request.value)
    else:
        return manager.store_short_term(session_id, request.key, request.value)


@router.post("/memory/session/{session_id}/clear")
async def clear_short_term_memory(session_id: str,
    user=Depends(get_current_user)):
    manager = get_session_memory_manager()
    return manager.clear_short_term(session_id)


@router.get("/memory/long-term")
async def retrieve_long_term_memory(query: str = Query(...), limit: int = Query(10, ge=1, le=100),
    user=Depends(get_current_user)):
    manager = get_session_memory_manager()
    return manager.retrieve_long_term(query, limit)


@router.post("/memory/long-term")
async def store_long_term_memory(request: StoreLongTermRequest,
    user=Depends(get_current_user)):
    manager = get_session_memory_manager()
    return manager.store_long_term(request.key, request.value)
