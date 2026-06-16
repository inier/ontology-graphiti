"""前端API兼容层 - 智能问答/认知路由"""

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from odap.infra.security.jwt_auth import get_current_user
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
import json
import uuid
import asyncio
from datetime import datetime

from odap.biz.integration.frontend_compat.api._deps import (
    audit_logger,
    AuditFilter,
    AuditEventType,
    ActorInfo,
    ResourceInfo,
    get_qa_engine,
)

router = APIRouter(prefix="/api/compat", tags=["frontend-compat-qa"])


# ==================== 智能问答路由 ====================

@router.post("/qa/ask")
async def ask_question(request: Request, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """
    智能问答接口

    请求体:
    {
        "question": "用户问题",
        "session_id": "可选的会话ID",
        "workspace_id": "可选的工作空间ID"
    }

    返回:
    {
        "session_id": "会话ID",
        "answer": "回答内容",
        "sources": [{"source": "来源", "excerpt": "内容摘要", "confidence": 0.9}],
        "intent": {"type": "query", "confidence": 0.95},
        "sources_used": ["graphiti", "rag"]
    }
    """
    try:
        question = data.get("question", "")
        session_id = data.get("session_id")
        workspace_id = data.get("workspace_id")
        user_id = data.get("user_id", "anonymous")
        agent_id = data.get("agent_id")

        if not question:
            raise HTTPException(status_code=400, detail="问题不能为空")

        agent_context = {}
        if agent_id:
            try:
                from odap.biz.management.agent_management.services.agent_service import AgentService
                agent_service = AgentService()
                agent = agent_service.get_agent(agent_id)
                if agent:
                    agent_context = {
                        "agent_name": agent.get("display_name") or agent.get("name", ""),
                        "main_object": agent.get("main_object", ""),
                        "description": agent.get("description", ""),
                        "related_objects": agent.get("related_objects", []),
                        "related_processes": agent.get("related_processes", []),
                        "related_rules": agent.get("related_rules", []),
                        "related_business_logic": agent.get("related_business_logic", []),
                        "related_indicators": agent.get("related_indicators", []),
                        "related_skills": agent.get("related_skills", []),
                        "related_knowledge_bases": agent.get("related_knowledge_bases", []),
                    }
            except HTTPException:
                raise
            except Exception as e:
                import logging
                logging.getLogger("frontend_compat").warning(f"Failed to load agent context: {e}")

        qa_engine = get_qa_engine(use_mock=False)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: qa_engine.ask(
                query=question,
                user_id=user_id,
                session_id=session_id,
                workspace_id=workspace_id,
                scenario_id=data.get("scenario_id"),
                agent_id=agent_id,
                context=agent_context if agent_context else None,
            ),
        )

        return {
            "session_id": result.get("session_id"),
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "dialog_state": result.get("dialog_state", "completed"),
            "intent": result.get("intent", {
                "type": "query",
                "confidence": max((s.get("confidence", 0.0) for s in result.get("sources", [])), default=0.0),
            }),
            "sources_used": list(set(
                s.get("source", "unknown") for s in result.get("sources", []) if s.get("source")
            )) if result.get("sources") else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"QA ask error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa/ask/stream")
