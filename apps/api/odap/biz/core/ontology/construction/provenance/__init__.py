"""L2 Construction — Provenance Subsystem.

4级溯源链:
  原始文档 → 提取记录 → 构建操作 → 图谱实体
"""

from .provenance_linker import ProvenanceChain, ProvenanceLinker, get_provenance_linker
from .provenance_query import ProvenanceQuery, get_provenance_query
from .provenance_schema import (
    SCHEMA_VERSION,
    PROVENANCE_FIELDS,
    FIELD_SCHEMA_VERSION,
    FIELD_SOURCE_DOC_IDS,
    FIELD_CHUNK_ID,
    FIELD_CHAR_SPAN,
    FIELD_CONFIDENCE,
    FIELD_EVIDENCE_TEXT,
    build_provenance_props,
    merge_provenance,
)

__all__ = [
    "ProvenanceChain",
    "ProvenanceLinker",
    "get_provenance_linker",
    "ProvenanceQuery",
    "get_provenance_query",
    # 冻结的 span 级溯源 schema（prov-span-v1）
    "SCHEMA_VERSION",
    "PROVENANCE_FIELDS",
    "FIELD_SCHEMA_VERSION",
    "FIELD_SOURCE_DOC_IDS",
    "FIELD_CHUNK_ID",
    "FIELD_CHAR_SPAN",
    "FIELD_CONFIDENCE",
    "FIELD_EVIDENCE_TEXT",
    "build_provenance_props",
    "merge_provenance",
]
