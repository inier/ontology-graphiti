"""Ingestor 注册表与门面适配器（P0-2）。

``IngestorRegistry`` 是 source_type → 端口的唯一真值来源：
``get_supported_source_types()`` 直接由注册结果生成，因此「列表里有」
和「路由能走到」永远一致。

``FacadeIngestor`` 把既有的 ``_ingest_document`` / ``_ingest_event`` 包装成
符合 ``IngestorPort`` 的两段式实现。当前传输（HTTP 抓取、Tavily 搜索、Neo4j
写入）仍由下游 handler 负责，因此 fetch 阶段只做「请求侧元数据归集」，
normalize 阶段负责规范化与内容指纹 —— 契约先立住接缝，后续新增源可直接
实现真实的两段式，无需再改门面。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional

from .ports.ingestor import (
    DOCUMENT_DRIVEN,
    EVENT_DRIVEN,
    IngestRequest,
    IngestorPort,
    NormalizedDoc,
    RawPayload,
    build_normalized_doc,
    utc_now_iso,
)

logger = logging.getLogger(__name__)

AsyncHandler = Callable[..., Any]

CATEGORY_LABELS = (DOCUMENT_DRIVEN, EVENT_DRIVEN)

# 请求里可能承载「来源定位」的字段，按可信度排序取第一个非空值
_URI_FIELDS = ("source_uri", "url", "uri", "file_path", "path")

# 无显式 URI 时，用「来源类型:自然键」构造可追溯标识
_SCOPED_KEY_FIELDS = {
    "news": "query",
    "tavily": "query",
    "sensor": "sensor_id",
    "kb_upload": "doc_id",
    "ontology_document": "ontology_id",
    "database": "connection_id",
    "webhook": "event_id",
    "mcp": "tool_name",
    "file": "filename",
    "api": "endpoint",
}

# 可能承载正文的字段，按优先级取第一个非 None
_CONTENT_FIELDS = (
    "content", "text", "raw_json", "form_data",
    "payload", "structured_data", "value",
)


def build_source_uri(source_type: str, kwargs: Mapping[str, Any]) -> str:
    """从请求参数构造来源 URI。

    优先使用调用方显式给出的 ``source_uri`` / ``url`` / ``uri`` / ``file_path``；
    其次用「来源类型:自然键」（如 ``news:红海航运``）；都没有则返回空串——
    空串表示该次摄入不可定位，不猜测、不补造。
    """
    for field in _URI_FIELDS:
        value = kwargs.get(field)
        if value:
            return str(value)

    key_field = _SCOPED_KEY_FIELDS.get(source_type)
    if key_field:
        value = kwargs.get(key_field)
        if value:
            return f"{source_type}:{value}"
    return ""


def _extract_content(kwargs: Mapping[str, Any]) -> Any:
    """按优先级取出本次请求的原始负载。"""
    for field in _CONTENT_FIELDS:
        value = kwargs.get(field)
        if value is not None:
            return value
    return ""


class FacadeIngestor:
    """把门面既有 handler 适配为 ``IngestorPort``。"""

    def __init__(
        self,
        *,
        category: str,
        source_types: FrozenSet[str],
        handler: AsyncHandler,
    ) -> None:
        if category not in CATEGORY_LABELS:
            raise ValueError(f"unknown ingest category: {category}")
        if not source_types:
            raise ValueError("source_types must not be empty")
        self.category = category
        self.source_types = frozenset(source_types)
        self._handler = handler

    async def fetch(self, request: IngestRequest) -> RawPayload:
        return RawPayload(
            source_type=request.source_type,
            source_uri=build_source_uri(request.source_type, request.kwargs),
            content=_extract_content(request.kwargs),
            mime=str(request.kwargs.get("mime") or ""),
            watermark=request.kwargs.get("watermark"),
            fetched_at=utc_now_iso(),
            headers=request.kwargs.get("headers") or {},
        )

    def normalize(self, raw: RawPayload, request: IngestRequest) -> NormalizedDoc:
        return build_normalized_doc(
            raw,
            workspace_id=request.workspace_id,
            mime=str(request.kwargs.get("mime") or "") or None,
        )

    async def ingest(self, request: IngestRequest) -> Dict[str, Any]:
        raw = await self.fetch(request)
        doc = self.normalize(raw, request)

        result = await self._handler(request.source_type, **dict(request.kwargs))
        if not isinstance(result, dict):
            raise TypeError(
                f"ingest handler returned {type(result).__name__}, expected dict "
                f"(source_type={request.source_type})"
            )

        # 元数据对成功与失败都附上：失败时同样需要定位「哪一份输入坏了」
        for key, value in doc.as_metadata().items():
            result.setdefault(key, value)
        return result


class IngestorRegistry:
    """source_type → IngestorPort 的注册表。"""

    def __init__(self) -> None:
        self._by_source_type: Dict[str, IngestorPort] = {}

    def register(self, port: IngestorPort) -> None:
        """注册端口。source_type 冲突视为编程错误，直接拒绝。"""
        for source_type in port.source_types:
            existing = self._by_source_type.get(source_type)
            if existing is not None:
                raise ValueError(
                    f"duplicate ingest source_type '{source_type}': "
                    f"already registered by {type(existing).__name__}"
                )
        for source_type in port.source_types:
            self._by_source_type[source_type] = port

    def resolve(self, source_type: str) -> Optional[IngestorPort]:
        return self._by_source_type.get(source_type)

    def supported(self) -> Dict[str, List[str]]:
        grouped: Dict[str, List[str]] = {label: [] for label in CATEGORY_LABELS}
        for source_type, port in self._by_source_type.items():
            grouped[port.category].append(source_type)
        return {label: sorted(types) for label, types in grouped.items()}

    def all_source_types(self) -> List[str]:
        return sorted(self._by_source_type)
