"""SemanticAssetPipeline Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    """统一编排入口请求。"""
    source_type: str = Field(..., description="数据源类型（structured/unstructured 之一）")
    ontology_id: Optional[str] = Field(default=None, description="目标本体 ID（约束性抽取必填）")
    extraction_mode: str = Field(default="exploratory", description="constrained | exploratory")
    template_ref: Optional[str] = Field(default=None, description="模板名/路径（非结构化链路）")
    payload: Dict[str, Any] = Field(default_factory=dict, description="各源所需参数（text/json/url/...）")
    scenario_id: str = Field(default="", description="场景 ID")
    workspace_id: str = Field(default="default", description="工作空间 ID")


class PipelineSubmitRequest(BaseModel):
    """提交审核请求。"""
    pipeline_run_id: str = Field(..., description="Pipeline 运行 ID")


class PipelineRunResponse(BaseModel):
    """统一编排入口响应。"""
    status: str = "ok"
    pipeline_run_id: Optional[str] = None
    source_kind: Optional[str] = None
    source_type: Optional[str] = None
    candidate_count: int = 0
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    session_id: Optional[str] = None
    template_used: Optional[str] = None
    degradation_flags: List[str] = Field(default_factory=list)
    ingest: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
