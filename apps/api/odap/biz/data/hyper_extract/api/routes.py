"""Hyper-Extract API routes.

Provides direct HE extraction endpoints at /api/he/:
- POST /api/he/extract — combined extract + write
- GET /api/he/templates/{ontology_id} — generate template from ontology
- POST /api/he/extract/batch — batch extraction
"""

import logging
from fastapi import APIRouter, HTTPException

from .schemas import ExtractRequest, ExtractResponse, TemplateResponse, BatchExtractRequest
from ..services.extract_service import ExtractService
from ..services.template_engine import TemplateEngine
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
