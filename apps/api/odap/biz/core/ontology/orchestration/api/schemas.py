"""本体问答 API 请求模型（openapi-v2 `QaRequest`）。"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RetrievalMode(str, Enum):
    AUTO = "auto"
    CHAIN = "chain"
    NL = "nl"
    MDL = "mdl"
    GRAPH = "graph"
    METRIC = "metric"


class QaRequest(BaseModel):
    """`query` 声明为可选，由 service 抛 400 QA_QUERY_REQUIRED（错误契约统一）。"""

    model_config = ConfigDict(extra="forbid")

    query: Optional[str] = Field(default=None, description="自然语言问题")
    workspace_id: Optional[str] = None
    mode: RetrievalMode = RetrievalMode.AUTO
    allow_actions: bool = False
    locale: str = "zh-CN"


class QaActionDecision(BaseModel):
    """HITL 决策请求（AC-41）。

    `approved=false` 即驳回；`note` 仅用于审计留痕（写入日志，不落 `qa_actions`）。
    """

    model_config = ConfigDict(extra="forbid")

    approved: bool
    note: Optional[str] = Field(default=None, max_length=500)


__all__ = ["QaRequest", "RetrievalMode", "QaActionDecision"]
