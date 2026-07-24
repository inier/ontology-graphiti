"""Extraction API routes.

遵循 AGENTS.md 规则：
- 路由前缀统一 /api/extraction
- except HTTPException: raise 必须透传
- 服务层返回 Dict，路由层翻译错误为 HTTPException
"""

import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from odap.biz.core.ontology.extraction.services.extraction_service import ExtractionService
from odap.biz.core.ontology.extraction.models.schemas import (
    DatabaseConnectionRequest,
    DatabaseTestConnectionResponse,
    DatabaseExtractionRequest,
    NLExtractionRequest,
    KBExtractionRequest,
    ExtractionSessionResponse,
    ExtractionConfirmRequest,
)
from odap.biz.data.hyper_extract.services.progress_manager import get_progress_manager
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.sse_utils import progress_event_generator, sse_response
from odap.infra.upload_utils import stream_upload_to_file, check_upload_size

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt", ".md", ".csv",
    ".xlsx", ".xls", ".json", ".xml",
    ".jpg", ".jpeg", ".png", ".tiff",
}
MAX_FILE_SIZE = 100 * 1024 * 1024

router = APIRouter(prefix="/api/extraction", tags=["extraction"])
_extraction_service = ExtractionService()


@router.post("/test-connection", response_model=DatabaseTestConnectionResponse)
async def test_database_connection(
    request: DatabaseConnectionRequest,
    user=Depends(get_current_user),
):
    """Test database connection and return table count."""
    try:
        result = _extraction_service.test_database_connection(
            db_type=request.db_type,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/database")
async def extract_from_database(
    request: DatabaseExtractionRequest,
    user=Depends(get_current_user),
):
    """Extract schema from database and create extraction session."""
    try:
        result = _extraction_service.extract_from_database(
            ontology_id=request.ontology_id,
            db_type=request.db_type,
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password,
            table_filter=request.table_filter if request.table_filter else None,
            use_llm_enrichment=request.use_llm_enrichment,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Extraction failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/natural-language")
async def extract_from_natural_language(
    request: NLExtractionRequest,
    user=Depends(get_current_user),
):
    """Extract schema from natural language description using LLM.

    Uses simple ChatOpenAI-based extraction (not hyper-extract) for
    compatibility with non-OpenAI endpoints (NVIDIA NIM, etc.).
    """
    try:
        result = _extraction_service.simple_nl_extract(request.text)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Extraction failed"))

        session_id = result.get("session_id", "")
        if session_id:
            _extraction_service.ontology_service.create_extraction_session(
                ontology_id=request.ontology_id,
                extraction_type="natural_language",
                input_data={"text": request.text},
                session_id=session_id,
            )
            _extraction_service.ontology_service.update_extraction_session(
                session_id,
                {"status": "completed", "result_data": result.get("result", {})},
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/document")
async def extract_from_document(
    ontology_id: str = Form(...),
    file: UploadFile = File(...),
    template_id: str = Form(None),
    method: str = Form(None),
    user=Depends(get_current_user),
):
    """Extract schema from an uploaded document file."""
    import os
    import tempfile
    import uuid

    try:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        # P3-M9: 预检 Content-Length，提前拒绝超大文件（避免无谓的磁盘写入）
        check_upload_size(file, MAX_FILE_SIZE)

        tmp_dir = tempfile.mkdtemp()
        # 安全：丢弃用户提供的 filename，使用 uuid 防止路径穿越（CRITICAL-4 修复）
        safe_name = f"{uuid.uuid4().hex}{ext}"
        tmp_path = os.path.join(tmp_dir, safe_name)
        # 深度防御：断言最终路径仍在 tmp_dir 内
        if not os.path.realpath(tmp_path).startswith(os.path.realpath(tmp_dir) + os.sep):
            raise HTTPException(status_code=400, detail="Invalid file path")
        try:
            # P3-M9: 流式分块写盘，避免大文件一次性读入内存导致 OOM
            await stream_upload_to_file(file, tmp_path, max_size=MAX_FILE_SIZE)

            result = await _extraction_service.extract_from_document(
                ontology_id=ontology_id,
                file_path=tmp_path,
                template_id=template_id,
                method=method,
            )
            if result.get("status") == "error":
                raise HTTPException(status_code=400, detail=result.get("message", "Extraction failed"))
            return result
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/knowledge-base")
async def extract_from_knowledge_base(
    request: KBExtractionRequest,
    user=Depends(get_current_user),
):
    """Extract schema from a knowledge base using simple LLM extraction.

    Bypasses hyper-extract due to compatibility issues with non-OpenAI endpoints.
    Reads KB documents, concatenates text, and extracts via LLM.
    """
    import uuid
    try:
        # Read KB documents
        from odap.biz.data.knowledge_base.services import get_kb_service
        kb_service = get_kb_service()
        kb = kb_service.get_knowledge_base(request.kb_id)
        if not kb or kb.get("status") == "error":
            raise HTTPException(status_code=400, detail=f"Knowledge base '{request.kb_id}' not found")

        docs = kb_service.list_documents(request.kb_id)
        if not docs:
            raise HTTPException(status_code=400, detail=f"Knowledge base '{request.kb_id}' is empty")

        # Filter and extract text
        doc_ids = set(request.document_ids) if request.document_ids else None
        texts = []
        processed_count = 0
        for doc in docs:
            if doc_ids and doc.get("doc_id") not in doc_ids:
                continue
            content = doc.get("cleaned_content", "") or doc.get("content", "") or ""
            if content.strip():
                texts.append(content[:2000])  # Truncate per doc to stay within limits
            processed_count += 1

        if not texts:
            raise HTTPException(status_code=400, detail="No text content found in knowledge base documents")

        combined_text = "\n\n".join(texts)

        # Use simple NL extraction (P3-M8: 调用 service 层方法)
        nl_result = _extraction_service.simple_nl_extract(combined_text)

        if nl_result.get("status") == "error":
            raise HTTPException(status_code=400, detail=nl_result.get("message", "Extraction failed"))

        session_id = str(uuid.uuid4())
        nl_result_data = nl_result.get("result", {})
        result = {
            "status": "ok",
            "session_id": session_id,
            "result": {
                "entities": nl_result_data.get("entities", []),
                "relations": nl_result_data.get("relations", []),
                "object_types": nl_result_data.get("object_types", []),
                "link_types": nl_result_data.get("link_types", []),
                "action_types": nl_result_data.get("action_types", []),
                "rule_types": nl_result_data.get("rule_types", []),
                "process_types": nl_result_data.get("process_types", []),
                "indicator_types": nl_result_data.get("indicator_types", []),
                "conflicts": [],
            },
            "conflicts": [],
            "source": "simple_kb_extract",
            "summary": nl_result.get("summary", {}),
            "provenance_summary": {
                "kb_id": request.kb_id,
                "total_documents": len(docs),
                "processed_documents": processed_count,
            },
        }

        _extraction_service.ontology_service.create_extraction_session(
            ontology_id=request.ontology_id,
            extraction_type="knowledge_base",
            input_data={"kb_id": request.kb_id, "document_ids": request.document_ids},
            session_id=session_id,
        )
        _extraction_service.ontology_service.update_extraction_session(
            session_id,
            {"status": "completed", "result_data": result.get("result", {})},
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("extract_from_knowledge_base failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates(
    user=Depends(get_current_user),
):
    """List available HE templates."""
    try:
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        from odap.biz.data.hyper_extract.storage import Storage

        engine = TemplateEngine(HEAdapter(), Storage())
        presets = engine.list_presets()
        return {"status": "ok", "templates": presets}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates/recommend")
async def recommend_templates(
    request: dict,
    user=Depends(get_current_user),
):
    """Recommend templates based on text description."""
    try:
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        from odap.biz.data.hyper_extract.storage import Storage

        text = request.get("text", "")
        ontology_id = request.get("ontology_id", "")

        engine = TemplateEngine(HEAdapter(), Storage())
        assess_result = engine.assess(text, ontology_id)
        candidates = assess_result.get("candidates", [])
        return {"status": "ok", "templates": candidates, "assessment": assess_result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates/generate-web-search")
async def generate_template_web_search(
    request: dict,
    user=Depends(get_current_user),
):
    """Generate template via web search."""
    try:
        from odap.biz.data.hyper_extract.services.template_engine import TemplateEngine
        from odap.biz.data.hyper_extract.impl.he_adapter import HEAdapter
        from odap.biz.data.hyper_extract.storage import Storage

        text = request.get("text", "")
        ontology_id = request.get("ontology_id", "")

        engine = TemplateEngine(HEAdapter(), Storage())
        template = engine.generate_custom_with_fallback(
            text=text,
            ontology_schema={},
            gaps=["object", "relation", "action", "rule", "process"],
            ontology_id=ontology_id,
        )
        if template:
            return {"status": "ok", "template": template}
        return {"status": "ok", "template": None, "message": "No template generated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provenance/{entity_id}")
async def get_provenance(
    entity_id: str,
    user=Depends(get_current_user),
):
    """Get extraction provenance for an entity."""
    try:
        from odap.biz.data.hyper_extract.impl.provenance_tracker import ProvenanceTracker

        tracker = ProvenanceTracker()
        provenance = tracker.get_provenance(entity_id)
        if not provenance:
            raise HTTPException(status_code=404, detail="Provenance not found")
        return {"status": "ok", "provenance": provenance}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provenance/by-source/{doc_id}")
async def get_provenance_by_source(
    doc_id: str,
    user=Depends(get_current_user),
):
    """Get all entities extracted from a source document."""
    try:
        from odap.biz.data.hyper_extract.impl.provenance_tracker import ProvenanceTracker

        tracker = ProvenanceTracker()
        entities = tracker.get_entities_by_source(doc_id)
        return {"status": "ok", "entities": entities}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=ExtractionSessionResponse)
async def get_extraction_session(
    session_id: str,
    user=Depends(get_current_user),
):
    """Get extraction session details."""
    try:
        result = _extraction_service.get_session(session_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/confirm")
async def confirm_extraction(
    session_id: str,
    request: ExtractionConfirmRequest,
    user=Depends(get_current_user),
):
    """Confirm and import extraction results into ontology."""
    try:
        result = await _extraction_service.confirm_extraction(
            session_id=session_id,
            selected=request.selected if request.selected else None,
            data=request.data if request.data else None,
            merge_strategy=request.merge_strategy,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/progress/{session_id}")
async def extraction_progress_stream(
    session_id: str,
    user=Depends(get_current_user),
):
    """SSE 进度流：订阅指定提取会话的实时进度更新。

    P0-M1 IDOR 整改：订阅前校验调用者是否为该 session 的 owner（或 admin）。
    """
    pm = await get_progress_manager()
    existing_state = await pm.get_state(session_id)
    if existing_state and not existing_state.is_owned_by(user):
        logger.warning("IDOR blocked on extraction SSE: caller=%s session=%s",
                       user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous",
                       session_id)
        raise HTTPException(status_code=403, detail="无权订阅该会话的进度")

    async def event_generator() -> AsyncGenerator[str, None]:
        # P3-M7: 使用公共生成器，带 15s 心跳保活，防止 nginx idle 超时切断
        async for chunk in progress_event_generator(pm, session_id):
            yield chunk

    return sse_response(event_generator())


@router.get("/progress/{session_id}/status")
async def get_extraction_progress_status(
    session_id: str,
    user=Depends(get_current_user),
):
    """获取指定提取会话的当前进度状态。

    P0-M1 IDOR 整改：非 owner 非 admin 拒绝访问。
    """
    try:
        pm = await get_progress_manager()
        state = await pm.get_state(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="会话不存在或进度已过期")
        if not state.is_owned_by(user):
            logger.warning("IDOR blocked on extraction progress status: caller=%s session=%s",
                           user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous",
                           session_id)
            raise HTTPException(status_code=403, detail="无权查看该会话进度")
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
