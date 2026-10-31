"""Ingestor 端口契约（P0-2）。

问题背景：改造前 ``UnifiedIngestFacade.ingest`` 用两个硬编码 frozenset + 一串
``if source_type == ...`` 分派，新增数据源必须同时改三处（分类常量、路由分支、
文档分支），且没有任何统一的摄入元数据（来源 URI / 内容指纹 / 增量游标），
导致：

* 支持列表与实际路由会漂移（``get_supported_source_types`` 说有，实际走不到）；
* 重复摄入无法识别（同一份文档反复入图）；
* 未知来源只能靠 ``else`` 兜底，错误信息不带可用取值。

本模块把「数据源」抽象成端口：

    fetch(request) -> RawPayload        搬运原始负载（谁掌握传输谁实现）
    normalize(raw) -> NormalizedDoc     统一成可哈希、可去重的规范化文档
    ingest(request) -> Dict             端到端摄入（由上两层组合而成）

``source_uri`` / ``content_hash`` / ``watermark`` 是每个 ``NormalizedDoc`` 的
必带元数据：前者定位来源，中者用于去重与幂等，后者标识本次抓取的水位。

注意：本端口不负责「兜底」。fetch/normalize 失败必须抛异常，由调用方显式
决策（AGENTS.md 规则 14）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, FrozenSet, Mapping, Optional, Protocol, runtime_checkable

# 源分类：既是路由常量，也是注册表的分组键
DOCUMENT_DRIVEN = "document_driven"
EVENT_DRIVEN = "event_driven"


class SourceCategory:
    """数据源分类常量（保持历史导入路径兼容）。

    ``DOCUMENT_DRIVEN`` / ``EVENT_DRIVEN`` 仍是 frozenset，供既有调用方做
    归属判断；路由本身由 ``IngestorRegistry`` 的注册结果决定，不再依赖这两个
    集合做 if/elif 分支。
    """

    DOCUMENT_DRIVEN_SOURCES: ClassVar[FrozenSet[str]] = frozenset({
        "url", "news", "tavily", "manual", "json",
        "natural_language", "random_events", "database",
        "kb_upload", "ontology_document",
    })
    EVENT_DRIVEN_SOURCES: ClassVar[FrozenSet[str]] = frozenset({
        "webhook", "sensor", "mcp", "file", "api",
    })

    # 兼容旧引用名（routes/tests 直接读这两个属性）
    DOCUMENT_DRIVEN = DOCUMENT_DRIVEN_SOURCES
    EVENT_DRIVEN = EVENT_DRIVEN_SOURCES


class ExtractionMode:
    """抽取模式常量"""

    CONSTRAINED = "constrained"    # 约束性：entity_type 必须已定义
    EXPLORATORY = "exploratory"    # 探索性：允许推断新类型结构


def utc_now_iso() -> str:
    """当前 UTC 时间（ISO 8601，秒级）"""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def hash_text(text: str) -> str:
    """内容指纹：utf-8 编码后的 sha256 十六进制摘要。

    固定用 UTF-8 而非平台默认编码，保证同一文本在 Windows/容器内指纹一致，
    否则去重键会随运行环境漂移。
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_text(content: Any) -> str:
    """把任意负载规范化为参与哈希的文本。

    规则：
    - ``str`` 原样返回（不做 strip —— 首尾空白属于内容，裁剪会让 1 处变更不可见）
    - ``bytes`` 严格按 UTF-8 解码，失败即抛 ``UnicodeDecodeError``（不静默替换字符）
    - ``dict`` / ``list`` 用 sort_keys + 紧凑分隔符序列化，保证键序无关的稳定指纹
    - ``None`` → 空串
    - 其它类型走 ``str()``
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (bytes, bytearray)):
        return bytes(content).decode("utf-8")
    if isinstance(content, (dict, list, tuple)):
        return json.dumps(
            content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str,
        )
    return str(content)


@dataclass(frozen=True)
class IngestRequest:
    """一次摄入请求。``kwargs`` 即门面收到的具名参数，保持原样透传给 handler。"""

    source_type: str
    kwargs: Mapping[str, Any] = field(default_factory=dict)

    @property
    def ontology_id(self) -> Optional[str]:
        return self.kwargs.get("ontology_id")

    @property
    def workspace_id(self) -> Optional[str]:
        return self.kwargs.get("workspace_id")

    @property
    def scenario_id(self) -> Optional[str]:
        return self.kwargs.get("scenario_id")

    @property
    def extraction_mode(self) -> str:
        return self.kwargs.get("extraction_mode", ExtractionMode.CONSTRAINED)


@dataclass(frozen=True)
class RawPayload:
    """fetch 阶段的产物：尚未规范化、尚未哈希的原始负载。

    ``source_uri`` 为空的含义是「请求没有提供任何可定位的来源标识」，不是
    「猜一个」——调用方可据此判定该次摄入不可追溯。
    """

    source_type: str
    source_uri: str
    content: Any
    mime: str = ""
    watermark: Optional[str] = None
    fetched_at: str = ""
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedDoc:
    """normalize 阶段的产物：可哈希、可去重、可审计的规范化文档。"""

    source_type: str
    source_uri: str
    text: str
    content_hash: str
    byte_len: int
    mime: str = ""
    watermark: Optional[str] = None
    workspace_id: Optional[str] = None
    fetched_at: str = ""

    def as_metadata(self) -> Dict[str, Any]:
        """导出可并入摄入响应的元数据（不含正文，避免响应体膨胀）。"""
        return {
            "source_uri": self.source_uri,
            "content_hash": self.content_hash,
            "watermark": self.watermark,
            "bytes_len": self.byte_len,
            "mime": self.mime,
        }


def build_normalized_doc(
    raw: RawPayload,
    *,
    workspace_id: Optional[str] = None,
    mime: Optional[str] = None,
) -> NormalizedDoc:
    """由 RawPayload 构造 NormalizedDoc。"""
    text = canonical_text(raw.content)
    return NormalizedDoc(
        source_type=raw.source_type,
        source_uri=raw.source_uri,
        text=text,
        content_hash=hash_text(text),
        byte_len=len(text.encode("utf-8")),
        mime=mime if mime is not None else raw.mime,
        watermark=raw.watermark or raw.fetched_at or None,
        workspace_id=workspace_id,
        fetched_at=raw.fetched_at,
    )


@runtime_checkable
class IngestorPort(Protocol):
    """数据源端口。新增来源 = 实现本协议 + 注册，不改门面。"""

    source_types: FrozenSet[str]
    category: ClassVar[str]

    async def fetch(self, request: IngestRequest) -> RawPayload:
        """搬运原始负载。传输失败必须抛异常。"""
        ...

    def normalize(self, raw: RawPayload, request: IngestRequest) -> NormalizedDoc:
        """规范化并计算内容指纹。无法规范化必须抛异常。"""
        ...

    async def ingest(self, request: IngestRequest) -> Dict[str, Any]:
        """端到端摄入，返回 ``{"status": "ok"|"error", ...}``。"""
        ...
