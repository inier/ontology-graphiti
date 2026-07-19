"""L2 Construction — Provenance Subsystem.

4级溯源链:
  原始文档 → 提取记录 → 构建操作 → 图谱实体
"""

from .provenance_linker import ProvenanceChain, ProvenanceLinker, get_provenance_linker
from .provenance_query import ProvenanceQuery, get_provenance_query

__all__ = [
    "ProvenanceChain",
    "ProvenanceLinker",
    "get_provenance_linker",
    "ProvenanceQuery",
    "get_provenance_query",
]
