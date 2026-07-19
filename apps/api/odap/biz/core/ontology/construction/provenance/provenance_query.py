"""ProvenanceQuery — 溯源查询接口。

提供面向用户的溯源查询能力:
- 按实体ID查询溯源链
- 按文档ID查询所有关联实体
- 按构建批次查询所有实体
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .provenance_linker import ProvenanceChain, get_provenance_linker

logger = logging.getLogger(__name__)


class ProvenanceQuery:
    """溯源查询服务 — 单例"""

    _instance: Optional["ProvenanceQuery"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._linker = get_provenance_linker()
        self._initialized = True

    def trace_entity(self, graph_entity_id: str) -> dict:
        """查询单个实体的完整溯源链"""
        chain = self._linker.link_chain(graph_entity_id)
        return {
            "entity_id": graph_entity_id,
            "chain": chain.to_dict(),
            "is_complete": chain.is_complete(),
        }

    def trace_batch(self, graph_entity_ids: List[str]) -> List[dict]:
        """批量查询溯源链"""
        chains = self._linker.link_batch(graph_entity_ids)
        return [
            {
                "entity_id": c.graph_entity_id,
                "chain": c.to_dict(),
                "is_complete": c.is_complete(),
            }
            for c in chains
        ]

    def trace_by_document(self, document_id: str) -> dict:
        """按文档ID查询所有关联实体（预留，需DB支持）"""
        return {
            "document_id": document_id,
            "entities": [],  # TODO: 实现反向查询
            "note": "反向查询待实现 — 需要 SQLite 支持 document_id → entity_ids 的索引",
        }

    def trace_by_build(self, pipeline_run_id: str) -> dict:
        """按构建批次查询所有实体（预留）"""
        return {
            "pipeline_run_id": pipeline_run_id,
            "entities": [],
            "note": "批次查询待实现",
        }


def get_provenance_query() -> ProvenanceQuery:
    """获取溯源查询服务单例"""
    return ProvenanceQuery()


__all__ = ["ProvenanceQuery", "get_provenance_query"]
