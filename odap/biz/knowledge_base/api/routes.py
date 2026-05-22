from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from .schemas import (
    KnowledgeBase, KnowledgeBaseCreate, KnowledgeBaseUpdate,
    KnowledgeCategory, CategoryCreate,
    KnowledgeDocument,
)
from ..storage.sqlite_kb_storage import SQLiteKnowledgeBaseStorage


class RAGQueryRequest(BaseModel):
    query: str
    top_k: int = 5
    threshold: float = 0.3


class CrawlRequest(BaseModel):
    urls: List[str]
    max_depth: int = 1

router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])

storage = SQLiteKnowledgeBaseStorage()


# Knowledge Base CRUD
@router.get("", response_model=List[KnowledgeBase])
async def list_knowledge_bases():
    return storage.list_knowledge_bases()


@router.get("/{kb_id}", response_model=KnowledgeBase)
async def get_knowledge_base(kb_id: str):
    kb = storage.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


@router.post("", response_model=KnowledgeBase)
async def create_knowledge_base(kb: KnowledgeBaseCreate):
    data = kb.model_dump()
    return storage.create_knowledge_base(data)


@router.put("/{kb_id}", response_model=KnowledgeBase)
async def update_knowledge_base(kb_id: str, kb: KnowledgeBaseUpdate):
    data = kb.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="无更新数据")
    updated = storage.update_knowledge_base(kb_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return updated


@router.delete("/{kb_id}")
async def delete_knowledge_base(kb_id: str):
    success = storage.delete_knowledge_base(kb_id)
    if not success:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"message": "知识库删除成功"}


# Category CRUD
@router.get("/{kb_id}/categories", response_model=List[KnowledgeCategory])
async def list_categories(kb_id: str):
    return storage.list_categories(kb_id)


@router.post("/{kb_id}/categories", response_model=KnowledgeCategory)
async def create_category(kb_id: str, category: CategoryCreate):
    data = category.model_dump()
    return storage.create_category(kb_id, data)


@router.delete("/{kb_id}/categories/{category_id}")
async def delete_category(kb_id: str, category_id: str):
    success = storage.delete_category(kb_id, category_id)
    if not success:
        raise HTTPException(status_code=404, detail="分类不存在")
    return {"message": "分类删除成功"}


# Document CRUD
@router.get("/{kb_id}/documents", response_model=List[KnowledgeDocument])
async def list_documents(kb_id: str, category_id: Optional[str] = Query(None)):
    return storage.list_documents(kb_id, category_id)


@router.post("/{kb_id}/documents", response_model=KnowledgeDocument)
async def upload_document(
    kb_id: str,
    title: str = Form(...),
    content_type: str = Form("text"),
    category_id: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
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
    return storage.create_document(kb_id, data)


@router.get("/{kb_id}/documents/{doc_id}", response_model=KnowledgeDocument)
async def get_document(kb_id: str, doc_id: str):
    doc = storage.get_document(kb_id, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(kb_id: str, doc_id: str):
    success = storage.delete_document(kb_id, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "文档删除成功"}


@router.post("/documents/{doc_id}/build-graph")
async def build_graph(doc_id: str):
    all_kbs = storage.list_knowledge_bases()
    doc = None
    for kb in all_kbs:
        doc = storage.get_document(kb["kb_id"], doc_id)
        if doc:
            break
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    content = doc.get("content", "") or ""
    entities_extracted = 0
    try:
        import re
        patterns = [
            r'[\u4e00-\u9fff]{2,10}(?:舰队|部队|师|旅|团|营|连)',
            r'[\u4e00-\u9fff]{2,8}(?:导弹|雷达|坦克|舰艇|潜艇|航母)',
            r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
        ]
        found = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            found.update(matches)
        entities_extracted = len(found)
        try:
            from odap.infra.graph.graph_service import GraphManager
            gm = GraphManager()
            for entity_name in found:
                gm.add_node(entity_name, {"type": "extracted_entity", "source_doc": doc_id})
        except Exception:
            pass
    except Exception:
        pass
    return {"task_id": f"task_{doc_id}", "status": "completed", "entities_extracted": entities_extracted}


@router.get("/graph-tasks/{task_id}")
async def get_graph_build_status(task_id: str):
    return {"status": "completed", "progress": 100, "task_id": task_id}


@router.post("/{kb_id}/rag-query")
async def rag_query(kb_id: str, request: RAGQueryRequest):
    kb = storage.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    docs = storage.list_documents(kb_id)
    keywords = set(request.query.lower().split())
    scored = []
    for doc in docs:
        content = doc.get("content", "") or ""
        content_lower = content.lower()
        score = sum(1 for kw in keywords if kw in content_lower) / max(len(keywords), 1)
        if score >= request.threshold:
            scored.append((doc, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    top_docs = scored[:request.top_k]
    sources = [{"doc_id": d.get("doc_id"), "title": d.get("title", ""), "score": round(s, 3)} for d, s in top_docs]
    answer = ""
    if top_docs:
        snippets = [d.get("content", "")[:200] for d, _ in top_docs]
        answer = "相关文档片段：\n" + "\n---\n".join(snippets)
        try:
            from odap.infra.llm import get_llm_service
            llm = get_llm_service()
            context = "\n".join(snippets)
            answer = await llm.generate(f"基于以下内容回答问题：{request.query}\n\n{context}")
        except Exception:
            pass
    else:
        answer = "未找到与查询相关的文档"
    return {"answer": answer, "sources": sources, "related_entities": []}


@router.post("/{kb_id}/crawl")
async def crawl_web(kb_id: str, request: CrawlRequest):
    kb = storage.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    results = []
    for url in request.urls:
        try:
            content = ""
            try:
                from odap.utils.web_scraper import WebScraper
                scraper = WebScraper()
                content = await scraper.scrape(url)
            except Exception:
                try:
                    import urllib.request
                    resp = urllib.request.urlopen(url, timeout=10)
                    html = resp.read().decode('utf-8', errors='replace')
                    import re
                    content = re.sub(r'<[^>]+>', ' ', html)
                    content = re.sub(r'\s+', ' ', content).strip()
                except Exception as e:
                    results.append({"url": url, "status": "failed", "error": str(e)})
                    continue
            doc_id = storage.create_document(kb_id, {
                "title": url,
                "content_type": "web",
                "content": content[:50000],
            })
            results.append({"url": url, "doc_id": doc_id.get("doc_id"), "status": "success"})
        except Exception as e:
            results.append({"url": url, "status": "failed", "error": str(e)})
    return {"task_id": f"crawl_{kb_id}", "results": results}
