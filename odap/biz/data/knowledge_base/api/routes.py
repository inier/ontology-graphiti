from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import List, Optional
from pydantic import BaseModel, Field

from .schemas import (
    KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate,
    KnowledgeCategory, CategoryCreate,
    KnowledgeDocument,
)
from ..services.knowledge_base_service import KnowledgeBaseService


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    threshold: float = 0.3


class CrawlRequest(BaseModel):
    urls: List[str]
    max_depth: int = 1


class BuildGraphRequest(BaseModel):
    extraction_method: str = Field(default="auto", description="提取方式: regex/llm/auto")
    entity_types: List[str] = Field(default_factory=list, description="目标实体类型")


router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])

kb_service = KnowledgeBaseService.get_instance()


@router.get("", response_model=List[KnowledgeBase])
async def list_knowledge_bases():
    try:
        return kb_service.list_knowledge_bases()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}", response_model=KnowledgeBase)
async def get_knowledge_base(kb_id: str,
    user=Depends(get_current_user)):
    try:
        result = kb_service.get_knowledge_base(kb_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=KnowledgeBase)
async def create_knowledge_base(kb: KnowledgeBaseCreate):
    try:
        return kb_service.create_knowledge_base(kb.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{kb_id}", response_model=KnowledgeBase)
async def update_knowledge_base(kb_id: str, kb: KnowledgeBaseUpdate,
    user=Depends(get_current_user)):
    try:
        data = kb.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="无更新数据")
        result = kb_service.update_knowledge_base(kb_id, data)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: str,
    user=Depends(get_current_user)):
    try:
        result = kb_service.delete_knowledge_base(kb_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        return {"message": "知识库删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/categories", response_model=List[KnowledgeCategory])
async def list_categories(kb_id: str,
    user=Depends(get_current_user)):
    try:
        return kb_service.list_categories(kb_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_id}/categories", response_model=KnowledgeCategory)
async def create_category(kb_id: str, category: CategoryCreate,
    user=Depends(get_current_user)):
    try:
        return kb_service.create_category(kb_id, category.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{kb_id}/categories/{category_id}")
async def delete_category(kb_id: str, category_id: str,
    user=Depends(get_current_user)):
    try:
        result = kb_service.delete_category(kb_id, category_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "分类不存在"))
        return {"message": "分类删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/documents", response_model=List[KnowledgeDocument])
async def list_documents(kb_id: str, category_id: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    try:
        return kb_service.list_documents(kb_id, category_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_id}/documents", response_model=KnowledgeDocument)
async def upload_document(
    kb_id: str,
    title: str = Form(...),
    content_type: str = Form("text"),
    category_id: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user=Depends(get_current_user)):
    try:
        data = {
            'title': title,
            'content_type': content_type,
            'category_id': category_id,
            'content': content,
        }
        if file:
            file_content = await file.read()
            data['file_type'] = file.content_type
            data['file_size'] = len(file_content)
            data['content'] = file_content.decode('utf-8', errors='replace')
        return kb_service.create_document(kb_id, data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/documents/{doc_id}", response_model=KnowledgeDocument)
async def get_document(kb_id: str, doc_id: str,
    user=Depends(get_current_user)):
    try:
        result = kb_service.get_document(kb_id, doc_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "文档不存在"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str,
    user=Depends(get_current_user)):
    try:
        result = kb_service.delete_document(kb_id, doc_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "文档不存在"))
        return {"message": "文档删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{doc_id}/build-graph")
async def build_graph(doc_id: str, request: BuildGraphRequest = None,
    user=Depends(get_current_user)):
    try:
        req = request or BuildGraphRequest()
        result = await kb_service.build_graph(
            doc_id,
            extraction_method=req.extraction_method,
            entity_types=req.entity_types or None,
        )
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "文档不存在"))
        if isinstance(result, dict) and result.get("status") == "failed":
            raise HTTPException(status_code=500, detail=f"{result.get('method', '')}提取失败")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph-tasks/{task_id}")
async def get_graph_build_status(task_id: str,
    user=Depends(get_current_user)):
    try:
        result = kb_service.get_graph_build_status(task_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "任务不存在"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_id}/rag-query")
async def rag_query(kb_id: str, request: RAGQueryRequest,
    user=Depends(get_current_user)):
    try:
        result = await kb_service.rag_query(
            kb_id, request.query, top_k=request.top_k, threshold=request.threshold
        )
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_id}/crawl")
async def crawl_web(kb_id: str, request: CrawlRequest,
    user=Depends(get_current_user)):
    try:
        result = await kb_service.crawl_web(kb_id, request.urls, max_depth=request.max_depth)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
