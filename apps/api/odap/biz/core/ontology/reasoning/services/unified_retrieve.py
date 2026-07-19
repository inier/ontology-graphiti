"""UnifiedRetrieveEngine — 统一检索引擎。

全平台唯一的数据检索入口，支持:
- 跨源联邦查询 (schema + entity + document)
- NL→DSL→结构化查询
- 结果溯源 (4级ProvenanceChain)
- 指标关联填充

遵循 ADR-068 的四层契约模式。
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RetrieveRequest:
    """统一检索请求"""
    query: str
    workspace_id: str = "default"
    ontology_ids: List[str] = field(default_factory=list)
    source_types: List[str] = field(default_factory=lambda: ["schema", "entity", "document"])
    retrieval_mode: str = "hybrid"
    top_k: int = 20
    include_provenance: bool = True
    include_metrics: bool = False
    include_semantics: bool = False
    ontology_id: Optional[str] = None  # 单一本体ID（兼容旧API）


@dataclass
class RetrieveResult:
    """统一检索结果"""
    items: List[Dict[str, Any]] = field(default_factory=list)
    total: int = 0
    query_intent: str = ""
    execution_time_ms: float = 0.0
    sources_queried: List[str] = field(default_factory=list)
    provenance_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": "success",
            "items": self.items,
            "total": self.total,
            "query_intent": self.query_intent,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "sources_queried": self.sources_queried,
            "provenance_summary": self.provenance_summary,
        }


class UnifiedRetrieveEngine:
    """统一检索引擎 — 单例。

    封装 QueryService + NLDispatcher + KnowledgeBase RAG + GraphManager，
    提供全平台唯一的数据检索入口。
    """

    _instance: Optional["UnifiedRetrieveEngine"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

    async def retrieve(self, request: RetrieveRequest) -> RetrieveResult:
        """主入口：统一检索"""
        start = time.perf_counter()
        result = RetrieveResult()

        try:
            # 1. 意图分类
            intent = self._classify_intent(request.query)
            result.query_intent = intent

            # 2. 多源并行检索
            tasks = []
            source_types = request.source_types
            if not request.ontology_ids and request.ontology_id:
                request.ontology_ids = [request.ontology_id]

            if "schema" in source_types:
                tasks.append(self._retrieve_schema(request))
            if "entity" in source_types:
                tasks.append(self._retrieve_entity(request))
            if "document" in source_types:
                tasks.append(self._retrieve_document(request))

            if not tasks:
                tasks.append(self._retrieve_entity(request))

            all_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 3. 合并结果
            merged = []
            for r in all_results:
                if isinstance(r, Exception):
                    logger.warning("Retrieval sub-task failed: %s", r)
                    continue
                if isinstance(r, list):
                    merged.extend(r)

            # 4. 去重 + 排序
            merged = self._deduplicate(merged)
            merged = self._rank(merged, request.query)

            # 5. 填充溯源信息
            if request.include_provenance:
                merged = await self._enrich_provenance(merged)

            result.items = merged[:request.top_k]
            result.total = len(merged)
            result.sources_queried = source_types

        except Exception as e:
            logger.error("UnifiedRetrieveEngine failed: %s", e)
            result.items = [{"type": "error", "message": str(e)}]

        result.execution_time_ms = (time.perf_counter() - start) * 1000
        return result

    # ── 各源检索 ──

    async def _retrieve_schema(self, request: RetrieveRequest) -> List[Dict]:
        """检索本体类型定义"""
        try:
            from odap.infra.query import get_query_service, QuerySource
            qs = get_query_service()
            ontology_filter = ""
            if request.ontology_ids:
                ontology_filter = f", ontology_id='{request.ontology_ids[0]}'"
            dsl = f".schema with(kind='object_types'{ontology_filter})"
            result = await qs.execute_async(request.workspace_id, dsl, request.top_k)
            items = []
            for row in result.rows:
                item = {
                    "id": row.get("id", row.get("type_id", "")),
                    "name": row.get("name", row.get("display_name", "")),
                    "type": "entity_type",
                    "score": 1.0,
                    "source_type": "schema",
                    "raw_data": row,
                }
                # 关联Property
                props = row.get("properties", [])
                if props:
                    item["property_ids"] = [p.get("id", "") for p in props]
                items.append(item)
            return items
        except Exception as e:
            logger.warning("Schema retrieval failed: %s", e)
            return []

    async def _retrieve_entity(self, request: RetrieveRequest) -> List[Dict]:
        """检索实体实例"""
        try:
            from odap.infra.query import get_query_service
            qs = get_query_service()
            ontology_filter = ""
            if request.ontology_ids:
                ontology_filter = f", type='{request.ontology_ids[0]}'"
            dsl = f".entity with(search='{request.query}'{ontology_filter})"
            result = await qs.execute_async(request.workspace_id, dsl, request.top_k)
            items = []
            for row in result.rows:
                items.append({
                    "id": row.get("id", row.get("entity_id", "")),
                    "name": row.get("name", row.get("entity_name", "")),
                    "type": "entity",
                    "score": row.get("score", 0.8),
                    "source_type": "entity",
                    "raw_data": row,
                })
            return items
        except Exception as e:
            logger.warning("Entity retrieval failed: %s", e)
            return []

    async def _retrieve_document(self, request: RetrieveRequest) -> List[Dict]:
        """检索非结构化文档"""
        try:
            from odap.infra.query import get_query_service
            qs = get_query_service()
            ontology_filter = ""
            if request.ontology_ids:
                ontology_filter = f", ontology_id='{request.ontology_ids[0]}'"
            dsl = f".unstructured with(query='{request.query}'{ontology_filter})"
            result = await qs.execute_async(request.workspace_id, dsl, request.top_k)
            items = []
            for row in result.rows:
                items.append({
                    "id": row.get("id", row.get("document_id", "")),
                    "name": row.get("name", row.get("title", "")),
                    "type": "document",
                    "score": row.get("score", 0.7),
                    "source_type": "document",
                    "raw_data": row,
                    "snippet": row.get("text", row.get("content", ""))[:200],
                })
            return items
        except Exception as e:
            logger.warning("Document retrieval failed: %s", e)
            return []

    # ── 辅助方法 ──

    def _classify_intent(self, query: str) -> str:
        """简单意图分类"""
        q = query.lower()
        if any(kw in q for kw in ("定义", "类型", "schema", "有哪些属性")):
            return "structured"
        if any(kw in q for kw in ("文档", "报告", "内容")):
            return "document"
        if any(kw in q for kw in ("关系", "邻居", "路径", "关联")):
            return "graph"
        return "hybrid"

    def _deduplicate(self, items: List[Dict]) -> List[Dict]:
        seen = set()
        result = []
        for item in items:
            key = f"{item.get('type','')}:{item.get('id','')}"
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def _rank(self, items: List[Dict], query: str) -> List[Dict]:
        """按score降序排列"""
        return sorted(items, key=lambda x: x.get("score", 0), reverse=True)

    async def _enrich_provenance(self, items: List[Dict]) -> List[Dict]:
        """为每个item填充溯源信息"""
        try:
            from odap.biz.core.ontology.construction.provenance.provenance_linker import get_provenance_linker
            linker = get_provenance_linker()
            for item in items:
                if item.get("type") == "entity" and item.get("id"):
                    try:
                        chain = linker.link_chain(item["id"])
                        item["provenance"] = chain.to_dict()
                    except Exception:
                        item["provenance"] = None
                else:
                    item["provenance"] = None
        except Exception as e:
            logger.debug("Provenance enrichment failed: %s", e)
        return items


def get_retrieve_engine() -> UnifiedRetrieveEngine:
    return UnifiedRetrieveEngine()


__all__ = ["RetrieveRequest", "RetrieveResult", "UnifiedRetrieveEngine", "get_retrieve_engine"]
