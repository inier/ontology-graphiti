"""ProvenanceLinker — 4级溯源链编织器。

编织完整溯源链: 原始文档 → 提取记录 → 构建操作 → 图谱实体 → 审计日志。

采用 Frozen Dataclass 设计，遵循 ADR-068 契约模式。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProvenanceChain:
    """4级溯源链 — 从图谱实体回溯到原始文档。

    链路: Graphiti Entity → Build Record → Extraction Record → Source Document
    """
    # Level 3: 图谱实体
    graph_entity_id: str = ""
    graph_entity_type: str = ""
    graph_entity_name: str = ""

    # Level 2: 构建操作
    build_pipeline_run_id: Optional[str] = None
    build_step: Optional[str] = None       # normalization / relation_validation / consistency / review / graph_write / snapshot
    build_timestamp: Optional[str] = None
    build_operator: Optional[str] = None   # 构建操作者
    build_batch_id: Optional[str] = None

    # Level 1: 提取记录
    extraction_session_id: Optional[str] = None
    extraction_method: Optional[str] = None   # HE / LLM / Regex / Manual
    extraction_confidence: Optional[float] = None  # 0-1
    extraction_template: Optional[str] = None

    # Level 0: 原始文档/数据源
    source_document_id: Optional[str] = None
    source_document_name: Optional[str] = None
    source_document_type: Optional[str] = None   # pdf / docx / web / json / manual
    source_text_snippet: Optional[str] = None    # 原始文本片段 (前200字符)
    source_url: Optional[str] = None

    # 本体关联
    ontology_id: Optional[str] = None
    ontology_property_id: Optional[str] = None
    metric_definition_id: Optional[str] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转为字典（便于JSON序列化）"""
        return {
            "graph_entity_id": self.graph_entity_id,
            "graph_entity_type": self.graph_entity_type,
            "graph_entity_name": self.graph_entity_name,
            "build": {
                "pipeline_run_id": self.build_pipeline_run_id,
                "step": self.build_step,
                "timestamp": self.build_timestamp,
                "operator": self.build_operator,
                "batch_id": self.build_batch_id,
            },
            "extraction": {
                "session_id": self.extraction_session_id,
                "method": self.extraction_method,
                "confidence": self.extraction_confidence,
                "template": self.extraction_template,
            },
            "source": {
                "document_id": self.source_document_id,
                "document_name": self.source_document_name,
                "document_type": self.source_document_type,
                "text_snippet": self.source_text_snippet,
                "url": self.source_url,
            },
            "ontology": {
                "ontology_id": self.ontology_id,
                "property_id": self.ontology_property_id,
                "metric_id": self.metric_definition_id,
            },
            "metadata": self.metadata,
        }

    def is_complete(self) -> bool:
        """检查溯源链是否完整（至少包含实体→来源）"""
        return bool(self.graph_entity_id and self.source_document_id)