async def ask_question_stream(request: Request, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """
    智能问答流式接口 - 真正的逐token流式输出

    请求体:
    {
        "question": "用户问题",
        "session_id": "可选的会话ID",
        "workspace_id": "可选的工作空间ID"
    }

    返回: SSE 流式事件
    """
    try:
        question = data.get("question", "")
        session_id = data.get("session_id")
        workspace_id = data.get("workspace_id")
        user_id = data.get("user_id", "anonymous")
        agent_id = data.get("agent_id")

        if not question:
            raise HTTPException(status_code=400, detail="问题不能为空")

        agent_context = None
        if agent_id:
            try:
                from odap.biz.management.agent_management.api.routes import agent_service as _agent_svc
                agent = _agent_svc.get_agent(agent_id)
                if agent:
                    agent_context = {
                        "agent_name": agent.get("display_name") or agent.get("name", ""),
                        "main_object": agent.get("main_object", ""),
                        "description": agent.get("description", ""),
                        "related_objects": agent.get("related_objects", []),
                        "related_processes": agent.get("related_processes", []),
                        "related_rules": agent.get("related_rules", []),
                        "related_business_logic": agent.get("related_business_logic", []),
                        "related_indicators": agent.get("related_indicators", []),
                        "related_skills": agent.get("related_skills", []),
                        "related_knowledge_bases": agent.get("related_knowledge_bases", []),
                    }
            except HTTPException:
                raise
            except Exception as e:
                import logging
                logging.getLogger("frontend_compat").warning(f"Failed to load agent context: {e}")

        qa_engine = get_qa_engine(use_mock=False)

        async def streaming_response():
            async for event in qa_engine.ask_stream(
                query=question,
                user_id=user_id,
                session_id=session_id,
                workspace_id=workspace_id,
                scenario_id=data.get("scenario_id"),
                agent_id=agent_id,
                context=agent_context,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            streaming_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"QA stream error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qa/sessions")
async def list_qa_sessions(
    user_id: Optional[str] = Query(None),
    workspace_id: Optional[str] = Query(None),
    scenario_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)):
    """列出问答会话"""
    try:
        qa_engine = get_qa_engine()
        sessions = qa_engine.dialog_manager._sessions

        session_list = []
        for session_id, session in sessions.items():
            if workspace_id and session.workspace_id != workspace_id:
                continue

            if scenario_id and session.scenario_id != scenario_id:
                continue

            if agent_id and session.agent_id != agent_id:
                continue

            summary = ""
            for msg in session.messages:
                if msg.role == "user":
                    summary = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
                    break

            session_list.append({
                "session_id": session.session_id,
                "summary": summary,
                "message_count": len(session.messages),
                "model": "QAEngineV2",
                "created_at": session.created_at,
                "workspace_id": session.workspace_id,
                "scenario_id": session.scenario_id,
                "agent_id": session.agent_id,
            })

        session_list.sort(key=lambda x: x["created_at"], reverse=True)

        return {
            "sessions": session_list[:limit],
            "total": len(session_list),
            "limit": limit,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qa/sessions/{session_id}")
async def get_qa_session(session_id: str,
    user=Depends(get_current_user)):
    """获取问答会话详情"""
    try:
        qa_engine = get_qa_engine(use_mock=False)
        history = qa_engine.get_dialog_history(session_id)

        return {
            "session_id": session_id,
            "messages": history,
            "total": len(history),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/qa/sessions/{session_id}")
async def close_qa_session(session_id: str,
    user=Depends(get_current_user)):
    """关闭问答会话"""
    try:
        qa_engine = get_qa_engine(use_mock=False)
        qa_engine.close_dialog(session_id)

        return {"status": "success", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qa/sessions/{session_id}/history")
async def get_qa_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user)):
    """获取问答历史"""
    try:
        qa_engine = get_qa_engine(use_mock=False)
        history = qa_engine.get_dialog_history(session_id)

        return {
            "session_id": session_id,
            "history": history[-limit:],
            "total": len(history),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/qa/sessions/{session_id}/feedback")
async def submit_qa_feedback(session_id: str, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """提交问答反馈"""
    try:
        feedback = data.get("feedback", {})
        rating = data.get("rating", 5)

        asyncio.create_task(
            audit_logger.log_success(
                event_type=AuditEventType.QUERY,
                action="QA_FEEDBACK",
                resource=ResourceInfo(
                    resource_type="qa",
                    resource_id=session_id,
                    resource_name="问答反馈",
                ),
                message=f"问答反馈: 评分 {rating}",
                actor=ActorInfo(
                    actor_type="user",
                    actor_id=data.get("user_id", "anonymous"),
                    actor_name=data.get("user_id", "Anonymous"),
                    roles=[],
                ),
                context={
                    "session_id": session_id,
                    "feedback": feedback,
                    "rating": rating,
                },
            )
        )

        return {
            "status": "success",
            "feedback_id": f"fb_{uuid.uuid4().hex[:12]}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 用户认知引擎路由 ====================

@router.post("/cognition/intent")
async def recognize_intent(request: Request, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """
    意图识别接口

    请求体:
    {
        "input_text": "用户输入",
        "role": "director|intelligence|operator|analyst|guest"
    }
    """
    try:
        from odap.biz.core.cognition.user_cognition_engine import get_cognition_engine, RoleType

        input_text = data.get("input_text", "")
        role_str = data.get("role", "guest")

        try:
            role = RoleType(role_str)
        except ValueError:
            role = RoleType.GUEST

        cognition_engine = get_cognition_engine()
        result = cognition_engine.process_query(input_text, "anonymous", role)

        return {
            "intent": result.get("intent", {}),
            "knowledge_results": result.get("knowledge_results", []),
            "session_id": result.get("session_id"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cognition/view")
async def get_role_view(role: str = Query(...),
    user=Depends(get_current_user)):
    """获取角色视图"""
    try:
        from odap.biz.core.cognition.user_cognition_engine import get_cognition_engine, RoleType

        try:
            role_type = RoleType(role)
        except ValueError:
            role_type = RoleType.GUEST

        cognition_engine = get_cognition_engine()
        view = cognition_engine.get_role_view(role_type)

        return view
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cognition/navigate")
async def navigate_knowledge(request: Request, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """知识图谱导航"""
    try:
        from odap.biz.core.cognition.user_cognition_engine import get_cognition_engine

        entity_id = data.get("entity_id", "")
        direction = data.get("direction", "outbound")

        if not entity_id:
            raise HTTPException(status_code=400, detail="entity_id不能为空")

        cognition_engine = get_cognition_engine()
        result = cognition_engine.navigate_knowledge_graph(entity_id, direction)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cognition/explain")
async def explain_decision(request: Request, data: Dict[str, Any],
    user=Depends(get_current_user)):
    """决策解释"""
    try:
        from odap.biz.core.cognition.user_cognition_engine import get_cognition_engine

        decision_id = data.get("decision_id", "")
        context = data.get("context", {})

        cognition_engine = get_cognition_engine()
        explanation = cognition_engine.explain_decision(decision_id, context)

        return {
            "explanation_id": explanation.explanation_id,
            "query": explanation.query,
            "answer": explanation.answer,
            "confidence": explanation.confidence,
            "reasoning_chain": [
                {
                    "step_id": s.step_id,
                    "step_type": s.step_type,
                    "description": s.description,
                }
                for s in explanation.reasoning_chain.steps
            ] if explanation.reasoning_chain else [],
            "sources": explanation.sources,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 问数统计路由（多维度数据分析） ====================

@router.get("/qa/stats")
async def get_qa_stats(
    workspace_id: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    """
    获取问答统计数据

    返回多维度分析数据:
    - total: 总问答数
    - today: 今日问答数
    - by_intent: 按意图类型统计
    - by_source: 按来源统计
    - by_user: 按用户统计
    - time_distribution: 时间分布
    """
    try:
        filter_kwargs = {
            "limit": 1000,
            "order_by": "timestamp",
            "order_desc": True,
        }

        if start_time:
            filter_kwargs["start_time"] = datetime.fromisoformat(start_time)
        if end_time:
            filter_kwargs["end_time"] = datetime.fromisoformat(end_time)
        if workspace_id:
            filter_kwargs["workspace_id"] = workspace_id

        audit_filter = AuditFilter(**filter_kwargs)

        events = await audit_logger.query(audit_filter)

        qa_events = [e for e in events if "QA_ASK" in e.action]

        total = len(qa_events)
        today = len([
            e for e in qa_events
            if e.timestamp.date() == datetime.now().date()
        ])

        by_intent = {}
        for event in qa_events:
            intent_type = event.context.get("intent_type", "query") if event.context else "query"
            by_intent[intent_type] = by_intent.get(intent_type, 0) + 1

        by_source = {"graphiti": 0, "rag": 0, "mock": 0}
        for event in qa_events:
            if event.context and "sources_used" in event.context:
                for source in event.context["sources_used"]:
                    if source in by_source:
                        by_source[source] += 1

        time_distribution = {}
        for event in qa_events:
            hour = event.timestamp.hour
            time_distribution[hour] = time_distribution.get(hour, 0) + 1

        return {
            "total": total,
            "today": today,
            "by_intent": by_intent,
            "by_source": by_source,
            "time_distribution": time_distribution,
            "period": {
                "start": start_time,
                "end": end_time,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qa/stats/users")
async def get_user_qa_stats(
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    user=Depends(get_current_user)):
    """获取用户问答统计"""
    try:
        filter_kwargs = {
            "limit": 1000,
            "order_by": "timestamp",
            "order_desc": True,
        }

        if workspace_id:
            filter_kwargs["workspace_id"] = workspace_id

        audit_filter = AuditFilter(**filter_kwargs)

        events = await audit_logger.query(audit_filter)

        qa_events = [e for e in events if "QA_ASK" in e.action]

        user_stats = {}
        for event in qa_events:
            actor_id = event.actor.actor_id if event.actor else "anonymous"
            if actor_id not in user_stats:
                user_stats[actor_id] = {
                    "user_id": actor_id,
                    "count": 0,
                    "first_time": event.timestamp,
                    "last_time": event.timestamp,
                }
            user_stats[actor_id]["count"] += 1
            if event.timestamp > user_stats[actor_id]["last_time"]:
                user_stats[actor_id]["last_time"] = event.timestamp
            if event.timestamp < user_stats[actor_id]["first_time"]:
                user_stats[actor_id]["first_time"] = event.timestamp

        sorted_users = sorted(
            user_stats.values(),
            key=lambda x: x["count"],
            reverse=True,
        )[:limit]

        return {
            "user_stats": sorted_users,
            "total_users": len(user_stats),
            "limit": limit,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/qa/stats/topics")
async def get_topic_stats(
    workspace_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user)):
    """获取话题统计"""
    try:
        filter_kwargs = {
            "limit": 1000,
            "order_by": "timestamp",
            "order_desc": True,
        }

        if workspace_id:
            filter_kwargs["workspace_id"] = workspace_id

        audit_filter = AuditFilter(**filter_kwargs)

        events = await audit_logger.query(audit_filter)
        qa_events = [e for e in events if "QA_ASK" in e.action]

        topic_counts = {}
        for event in qa_events:
            question = event.context.get("question", "") if event.context else ""
            if question:
                keywords = question.split()[:3]
                topic = " ".join(keywords)
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        return {
            "topics": [
                {"topic": t, "count": c, "trend": "stable"}
                for t, c in sorted_topics
            ],
            "limit": limit,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
