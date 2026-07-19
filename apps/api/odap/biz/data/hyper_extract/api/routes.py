"""Hyper-Extract API routes.

Provides direct HE extraction endpoints at /api/he/:
- POST /api/he/extract — combined extract + write
- GET /api/he/templates/{ontology_id} — generate template from ontology
- POST /api/he/extract/batch — batch extraction
- GET /api/he/progress/{session_id} — SSE progress stream
- GET /api/he/progress/{session_id}/status — get current progress
"""

import logging
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .schemas import ExtractRequest, ExtractResponse, TemplateResponse, BatchExtractRequest
from ..services.extract_service import ExtractService
from ..services.template_engine import TemplateEngine
from ..services.progress_manager import get_progress_manager
from ..impl.he_adapter import HEAdapter
from ..storage import Storage

logger = logging.getLogger("hyper_extract_routes")

router = APIRouter(prefix="/api/he", tags=["hyper-extract"])

extract_service = ExtractService()
template_engine = TemplateEngine(HEAdapter(), Storage())


@router.post("/extract", response_model=ExtractResponse)
async def extract(request: ExtractRequest):
    """触发知识提取：文本 → HE 提取 → 本体映射 → 双通道写入"""
    try:
        result = await extract_service.extract_and_write(
            text=request.text,
            ontology_id=request.ontology_id,
            scenario_id=request.scenario_id,
            workspace_id=request.workspace_id,
            template_override=request.template_override,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{ontology_id}", response_model=TemplateResponse)
async def get_template(ontology_id: str):
    """查看本体定义自动生成的 HE 模板"""
    try:
        template = template_engine.generate_from_ontology(ontology_id)
        if template.get("status") == "error":
            raise HTTPException(status_code=400, detail=template.get("message"))
        return TemplateResponse(ontology_id=ontology_id, template=template)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/batch")
async def extract_batch(request: BatchExtractRequest):
    """批量并行知识提取"""
    try:
        result = await extract_service.extract_batch(
            texts=request.texts,
            ontology_id=request.ontology_id,
            scenario_id=request.scenario_id,
            workspace_id=request.workspace_id,
            max_concurrency=request.max_concurrency,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress/{session_id}")
async def progress_stream(session_id: str):
    """SSE 进度流：订阅指定会话的实时进度更新"""

    async def event_generator() -> AsyncGenerator[str, None]:
        pm = await get_progress_manager()
        queue = await pm.subscribe(session_id)

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                import json

                yield f"data: {json.dumps(event)}\n\n"
        finally:
            await pm.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/progress/{session_id}/status")
async def get_progress_status(session_id: str):
    """获取指定会话的当前进度状态"""
    try:
        pm = await get_progress_manager()
        state = pm.get_progress(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="会话不存在或进度已过期")
        return {
            "session_id": session_id,
            "stage": state.stage,
            "progress_percent": state.progress_percent,
            "message": state.message,
            "current_step": state.current_step,
            "total_steps": state.total_steps,
            "is_completed": state.is_completed,
            "result": state.result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
