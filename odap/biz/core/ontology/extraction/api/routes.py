"""Extraction API routes.

遵循 AGENTS.md 规则：
- 路由前缀统一 /api/extraction
- except HTTPException: raise 必须透传
- 服务层返回 Dict，路由层翻译错误为 HTTPException
"""

from fastapi import APIRouter, HTTPException, Depends

from odap.biz.core.ontology.extraction.services.extraction_service import ExtractionService
from odap.biz.core.ontology.extraction.models.schemas import (
    DatabaseConnectionRequest,
    DatabaseTestConnectionResponse,
    DatabaseExtractionRequest,
    NLExtractionRequest,
    ExtractionSessionResponse,
    ExtractionConfirmRequest,
)
from odap.infra.security.jwt_auth import get_current_user

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
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Extraction failed"))
        return result
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
        result = _extraction_service.confirm_extraction(
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
