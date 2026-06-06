import uuid
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from odap.biz.data.qa.qa_engine import QAEngineV2
from odap.biz.data.qa.impl.temporal_reasoner import TemporalReasoner
from odap.biz.data.qa.impl.chart_renderer import ChartRenderer


class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    user_id: str = "anonymous"
    agent_id: Optional[str] = None


class AskStreamRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    user_id: str = "anonymous"
    agent_id: Optional[str] = None


class FeedbackRequest(BaseModel):
    feedback: Dict[str, Any] = Field(default_factory=dict)
    rating: int = Field(default=5, ge=1, le=10)


class AskResponse(BaseModel):
    session_id: str
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    dialog_state: str = "completed"
    intent: Dict[str, Any] = Field(default_factory=dict)
    sources_used: List[str] = Field(default_factory=list)


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    state: str
    created_at: str
    updated_at: str
    message_count: int = 0


class SessionDetailResponse(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class HistoryResponse(BaseModel):
    session_id: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class FeedbackResponse(BaseModel):
    status: str
    feedback_id: str


class StatsResponse(BaseModel):
    total: int = 0
    today: int = 0
    by_intent: Dict[str, int] = Field(default_factory=dict)
    by_source: Dict[str, int] = Field(default_factory=dict)
    time_distribution: Dict[str, int] = Field(default_factory=dict)
    period: Dict[str, Optional[str]] = Field(default_factory=dict)


class UserStatsResponse(BaseModel):
    user_stats: List[Dict[str, Any]] = Field(default_factory=list)
    total_users: int = 0
    limit: int = 10


class TopicStatsResponse(BaseModel):
    topics: List[Dict[str, Any]] = Field(default_factory=list)
    limit: int = 20


class TemporalAskRequest(BaseModel):
    question: str
    valid_time: Optional[str] = None
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None


class TemporalAskResponse(BaseModel):
    status: str
    question: str
    answer: str
    valid_time: Optional[str] = None
    time_type: Optional[str] = None
    entity_count: int = 0


class ChartRequest(BaseModel):
    chart_type: str
    data: Dict[str, Any]
    title: str = ""
    render_mode: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class ChartResponse(BaseModel):
    status: str
    chart_type: str
    render_mode: str
    title: str
    spec: Dict[str, Any] = Field(default_factory=dict)


router = APIRouter(prefix="/api/qa", tags=["qa"])

logger = logging.getLogger(__name__)

_qa_engine_instance: Optional[QAEngineV2] = None


def _get_qa_engine() -> QAEngineV2:
    global _qa_engine_instance
    if _qa_engine_instance is None:
        graph_manager = None
        try:
            from odap.infra.graph.graph_service import GraphManager
            graph_manager = GraphManager()
        except Exception:
            pass

        ingest_storage = None
        try:
            from odap.biz.core.ontology.storage.sqlite_ingest_storage import SQLiteIngestStorage
            ingest_storage = SQLiteIngestStorage()
        except Exception as e:
            logger.warning(f"SQLiteIngestStorage creation failed: {e}")

        semantic_map_storage = None
        try:
            from odap.biz.data.semantic_map.storage import Storage as SemanticMapStorage
            semantic_map_storage = SemanticMapStorage()
        except Exception as e:
            logger.warning(f"SemanticMapStorage creation failed: {e}")

        use_mock = (graph_manager is None and ingest_storage is None and semantic_map_storage is None)

        _qa_engine_instance = QAEngineV2(
            graphiti_client=graph_manager,
            use_mock=use_mock,
            ingest_storage=ingest_storage,
            semantic_map_storage=semantic_map_storage,
        )
    return _qa_engine_instance


def _load_agent_context(agent_id: str) -> Dict[str, Any]:
    if not agent_id:
        return {}
    try:
        from odap.biz.management.agent_management.storage.sqlite_agent_storage import SQLiteAgentStorage
        storage = SQLiteAgentStorage()
        agent = storage.get_agent(agent_id)
        if not agent:
            return {}
        return {
            "agent_id": agent.get("agent_id", ""),
            "agent_name": agent.get("display_name", agent.get("name", "")),
            "main_object": agent.get("main_object", ""),
            "related_objects": agent.get("related_objects", []),
            "related_processes": agent.get("related_processes", []),
            "related_rules": agent.get("related_rules", []),
            "related_business_logic": agent.get("related_business_logic", []),
            "related_indicators": agent.get("related_indicators", []),
            "related_skills": agent.get("related_skills", []),
            "related_knowledge_bases": agent.get("related_knowledge_bases", []),
            "allowed_roles": agent.get("allowed_roles", []),
            "workspace_id": agent.get("workspace_id", ""),
            "description": agent.get("description", ""),
        }
    except Exception:
        return {}


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest,
    user=Depends(get_current_user)):
    if not request.question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    try:
        qa_engine = _get_qa_engine()
        agent_context = _load_agent_context(request.agent_id)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: qa_engine.ask(
                query=request.question,
                user_id=request.user_id,
                session_id=request.session_id,
                workspace_id=request.workspace_id,
                scenario_id=request.scenario_id,
                context=agent_context if agent_context else None,
            )
        )
        return AskResponse(
            session_id=result.get("session_id", ""),
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            dialog_state=result.get("dialog_state", "completed"),
            intent={"type": "query", "confidence": 0.85},
            sources_used=["graphiti", "rag"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


@router.post("/ask/stream")
async def ask_question_stream(request: AskStreamRequest,
    user=Depends(get_current_user)):
    if not request.question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    try:
        qa_engine = _get_qa_engine()
        agent_context = _load_agent_context(request.agent_id)

        async def streaming_response():
            import json
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: qa_engine.ask(
                    query=request.question,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    workspace_id=request.workspace_id,
                    scenario_id=request.scenario_id,
                    context=agent_context if agent_context else None,
                )
            )
            response_session_id = result.get("session_id", "")
            answer = result.get("answer", "")
            sources = result.get("sources", [])

            yield f'{{"type": "session_id", "value": "{response_session_id}"}}\n'

            for i in range(0, len(answer), 10):
                chunk = answer[i:i + 10]
                yield f'{{"type": "content", "value": {json.dumps(chunk)}}}\n'

            yield f'{{"type": "sources", "value": {json.dumps(sources)}}}\n'

            charts = result.get("charts", [])
            for chart in charts:
                yield f'{{"type": "chart", "value": {json.dumps(chart)}}}\n'

            temporal_data = result.get("temporal", [])
            for t in temporal_data:
                yield f'{{"type": "temporal", "value": {json.dumps(t)}}}\n'

            reports = result.get("reports", [])
            for r in reports:
                yield f'{{"type": "report", "value": {json.dumps(r)}}}\n'

            yield f'{{"type": "done"}}\n'

        return StreamingResponse(
            streaming_response(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    user_id: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    scenario_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)):
    try:
        qa_engine = _get_qa_engine()
        sessions = qa_engine.dialog_manager._sessions

        session_list = []
        for session_id, session in sessions.items():
            if workspace_id and session.workspace_id != workspace_id:
                continue
            if scenario_id and session.scenario_id != scenario_id:
                continue
            if user_id and session.user_id != user_id:
                continue
            session_list.append(SessionResponse(
                session_id=session.session_id,
                user_id=session.user_id,
                workspace_id=session.workspace_id,
                scenario_id=session.scenario_id,
                state=session.state.value,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=len(session.messages),
            ))

        session_list.sort(key=lambda s: s.updated_at, reverse=True)
        return session_list[:limit]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str,
    user=Depends(get_current_user)):
    try:
        qa_engine = _get_qa_engine()
        history = qa_engine.get_dialog_history(session_id)
        if not history:
            raise HTTPException(status_code=404, detail="会话不存在")
        return SessionDetailResponse(
            session_id=session_id,
            messages=history,
            total=len(history),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str,
    user=Depends(get_current_user)):
    try:
        qa_engine = _get_qa_engine()
        session = qa_engine.dialog_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        qa_engine.close_dialog(session_id)
        return {"status": "success", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


@router.get("/sessions/{session_id}/history", response_model=HistoryResponse)
async def get_session_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)):
    try:
        qa_engine = _get_qa_engine()
        history = qa_engine.get_dialog_history(session_id)
        return HistoryResponse(
            session_id=session_id,
            history=history[-limit:],
            total=len(history),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


@router.post("/sessions/{session_id}/feedback", response_model=FeedbackResponse)
async def submit_feedback(session_id: str, request: FeedbackRequest,
    user=Depends(get_current_user)):
    try:
        qa_engine = _get_qa_engine()
        session = qa_engine.dialog_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        return FeedbackResponse(status="success", feedback_id=feedback_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    workspace_id: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    try:
        qa_engine = _get_qa_engine()
        sessions = qa_engine.dialog_manager._sessions

        if workspace_id:
            sessions = {
                sid: s for sid, s in sessions.items()
                if s.workspace_id == workspace_id
            }

        total = sum(len(s.messages) for s in sessions.values())
        today = datetime.now().date()
        today_count = 0
        for s in sessions.values():
            for msg in s.messages:
                try:
                    msg_date = datetime.fromisoformat(msg.timestamp).date()
                    if msg_date == today:
                        today_count += 1
                except Exception:
                    pass

        by_intent: Dict[str, int] = {}
        by_source: Dict[str, int] = {}
        time_distribution: Dict[str, int] = {}

        for s in sessions.values():
            for msg in s.messages:
                if msg.role == "user":
                    intent_type = "query"
                    by_intent[intent_type] = by_intent.get(intent_type, 0) + 1
                if hasattr(msg, 'source') and msg.source:
                    by_source[msg.source] = by_source.get(msg.source, 0) + 1
                try:
                    hour = str(datetime.fromisoformat(msg.timestamp).hour)
                    time_distribution[hour] = time_distribution.get(hour, 0) + 1
                except Exception:
                    pass

        return StatsResponse(
            total=total,
            today=today_count,
            by_intent=by_intent,
            by_source=by_source,
            time_distribution=time_distribution,
            period={"start": start_time, "end": end_time},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


@router.get("/stats/users", response_model=UserStatsResponse)
async def get_user_stats(
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    user=Depends(get_current_user)):
    try:
        qa_engine = _get_qa_engine()
        sessions = qa_engine.dialog_manager._sessions

        if workspace_id:
            sessions = {
                sid: s for sid, s in sessions.items()
                if s.workspace_id == workspace_id
            }

        user_stats: Dict[str, Dict[str, Any]] = {}
        for session in sessions.values():
            uid = session.user_id
            if uid not in user_stats:
                user_stats[uid] = {
                    "user_id": uid,
                    "count": 0,
                    "first_time": session.created_at,
                    "last_time": session.updated_at,
                }
            user_stats[uid]["count"] += len(session.messages)
            if session.updated_at > user_stats[uid]["last_time"]:
                user_stats[uid]["last_time"] = session.updated_at
            if session.created_at < user_stats[uid]["first_time"]:
                user_stats[uid]["first_time"] = session.created_at

        sorted_users = sorted(user_stats.values(), key=lambda x: x["count"], reverse=True)[:limit]

        return UserStatsResponse(
            user_stats=sorted_users,
            total_users=len(user_stats),
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


@router.get("/stats/topics", response_model=TopicStatsResponse)
async def get_topic_stats(
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user)):
    try:
        qa_engine = _get_qa_engine()
        sessions = qa_engine.dialog_manager._sessions

        if workspace_id:
            sessions = {
                sid: s for sid, s in sessions.items()
                if s.workspace_id == workspace_id
            }

        topic_counts: Dict[str, int] = {}
        for session in sessions.values():
            for msg in session.messages:
                if msg.role == "user" and msg.content:
                    keywords = msg.content.split()[:3]
                    topic = " ".join(keywords)
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1

        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        return TopicStatsResponse(
            topics=[{"topic": t, "count": c, "trend": "stable"} for t, c in sorted_topics],
            limit=limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"QA 引擎不可用: {str(e)}")


_temporal_reasoner: Optional[TemporalReasoner] = None
_chart_renderer: Optional[ChartRenderer] = None


def _get_temporal_reasoner() -> TemporalReasoner:
    global _temporal_reasoner
    if _temporal_reasoner is None:
        graph_manager = None
        try:
            from odap.infra.graph.graph_service import GraphManager
            graph_manager = GraphManager()
        except Exception:
            pass
        _temporal_reasoner = TemporalReasoner(graphiti_client=graph_manager)
    return _temporal_reasoner


def _get_chart_renderer() -> ChartRenderer:
    global _chart_renderer
    if _chart_renderer is None:
        _chart_renderer = ChartRenderer()
    return _chart_renderer


@router.post("/ask/temporal", response_model=TemporalAskResponse)
async def ask_temporal_question(request: TemporalAskRequest,
    user=Depends(get_current_user)):
    if not request.question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    try:
        reasoner = _get_temporal_reasoner()
        result = reasoner.answer_temporal_question(
            question=request.question,
            valid_time=request.valid_time,
            workspace_id=request.workspace_id,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "时序解析失败"))
        return TemporalAskResponse(
            status=result.get("status", "success"),
            question=result.get("question", ""),
            answer=result.get("answer", ""),
            valid_time=result.get("valid_time"),
            time_type=result.get("time_type"),
            entity_count=result.get("entity_count", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"时序问答不可用: {str(e)}")


@router.post("/chart", response_model=ChartResponse)
async def render_chart(request: ChartRequest,
    user=Depends(get_current_user)):
    if not request.chart_type:
        raise HTTPException(status_code=400, detail="图表类型不能为空")
    if not request.data:
        raise HTTPException(status_code=400, detail="图表数据不能为空")
    try:
        renderer = _get_chart_renderer()
        result = renderer.render(
            chart_type=request.chart_type,
            data=request.data,
            title=request.title,
            render_mode=request.render_mode,
            options=request.options,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "图表渲染失败"))
        return ChartResponse(
            status=result.get("status", "success"),
            chart_type=result.get("chart_type", request.chart_type),
            render_mode=result.get("render_mode", "frontend"),
            title=result.get("title", request.title),
            spec=result.get("spec", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"图表渲染不可用: {str(e)}")
