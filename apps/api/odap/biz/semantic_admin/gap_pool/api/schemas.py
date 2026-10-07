from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class DismissRequest(BaseModel):
    reason: str = Field(..., description="驳回/忽略原因")


class PromoteRequest(BaseModel):
    domain_id: Optional[str] = None
    workspace_id: Optional[str] = None


class GapItem(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    expression: str
    scope_key: str
    heat: int
    status: str
