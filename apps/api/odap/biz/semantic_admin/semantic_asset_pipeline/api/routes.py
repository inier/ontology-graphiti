"""SemanticAssetPipeline FastAPI Routes。

注册前缀：/api/semantic-assets/pipeline
  GET  /options                → 下拉选项（数据源/模板/本体）
  POST /run                    → 统一编排入口（结构化引入 / 非结构化抽取）
  GET  /{run_id}               → 查询一次 pipeline 的产出候选
  POST /{run_id}/submit        → 将 DRAFT 候选提交审核（→ PENDING_REVIEW）
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from odap.infra.security.jwt_auth import get_current_user
from odap.biz.semantic_admin.semantic_asset_pipeline.services.pipeline_service import (
    get_semantic_asset_pipeline,
)

from .schemas import PipelineRunRequest, PipelineSubmitRequest, PipelineRunResponse

router = APIRouter(
    prefix="/api/semantic-assets/pipeline",
    tags=["semantic-asset-pipeline"],
)


def _actor(user: Any) -> str:
    if isinstance(user, dict):
        return str(user.get("sub") or user.get("username") or "system")
    return "system"


@router.get("/options")
async def pipeline_options(
    ontology_id: Optional[str] = Query(default=None),
    _user: Any = Depends(get_current_user),
):
    """返回 Pipeline 向导所需选项。"""
    pipeline = get_semantic_asset_pipeline()
    try:
        return pipeline.options(ontology_id=ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/usl-ontologies")
async def usl_ontologies(
    workspace_id: Optional[str] = Query(default=None),
    _user: Any = Depends(get_current_user),
):
    """列出 USL 系统本体（USL 本体管理界面数据源）。"""
    pipeline = get_semantic_asset_pipeline()
    try:
        return pipeline.list_usl_ontologies(workspace_id=workspace_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=PipelineRunResponse)
async def pipeline_run(
    body: PipelineRunRequest,
    _user: Any = Depends(get_current_user),
) -> PipelineRunResponse:
    """统一编排入口。"""
    pipeline = get_semantic_asset_pipeline()
    try:
        result = await pipeline.run(
            source_type=body.source_type,
            ontology_id=body.ontology_id,
            extraction_mode=body.extraction_mode,
            template_ref=body.template_ref,
            payload=body.payload,
            scenario_id=body.scenario_id,
            workspace_id=body.workspace_id,
            actor=_actor(_user),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return PipelineRunResponse(**result)


@router.get("/{pipeline_run_id}")
async def pipeline_get_run(
    pipeline_run_id: str,
    _user: Any = Depends(get_current_user),
):
    """查询一次 pipeline 的产出候选。"""
    pipeline = get_semantic_asset_pipeline()
    try:
        result = pipeline.get_run(pipeline_run_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


@router.post("/{pipeline_run_id}/submit")
async def pipeline_submit(
    pipeline_run_id: str,
    body: PipelineSubmitRequest,
    _user: Any = Depends(get_current_user),
):
    """将 pipeline 下所有 DRAFT 候选提交审核。"""
    pipeline = get_semantic_asset_pipeline()
    try:
        result = pipeline.submit(pipeline_run_id, actor=_actor(_user))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result


__all__ = ["router"]