class ProvenanceLinker:
    """溯源链编织器 — 单例。

    从分散的存储中组装完整的4级溯源链。
    """

    _instance: Optional["ProvenanceLinker"] = None

    def __new__(cls) -> "ProvenanceLinker":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

    def link_chain(self, graph_entity_id: str) -> ProvenanceChain:
        """从图谱实体ID回溯完整溯源链。

        查链过程:
        1. 查 extraction_provenance 表 → 提取记录
        2. 查 construction_provenance 表 → 构建记录
        3. 查 kb_documents 表 → 原始文档
        """
        chain = ProvenanceChain(graph_entity_id=graph_entity_id)

        # Level 2: 构建溯源
        build_info = self._get_build_provenance(graph_entity_id)
        if build_info:
            chain = ProvenanceChain(
                graph_entity_id=graph_entity_id,
                graph_entity_type=build_info.get("entity_type", ""),
                graph_entity_name=build_info.get("entity_name", ""),
                build_pipeline_run_id=build_info.get("pipeline_run_id"),
                build_step=build_info.get("step"),
                build_timestamp=build_info.get("timestamp"),
                build_operator=build_info.get("operator"),
                build_batch_id=build_info.get("batch_id"),
            )

        # Level 1: 提取溯源
        extract_info = self._get_extraction_provenance(graph_entity_id)
        if extract_info:
            chain = ProvenanceChain(
                graph_entity_id=chain.graph_entity_id,
                graph_entity_type=chain.graph_entity_type,
                graph_entity_name=chain.graph_entity_name,
                build_pipeline_run_id=chain.build_pipeline_run_id,
                build_step=chain.build_step,
                build_timestamp=chain.build_timestamp,
                build_operator=chain.build_operator,
                build_batch_id=chain.build_batch_id,
                extraction_session_id=extract_info.get("session_id"),
                extraction_method=extract_info.get("method"),
                extraction_confidence=extract_info.get("confidence"),
                extraction_template=extract_info.get("template"),
            )

        # Level 0: 原始文档
        doc_info = self._get_source_document(extract_info)
        if doc_info:
            chain = ProvenanceChain(
                graph_entity_id=chain.graph_entity_id,
                graph_entity_type=chain.graph_entity_type,
                graph_entity_name=chain.graph_entity_name,
                build_pipeline_run_id=chain.build_pipeline_run_id,
                build_step=chain.build_step,
                build_timestamp=chain.build_timestamp,
                build_operator=chain.build_operator,
                build_batch_id=chain.build_batch_id,
                extraction_session_id=chain.extraction_session_id,
                extraction_method=chain.extraction_method,
                extraction_confidence=chain.extraction_confidence,
                extraction_template=chain.extraction_template,
                source_document_id=doc_info.get("id"),
                source_document_name=doc_info.get("name"),
                source_document_type=doc_info.get("type"),
                source_text_snippet=doc_info.get("snippet"),
                source_url=doc_info.get("url"),
            )

        return chain

    def link_batch(self, graph_entity_ids: List[str]) -> List[ProvenanceChain]:
        """批量编织溯源链"""
        return [self.link_chain(eid) for eid in graph_entity_ids]

    # ── 内部方法 ──

    def _get_build_provenance(self, entity_id: str) -> Optional[dict]:
        """从 extraction_provenance 表查询构建溯源

        D5 修复：ProvenanceTracker 无 get_by_entity_id 方法，真实方法是
        get_provenance(entity_id) -> Optional[Dict]（单条记录）。原代码调用不存在
        方法触发 AttributeError 被 except 静默吞成 debug → 4级溯源链永远返回空壳。
        """
        try:
            from odap.biz.data.hyper_extract.impl.provenance_tracker import ProvenanceTracker
            tracker = ProvenanceTracker()
            r = tracker.get_provenance(entity_id)
            if r:
                return {
                    "entity_type": r.get("entity_type", ""),
                    "entity_name": r.get("entity_name", ""),
                    "pipeline_run_id": r.get("pipeline_run_id"),
                    "step": r.get("step"),
                    "timestamp": r.get("timestamp"),
                    "operator": r.get("operator"),
                    "batch_id": r.get("batch_id"),
                }
        except Exception as e:
            logger.warning(
                "ProvenanceLinker: build provenance lookup failed for entity_id=%s: %s",
                entity_id, e,
            )
        return None

    def _get_extraction_provenance(self, entity_id: str) -> Optional[dict]:
        """从 extraction_provenance 表查询提取溯源

        D5 修复：同 _get_build_provenance，改用 get_provenance(entity_id) 单条查询。
        """
        try:
            from odap.biz.data.hyper_extract.impl.provenance_tracker import ProvenanceTracker
            tracker = ProvenanceTracker()
            r = tracker.get_provenance(entity_id)
            if r and r.get("source_doc_id"):
                return {
                    "session_id": r.get("session_id"),
                    "method": r.get("extraction_method", "unknown"),
                    "confidence": r.get("confidence_score"),
                    "template": r.get("source_template"),
                    "source_doc_id": r.get("source_doc_id"),
                }
        except Exception as e:
            logger.warning(
                "ProvenanceLinker: extraction provenance lookup failed for entity_id=%s: %s",
                entity_id, e,
            )
        return None

    def _get_source_document(self, extract_info: Optional[dict]) -> Optional[dict]:
        """从知识库查询原始文档（Level 0）。

        D5 修复：原 `from odap.infra.storage.sqlite_client import get_sqlite_client`
        是幻影——该模块/函数在整个 odap 中都不存在，import 恒抛 ModuleNotFoundError
        被 except 吞掉 → 4级溯源链的 Level 0 永远无法解析；且旧字段名（id/name/source_url）
        与真实 kb_documents 表（doc_id/title/file_url）不符。改用真实存储
        SQLiteKnowledgeBaseStorage.find_document_by_id(doc_id)（仅需 doc_id）。
        """
        if not extract_info or not extract_info.get("source_doc_id"):
            return None
        doc_id = extract_info["source_doc_id"]
        try:
            from odap.biz.data.knowledge_base.storage.sqlite_kb_storage import (
                SQLiteKnowledgeBaseStorage,
            )
            store = SQLiteKnowledgeBaseStorage()
            doc = store.find_document_by_id(doc_id)
            if doc:
                content = (
                    doc.get("content")
                    or doc.get("raw_content")
                    or doc.get("cleaned_content")
                    or ""
                )
                return {
                    "id": doc.get("doc_id", ""),
                    "name": doc.get("title", ""),
                    "type": doc.get("file_type") or doc.get("content_type", ""),
                    "snippet": content[:200] if content else "",
                    "url": doc.get("file_url", ""),
                }
        except Exception as e:
            logger.warning(
                "ProvenanceLinker: source document lookup failed for doc_id=%s: %s",
                doc_id, e,
            )
        return None


