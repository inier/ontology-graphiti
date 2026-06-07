"""
UnstructuredSourceImpl — 非结构化数据源实现。

包装 SemanticObjectRetriever，向上提供 QueryService 兼容的 search() 接口。

数据流：
    QueryService → UnstructuredSource.search()
        → SemanticObjectRetriever.retrieve()
        → object_service.semantic_query()
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UnstructuredSourceImpl:
    """非结构化数据源：基于 object_service 的语义检索。"""

    def __init__(self, retriever: Optional[Any] = None) -> None:
        self._retriever = retriever

    @property
    def retriever(self) -> Any:
        if self._retriever is None:
            try:
                from odap.biz.data.qa.semantic_retriever import SemanticObjectRetriever
                self._retriever = SemanticObjectRetriever()
            except Exception as e:
                logger.warning("Failed to lazy-load SemanticObjectRetriever: %s", e)
                raise
        return self._retriever

    def search(
        self,
        query: str,
        workspace_id: Optional[str] = None,
        ontology_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        try:
            result = self._run_retrieve(query, limit)
            return [self._row_from(obj, workspace_id, ontology_id) for obj in (result.objects or [])]
        except Exception as e:
            logger.warning("UnstructuredSource.search failed: %s", e)
            return [self._error_row(query, workspace_id, ontology_id, str(e))]

    def _run_retrieve(self, query: str, limit: int):
        import asyncio
        coro = self.retriever.retrieve(query, top_k=limit)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            return self._run_in_thread(coro)
        return asyncio.run(coro)

    def _run_in_thread(self, coro):
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_run_async, coro).result(timeout=30)

    def _row_from(self, obj, workspace_id, ontology_id) -> Dict[str, Any]:
        return {
            "id": getattr(obj, "object_id", obj.id) if hasattr(obj, "id") else str(obj),
            "object_id": getattr(obj, "object_id", None),
            "object_type": getattr(obj, "object_type", None),
            "score": getattr(obj, "score", None),
            "content": getattr(obj, "description", ""),
            "links": getattr(obj, "links", []),
            "workspace_id": workspace_id,
            "ontology_id": ontology_id,
        }

    def _error_row(self, query, workspace_id, ontology_id, err: str) -> Dict[str, Any]:
        return {
            "error": err,
            "query": query,
            "workspace_id": workspace_id,
            "ontology_id": ontology_id,
        }


def _run_async(coro):
    import asyncio
    return asyncio.run(coro)


__all__ = ["UnstructuredSourceImpl"]
