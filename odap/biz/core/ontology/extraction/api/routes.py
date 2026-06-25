"""Extraction API routes.

遵循 AGENTS.md 规则：
- 路由前缀统一 /api/extraction
- except HTTPException: raise 必须透传
- 服务层返回 Dict，路由层翻译错误为 HTTPException
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form

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
from odap.infra.security.jwt_auth import get_current_user

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
    """Extract schema from natural language description using LLM."""
    try:
        result = await _extraction_service.extract_from_nl(
            ontology_id=request.ontology_id,
            text=request.text,
            auto_search=request.auto_search,
            template_id=request.template_id,
            method=request.method,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Extraction failed"))
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
    """Extract schema from a knowledge base and create extraction session."""
    try:
        result = await _extraction_service.extract_from_knowledge_base(
            ontology_id=request.ontology_id,
            kb_id=request.kb_id,
            template_id=request.template_id,
            method=request.method,
            document_ids=request.document_ids if request.document_ids else None,
            batch_size=request.batch_size,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Extraction failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
async def list_templates(
    user=Depends(get_current_user),
):
    """List available HE templates."""
    try:
        from odap.biz.core.ontology.extraction.impl.template_generator import TemplateGenerator

        generator = TemplateGenerator()
        presets = generator.list_all_presets()
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
        from odap.biz.core.ontology.extraction.impl.template_generator import TemplateGenerator

        text = request.get("text", "")
        top_k = request.get("top_k", 3)

        generator = TemplateGenerator()
        recommendations = generator.recommend_templates(text, top_k=top_k)
        return {"status": "ok", "templates": recommendations}
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
        from odap.biz.core.ontology.extraction.impl.template_generator import TemplateGenerator

        text = request.get("text", "")

        generator = TemplateGenerator()
        template = generator.generate_with_web_search(text)
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
        from odap.biz.core.ontology.extraction.impl.provenance_tracker import ProvenanceTracker

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
        from odap.biz.core.ontology.extraction.impl.provenance_tracker import ProvenanceTracker

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
            selected_type_ids=request.selected_type_ids if request.selected_type_ids else None,
            merge_strategy=request.merge_strategy,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
