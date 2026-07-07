from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import List, Optional
from pydantic import BaseModel, Field
import os
import re
import asyncio
import logging
import uuid as _uuid

from .schemas import (
    KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate,
    KnowledgeCategory, CategoryCreate,
    KnowledgeDocument,
)
from ..services.knowledge_base_service import KnowledgeBaseService
from ..services.cleaning_service import background_clean_and_update, CLEANING_LEVEL

logger = logging.getLogger(__name__)

# MinIO 配置
MINIO_BUCKET = "odap-documents"


def _get_minio():
    """获取 MinIO 客户端单例"""
    from odap.infra.storage.minio_client import get_minio_client
    return get_minio_client()


def _is_minio_key(file_url: str) -> bool:
    """判断 file_url 是否为 MinIO 对象 key（非旧的本地路径）"""
    return bool(file_url) and not file_url.startswith("/uploads/")


async def _notify_unified_ingest_facade(
    kb_id: str, doc_id: str, title: str, content_type: str, workspace_id: str = "default",
):
    """通知 UnifiedIngestFacade 发生了 KB 文档摄入事件（非阻塞）"""
    try:
        from odap.biz.data.ingest.unified_ingest_facade import get_unified_ingest_facade
        facade = get_unified_ingest_facade()
        await facade.ingest(
            source_type="kb_upload",
            kb_id=kb_id,
            doc_id=doc_id,
            title=title,
            content_type=content_type,
            workspace_id=workspace_id,
        )
    except Exception:
        pass  # 统一入口通知失败不影响上传主流程


def _attach_presigned_url(doc: dict) -> dict:
    """为文档附加 MinIO presigned URL（如果 file_url 是 MinIO key）"""
    if not doc or not doc.get("file_url") or not _is_minio_key(doc["file_url"]):
        return doc
    minio = _get_minio()
    if not minio.available:
        return doc
    result = minio.get_presigned_url(MINIO_BUCKET, doc["file_url"])
    if result.get("status") == "success":
        url = result["url"]
        # 将容器内部主机名替换为 localhost，让浏览器可以访问
        # MinIO 端口 9000 已通过 docker-compose 映射到宿主机
        endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
        internal_host = endpoint.replace("https://", "").replace("http://", "")
        if internal_host in url:
            url = url.replace(internal_host, "localhost:9000", 1)
        doc["presigned_url"] = url
    return doc


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


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "knowledge_base", workspace_id: str = "default"):
    """审计便捷函数"""
    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource="knowledge_base",
            user=user_id,
            service=service,
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


