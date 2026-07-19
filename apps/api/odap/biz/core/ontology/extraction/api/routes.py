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


def _simple_nl_extract(text: str, is_async: bool = False) -> dict:
    """Simple NL extraction using ChatOpenAI directly — bypasses hyper-extract.

    Hyper-extract has compatibility issues with non-OpenAI endpoints (NVIDIA NIM,
    custom proxies) due to embeddings, YAML expectations, and parallel LLM calls
    that exhaust rate limits. This function provides a reliable fallback.
    """
    import json as _json
    import os as _os
    import uuid as _uuid
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage

    # Use env var directly to avoid config encryption key mismatch
    # (config DB auto-populates from env but encrypts with a per-process key)
    api_key = _os.environ.get("OPENAI_API_KEY", "")
    api_base = _os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
    model = _os.environ.get("OPENAI_MODEL", "gpt-4o")

    if not api_key:
        return {"status": "error", "message": "LLM API key not configured"}

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=api_base,
        temperature=0,
    )

    prompt = (
        "你是一个本体设计专家。请从以下自然语言描述中提取结构化的类型定义。\n\n"
        "返回一个JSON对象，包含以下键：\n"
        '- "object_types": 对象类型列表，每个有 name (英文snake_case), display_name (中文), description\n'
        '- "link_types": 关系类型列表，每个有 name, source_type, target_type, description\n'
        '- "action_types": 动作类型列表，每个有 name, description\n'
        '- "rule_types": 规则类型列表，每个有 name, description\n'
        '- "process_types": 业务流程类型列表，每个有 name, description\n'
        '- "indicator_types": 指标类型列表，每个有 name, indicator_type (kpi/metric/dimension), formula, unit\n\n'
        "IMPORTANT: 只返回有效的JSON对象。不要markdown，不要解释，不要代码块。\n\n"
        f"自然语言描述：\n{text[:3000]}"
    )

    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        content = resp.content if hasattr(resp, "content") else str(resp)
    except Exception as e:
        return {"status": "error", "message": f"LLM call failed: {type(e).__name__}: {e}"}

    if not content or not content.strip():
        return {"status": "error", "message": "LLM returned empty response"}

    # Parse JSON from response (handle prefix text like "我们{...}")
    for i, ch in enumerate(content):
        if ch in "{[":
            try:
                parsed = _json.loads(content[i:])
                break
            except _json.JSONDecodeError:
                continue
    else:
        return {"status": "error", "message": "Failed to parse LLM response as JSON", "raw": content[:200]}

    if not isinstance(parsed, dict):
        return {"status": "error", "message": "LLM response is not a JSON object"}

    session_id = str(_uuid.uuid4())
    result = {
        "status": "ok",
        "session_id": session_id,
        "result": {
            "object_types": parsed.get("object_types", []),
            "link_types": parsed.get("link_types", []),
            "action_types": parsed.get("action_types", []),
            "rule_types": parsed.get("rule_types", []),
            "process_types": parsed.get("process_types", []),
            "indicator_types": parsed.get("indicator_types", []),
            "entities": [],
            "relations": [],
            "conflicts": [],
        },
        "conflicts": [],
        "source": "simple_nl_extract",
        "summary": {
            "object_types": len(parsed.get("object_types", [])),
            "link_types": len(parsed.get("link_types", [])),
            "action_types": len(parsed.get("action_types", [])),
            "rule_types": len(parsed.get("rule_types", [])),
            "process_types": len(parsed.get("process_types", [])),
            "indicator_types": len(parsed.get("indicator_types", [])),
        },
    }
    return result

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
        result = _simple_nl_extract(request.text)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Extraction failed"))

        from odap.biz.core.ontology.ontology_api.services import get_ontology_service

        session_id = result.get("session_id", "")
        if session_id:
            ontology_service = get_ontology_service()
            ontology_service.create_extraction_session(
                ontology_id=request.ontology_id,
                extraction_type="natural_language",
                input_data={"text": request.text},
                session_id=session_id,
            )
            ontology_service.update_extraction_session(
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

    try:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        contents = await file.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {len(contents)} bytes. Maximum: {MAX_FILE_SIZE} bytes (100 MB)",
            )

        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, file.filename or "upload")
        try:
            with open(tmp_path, "wb") as f:
                f.write(contents)

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

        # Use simple NL extraction
        nl_result = _simple_nl_extract(combined_text)

        if nl_result.get("status") == "error":
            raise HTTPException(status_code=400, detail=nl_result.get("message", "Extraction failed"))

        # Wrap in the format frontend expects (with result sub-dict)
        session_id = str(uuid.uuid4())
        return {
            "status": "ok",
            "session_id": session_id,
            "result": {
                "entities": nl_result.get("entities", []),
                "relations": nl_result.get("relations", []),
                "object_types": nl_result.get("object_types", []),
                "link_types": nl_result.get("link_types", []),
                "action_types": nl_result.get("action_types", []),
                "rule_types": nl_result.get("rule_types", []),
                "process_types": nl_result.get("process_types", []),
                "indicator_types": nl_result.get("indicator_types", []),
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
    """SSE 进度流：订阅指定提取会话的实时进度更新"""

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
async def get_extraction_progress_status(
    session_id: str,
    user=Depends(get_current_user),
):
    """获取指定提取会话的当前进度状态"""
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
