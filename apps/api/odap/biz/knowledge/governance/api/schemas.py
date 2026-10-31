"""文档治理 API 请求模型（Pydantic v2）。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SupersedeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    superseded_by: str = Field(..., min_length=1, description="canonical 文档 id")


__all__ = ["SupersedeRequest"]
