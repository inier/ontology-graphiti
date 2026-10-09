"""概念缺口模型 —— 聚合运行时未答信号（BeModel 概念缺口回路参照）。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class GapStatus(str, Enum):
    OPEN = "open"
    PROMOTED = "promoted"
    ADOPTED = "adopted"
    REJECTED = "rejected"

    def __str__(self) -> str:
        return self.value


class GapSignalSource(str, Enum):
    TERM_RESOLVE_MISS = "term_resolve_miss"
    MAPPING_FAILURE = "mapping_failure"
    QA_UNANSWERED = "qa_unanswered"
    NL_QUERY_UNANSWERED = "nl_query_unanswered"

    def __str__(self) -> str:
        return self.value


class GapLayer(str, Enum):
    """缺口归因三层（ADR-088，对齐 EvoOntology schema/content/tool 三层）。

    归因是最佳努力：信号点上下文不足以判定 layer 时省略（None），绝不造数（规则 14）。
    """

    SCHEMA = "schema"    # TBox 结构：object_type / property / relation / event / action
    CONTENT = "content"  # USL 术语 / canonical / 同义词 / 映射
    TOOL = "tool"        # 检索引擎 / MDL 模板 / 路由规则

    def __str__(self) -> str:
        return self.value


def make_scope_key(workspace_id: Optional[str], domain_id: Optional[str]) -> str:
    return f"{workspace_id or '-'}::{domain_id or '-'}"


@dataclass
class ConceptGap:
    expression: str
    scope_key: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    heat: int = 1
    source_counts: Dict[str, int] = field(default_factory=dict)
    sources: List[Dict[str, Any]] = field(default_factory=list)  # 最近 50 条 occurrence
    attribution_counts: Dict[str, int] = field(default_factory=dict)  # {layer: count} 全量计数
    status: str = GapStatus.OPEN.value
    first_seen: str = field(default_factory=_utc_now_iso)
    last_seen: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    promoted_candidate_id: Optional[str] = None
    resolved_term_id: Optional[str] = None
    dismiss_reason: Optional[str] = None
    workspace_id: Optional[str] = None
    domain_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "expression": self.expression,
            "scope_key": self.scope_key,
            "heat": self.heat,
            "source_counts_json": dict(self.source_counts),
            "sources_json": list(self.sources),
            "attribution_counts_json": dict(self.attribution_counts),
            "status": self.status,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "updated_at": self.updated_at,
            "promoted_candidate_id": self.promoted_candidate_id,
            "resolved_term_id": self.resolved_term_id,
            "dismiss_reason": self.dismiss_reason,
            "workspace_id": self.workspace_id,
            "domain_id": self.domain_id,
        }


__all__ = ["ConceptGap", "GapStatus", "GapSignalSource", "GapLayer", "make_scope_key"]