@router.get("", response_model=List[KnowledgeBase])
async def list_knowledge_bases():
    try:
        return kb_service.list_knowledge_bases()
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_list_failed", "anonymous", "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}", response_model=KnowledgeBase)
async def get_knowledge_base(kb_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = kb_service.get_knowledge_base(kb_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_get_failed", _uid, "failure", str(e), details={"kb_id": kb_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=KnowledgeBase)
async def create_knowledge_base(kb: KnowledgeBaseCreate,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = kb_service.create_knowledge_base(kb.model_dump())
        _audit("knowledge_base_create", _uid, "success", details={"name": kb.name})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_create_failed", _uid, "failure", str(e), details={"name": kb.name})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{kb_id}", response_model=KnowledgeBase)
async def update_knowledge_base(kb_id: str, kb: KnowledgeBaseUpdate,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        data = kb.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="无更新数据")
        result = kb_service.update_knowledge_base(kb_id, data)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        _audit("knowledge_base_update", _uid, "success", details={"kb_id": kb_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_update_failed", _uid, "failure", str(e), details={"kb_id": kb_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        # 先获取文档列表，用于 MinIO 批量清理
        docs = kb_service.list_documents(kb_id) or []
        result = kb_service.delete_knowledge_base(kb_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        # 批量清理 MinIO 对象
        minio = _get_minio()
        if minio.available:
            for doc in docs:
                if isinstance(doc, dict) and doc.get("file_url") and _is_minio_key(doc["file_url"]):
                    minio.delete_object(MINIO_BUCKET, doc["file_url"])
            logger.info("知识库 %s 的 MinIO 对象已清理（%d 个文档）", kb_id, len(docs))
        _audit("knowledge_base_delete", _uid, "success", details={"kb_id": kb_id})
        return {"message": "知识库删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_delete_failed", _uid, "failure", str(e), details={"kb_id": kb_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/categories", response_model=List[KnowledgeCategory])
async def list_categories(kb_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        return kb_service.list_categories(kb_id)
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_list_categories_failed", _uid, "failure", str(e), details={"kb_id": kb_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_id}/categories", response_model=KnowledgeCategory)
async def create_category(kb_id: str, category: CategoryCreate,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = kb_service.create_category(kb_id, category.model_dump())
        _audit("knowledge_base_create_category", _uid, "success", details={"kb_id": kb_id, "name": category.name})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_create_category_failed", _uid, "failure", str(e), details={"kb_id": kb_id, "name": category.name})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{kb_id}/categories/{category_id}")
async def delete_category(kb_id: str, category_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = kb_service.delete_category(kb_id, category_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "分类不存在"))
        _audit("knowledge_base_delete_category", _uid, "success", details={"kb_id": kb_id, "category_id": category_id})
        return {"message": "分类删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_delete_category_failed", _uid, "failure", str(e), details={"kb_id": kb_id, "category_id": category_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/graph")
async def get_kb_graph(kb_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        kb = kb_service.get_knowledge_base(kb_id)
        if isinstance(kb, dict) and kb.get("status") == "error":
            raise HTTPException(status_code=404, detail=kb.get("message", "知识库不存在"))
        result = kb_service.get_kb_graph(kb_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_get_graph_failed", _uid, "failure", str(e), details={"kb_id": kb_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/documents", response_model=List[KnowledgeDocument])
async def list_documents(kb_id: str, category_id: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        docs = kb_service.list_documents(kb_id, category_id)
        return [_attach_presigned_url(d) for d in docs]
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_list_documents_failed", _uid, "failure", str(e), details={"kb_id": kb_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_id}/documents", response_model=KnowledgeDocument)
async def upload_document(
    kb_id: str,
    title: str = Form(""),
    content_type: str = Form("text"),
    category_id: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    web_url: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user=Depends(get_current_user)):
    """统一入口 → 知识库子路由

    文档上传端点，通过 UnifiedIngestFacade 统一摄入架构路由。
    支持：文本粘贴、文件上传（MinIO/本地）、在线文档/网页抓取。
    上传完成后自动触发后台清洗和实体抽取。
    """
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        final_title = title or (file.filename if file and file.filename else "") or "未命名文档"

        data = {
            'title': final_title,
            'content_type': content_type if content_type != 'text' or not file else 'file',
            'category_id': category_id,
            'content': content,
        }

        # 在线文档 / 网页抓取：从 URL 获取内容
        if content_type in ('online_doc', 'web_crawl') and web_url:
            data['web_url'] = web_url
            data['content_type'] = 'web'
            if not title:
                data['title'] = web_url
            fetched_content = ""
            try:
                from odap.infra.utils.web_scraper import WebScraper
                scraper = WebScraper()
                raw = scraper.fetch_url(web_url)
                if raw:
                    fetched_content = scraper.extract_text(raw) or ""
            except Exception:
                try:
                    import urllib.request
                    resp = urllib.request.urlopen(web_url, timeout=15)
                    html = resp.read().decode("utf-8", errors="replace")
                    fetched_content = re.sub(r"<[^>]+>", " ", html)
                    fetched_content = re.sub(r"\s+", " ", fetched_content).strip()
                except Exception as e:
                    logger.warning("网页抓取失败: %s — %s", web_url, e)
            if fetched_content:
                data['content'] = fetched_content[:50000]
                data['file_type'] = 'text/html'
                data['file_size'] = len(fetched_content.encode('utf-8', errors='replace'))
            else:
                data['content'] = ""
                data['file_type'] = 'text/html'
                data['file_size'] = 0

        if file:
            file_content = await file.read()
            data['file_type'] = file.content_type
            data['file_size'] = len(file_content)
            _text_types = {'text/plain', 'text/markdown', 'text/csv', 'text/html', 'application/json'}
            if (file.content_type or '').startswith('text/') or file.content_type in _text_types:
                # 文本类文件：内容直接存数据库，不上传到 MinIO
                data['content'] = file_content.decode('utf-8', errors='replace')
                data['file_url'] = None
            else:
                # 二进制文件：上传到 MinIO 对象存储
                safe_filename = file.filename or f"file_{_uuid.uuid4().hex[:8]}"
                ext = os.path.splitext(safe_filename)[1]
                stem = os.path.splitext(safe_filename)[0][:50]
                unique_name = f"{stem}_{_uuid.uuid4().hex[:6]}{ext}"
                object_key = f"kb/{kb_id}/{unique_name}"

                minio = _get_minio()

                # 先确保 bucket 存在；失败则直接降级到本地存储
                upload_result = None
                if minio.available:
                    bucket_result = minio.ensure_bucket(MINIO_BUCKET)
                    if bucket_result.get("status") == "success":
                        upload_result = minio.upload_object(
                            bucket=MINIO_BUCKET,
                            key=object_key,
                            data=file_content,
                            content_type=file.content_type or "application/octet-stream",
                        )
                    else:
                        logger.warning(
                            "MinIO ensure_bucket 失败，跳过上传: %s",
                            bucket_result.get("message"),
                        )

                if upload_result and upload_result.get("status") == "success":
                    data['file_url'] = object_key
                    logger.info("文件已上传到 MinIO: bucket=%s, key=%s", MINIO_BUCKET, object_key)
                else:
                    # MinIO 不可用或上传失败时降级到本地磁盘
                    _reason = upload_result.get("message", "MinIO client unavailable") if upload_result else "ensure_bucket failed or client unavailable"
                    logger.warning("MinIO 上传失败，降级到本地存储: %s", _reason)
                    _fallback_dir = os.path.join(
                        os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data")),
                        "uploads", "kb", kb_id
                    )
                    os.makedirs(_fallback_dir, exist_ok=True)
                    file_path = os.path.join(_fallback_dir, unique_name)
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                    data['file_url'] = f"/uploads/kb/{kb_id}/{unique_name}"

                # 文本内容保留前 2000 字符作为预览
                try:
                    data['content'] = file_content.decode('utf-8', errors='replace')[:2000]
                except Exception:
                    data['content'] = None

        result = kb_service.create_document(kb_id, data)

        # 统一入口通知：通过 UnifiedIngestFacade 记录摄入事件
        doc_id = result.get("doc_id") if isinstance(result, dict) else None
        if doc_id:
            asyncio.create_task(_notify_unified_ingest_facade(
                kb_id=kb_id,
                doc_id=doc_id,
                title=final_title,
                content_type=data.get('content_type', 'text'),
                workspace_id="default",
            ))

        # 后台异步清洗：不阻塞上传响应
        raw_content = data.get('content')
        if raw_content and raw_content.strip():
            cleaning_level = os.environ.get("CLEANING_LEVEL", "basic").lower()
            doc_id = result.get("doc_id") if isinstance(result, dict) else None
            if doc_id:
                asyncio.create_task(
                    background_clean_and_update(
                        doc_id=doc_id,
                        kb_id=kb_id,
                        raw_content=raw_content,
                        level=cleaning_level,
                    )
                )
                logger.info("已启动文档 %s 的后台清洗任务 (level=%s)", doc_id, cleaning_level)

        _audit("knowledge_base_upload_document", _uid, "success", details={"kb_id": kb_id, "title": final_title})
        return _attach_presigned_url(result) if isinstance(result, dict) else result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_upload_document_failed", _uid, "failure", str(e), details={"kb_id": kb_id, "title": title})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}/documents/{doc_id}", response_model=KnowledgeDocument)
async def get_document(kb_id: str, doc_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = kb_service.get_document(kb_id, doc_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "文档不存在"))
        return _attach_presigned_url(result)
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_get_document_failed", _uid, "failure", str(e), details={"kb_id": kb_id, "doc_id": doc_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        # 先获取文档信息，用于 MinIO 清理
        doc = kb_service.get_document(kb_id, doc_id)
        result = kb_service.delete_document(kb_id, doc_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "文档不存在"))
        # 清理 MinIO 对象
        if isinstance(doc, dict) and doc.get("file_url") and _is_minio_key(doc["file_url"]):
            minio = _get_minio()
            if minio.available:
                del_result = minio.delete_object(MINIO_BUCKET, doc["file_url"])
                if del_result.get("status") == "success":
                    logger.info("MinIO 对象已删除: %s", doc["file_url"])
        _audit("knowledge_base_delete_document", _uid, "success", details={"kb_id": kb_id, "doc_id": doc_id})
        return {"message": "文档删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_delete_document_failed", _uid, "failure", str(e), details={"kb_id": kb_id, "doc_id": doc_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{doc_id}/build-graph")
async def build_graph(doc_id: str, request: BuildGraphRequest = None,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
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
            error_msg = result.get("error") or f"{result.get('method', '')}提取失败"
            raise HTTPException(status_code=500, detail=error_msg)
        _audit("knowledge_base_build_graph", _uid, "success", details={"doc_id": doc_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_build_graph_failed", _uid, "failure", str(e), details={"doc_id": doc_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph-tasks/{task_id}")
async def get_graph_build_status(task_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = kb_service.get_graph_build_status(task_id)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "任务不存在"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_get_graph_task_failed", _uid, "failure", str(e), details={"task_id": task_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_id}/rag-query")
async def rag_query(kb_id: str, request: RAGQueryRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = await kb_service.rag_query(
            kb_id, request.query, top_k=request.top_k, threshold=request.threshold
        )
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        _audit("knowledge_base_rag_query", _uid, "success", details={"kb_id": kb_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_rag_query_failed", _uid, "failure", str(e), details={"kb_id": kb_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_id}/crawl")
async def crawl_web(kb_id: str, request: CrawlRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = await kb_service.crawl_web(kb_id, request.urls, max_depth=request.max_depth)
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "知识库不存在"))
        _audit("knowledge_base_crawl", _uid, "success", details={"kb_id": kb_id, "url_count": len(request.urls)})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("knowledge_base_crawl_failed", _uid, "failure", str(e), details={"kb_id": kb_id})
        raise HTTPException(status_code=500, detail=str(e))