class ProvenanceQuery:
    """溯源查询器 — 支持按文档ID和构建批次查询。

    替代原本的 Stub 实现，提供完整的溯源链查询功能。
    依赖 ProvenanceTracker 的反向查询能力和 ProvenanceLinker 的链编织能力。
    """

    def __init__(self, linker: Optional[ProvenanceLinker] = None):
        self._linker = linker or ProvenanceLinker()

    def trace_by_document(self, document_id: str) -> dict:
        """按文档ID查询所有关联实体。

        从 extraction_provenance 表反向查询所有与该文档相关的实体，
        然后为每个实体编织完整的4级溯源链。

        Args:
            document_id: 来源文档ID

        Returns:
            dict: {
                "document_id": str,
                "entities": [{"entity_id", "chain", "is_complete"}],
                "total": int,
            }
        """
        entities: List[Dict[str, Any]] = []
        try:
            from odap.biz.data.hyper_extract.impl.provenance_tracker import ProvenanceTracker
            tracker = ProvenanceTracker()
            records = tracker.get_by_document_id(document_id)
            if records:
                for r in records:
                    eid = r.get("entity_id", "")
                    if eid:
                        chain = self._linker.link_chain(eid)
                        entities.append({
                            "entity_id": eid,
                            "chain": chain.to_dict(),
                            "is_complete": chain.is_complete(),
                        })
        except Exception as e:
            logger.warning("trace_by_document failed: %s", e)

        return {
            "document_id": document_id,
            "entities": entities,
            "total": len(entities),
        }

    def trace_by_build(self, pipeline_run_id: str) -> dict:
        """按构建批次查询所有实体。

        从 extraction_provenance 表按 pipeline_run_id 反向查询，
        然后为每个实体编织完整的溯源链。

        Args:
            pipeline_run_id: 构建流水线运行ID

        Returns:
            dict: {
                "pipeline_run_id": str,
                "entities": [{"entity_id", "chain", "is_complete"}],
                "total": int,
            }
        """
        entities: List[Dict[str, Any]] = []
        try:
            from odap.biz.data.hyper_extract.impl.provenance_tracker import ProvenanceTracker
            tracker = ProvenanceTracker()
            records = tracker.get_by_pipeline_run(pipeline_run_id)
            if records:
                for r in records:
                    eid = r.get("entity_id", "")
                    if eid:
                        chain = self._linker.link_chain(eid)
                        entities.append({
                            "entity_id": eid,
                            "chain": chain.to_dict(),
                            "is_complete": chain.is_complete(),
                        })
        except Exception as e:
            logger.warning("trace_by_build failed: %s", e)

        return {
            "pipeline_run_id": pipeline_run_id,
            "entities": entities,
            "total": len(entities),
        }


def get_provenance_linker() -> ProvenanceLinker:
    """获取溯源链编织器单例"""
    return ProvenanceLinker()


__all__ = ["ProvenanceChain", "ProvenanceLinker", "ProvenanceQuery", "get_provenance_linker"]
