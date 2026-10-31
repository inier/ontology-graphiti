"""Ingest 端口层导出。"""

from __future__ import annotations

from .ingestor import (
    DOCUMENT_DRIVEN,
    EVENT_DRIVEN,
    ExtractionMode,
    IngestRequest,
    IngestorPort,
    NormalizedDoc,
    RawPayload,
    SourceCategory,
    build_normalized_doc,
    canonical_text,
    hash_text,
)

__all__ = [
    "DOCUMENT_DRIVEN",
    "EVENT_DRIVEN",
    "ExtractionMode",
    "IngestRequest",
    "IngestorPort",
    "NormalizedDoc",
    "RawPayload",
    "SourceCategory",
    "build_normalized_doc",
    "canonical_text",
    "hash_text",
]
