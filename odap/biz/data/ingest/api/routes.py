"""统一摄入路由

提供 POST /api/ingest/unified 统一摄入端点，
根据 source_type 自动路由到 IngestService 或 PerceptionHub。

语义管理台联动（T2 Ingest→Pipeline 后台集成）：
  natural_language + 配置开关开启时，会 fire-and-forget 异步触发
  OL Pipeline（L1~L5 本体学习）。失败不影响 API 返回（仅 warning log）。
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from odap.infra.security.jwt_auth import get_current_user
from ..unified_ingest_facade import get_unified_ingest_facade

router = APIRouter(prefix="/api/ingest", tags=["unified-ingest"])

logger = logging.getLogger(__name__)


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "ingest", workspace_id: str = "default"):
    """摄入审计便捷函数"""
    try:
        from odap.infra.security.unified_audit import log_audit
        log_audit(
            action=action,
            resource="ingest",
            user=user_id,
            service=service,
            result_status=result_status,
            result_message=result_message,
            details=details or {},
            workspace_id=workspace_id,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Ingest → OL Pipeline 后台异步触发（完全 fire-and-forget）
# ---------------------------------------------------------------------------
async def _ingest_auto_run_pipeline(
    *,
    workspace_id: str,
    text: str,
    extra_docs: Optional[List[str]],
    source_type: str,
    source_ref: Optional[str],
    ontology_id: Optional[str],
    triggered_by: str,
) -> None:
    """异步后台：同步 PipelineService.run_pipeline 放到子线程执行，避免阻塞 loop。

    失败不抛出，只记录 warning log。
    """
    try:
        # 延迟导入（避免循环：semantic_admin → infra → ...）
        from odap.biz.semantic_admin.ol_pipeline.services.pipeline_service import (
            PipelineService,
        )

        def _sync_run() -> Dict[str, Any]:
            svc = PipelineService()
            return svc.run_pipeline(
                workspace_id=workspace_id,
                text=text or "",
                extra_docs=list(extra_docs or []),
                ontology_id=ontology_id,
                source_type=source_type or "natural_language",
                source_ref=source_ref,
                triggered_by=triggered_by,
            )

        result = await asyncio.to_thread(_sync_run)
        status = result.get("status") if isinstance(result, dict) else "unknown"
        run_id = result.get("pipeline_run_id") if isinstance(result, dict) else None
        candidates = (
            result.get("candidate_count") if isinstance(result, dict) else None
        )
        logger.info(
            "ingest→pipeline auto triggered: ws=%s run=%s status=%s candidates=%s",
            workspace_id, run_id, status, candidates,
        )
    except Exception as exc:  # pragma: no cover - 防御性兜底
        logger.warning(
            "ingest→pipeline auto failed (non-fatal): ws=%s triggered_by=%s err=%s",
            workspace_id, triggered_by, exc,
        )


class UnifiedIngestRequest(BaseModel):
    """统一摄入请求"""
    source_type: str = Field(
        ...,
        description=(
            "数据源类型: url | news | tavily | manual | json | "
            "natural_language | random_events | database | "
            "webhook | sensor | mcp | file | api"
        ),
    )
    # 摄入契约参数
    ontology_id: Optional[str] = Field(None, description="所属本体 ID（约束性抽取时必填）")
    extraction_mode: Optional[str] = Field(
        "constrained",
        description="抽取模式: constrained（约束性，基于已有模型定义）| exploratory（探索性，推断类型结构）",
    )
    # 文档驱动参数
    url: Optional[str] = Field(None, description="URL 源地址 (source_type=url)")
    query: Optional[str] = Field(None, description="搜索查询词 (source_type=news/tavily)")
    event_context: Optional[str] = Field(None, description="事件上下文 (source_type=url/news/tavily)")
    max_sources: Optional[int] = Field(5, description="最大源数量 (source_type=news/tavily)")
    search_depth: Optional[str] = Field("basic", description="搜索深度 (source_type=tavily)")
    form_data: Optional[Any] = Field(None, description="手动录入表单数据 (source_type=manual)")
    raw_json: Optional[str] = Field(None, description="JSON 字符串 (source_type=json)")
    text: Optional[str] = Field(None, description="自然语言文本 (source_type=natural_language)")
    parties: Optional[List[str]] = Field(None, description="参与方列表 (source_type=random_events)")
    count: Optional[int] = Field(1, description="生成数量 (source_type=random_events)")
    generator_type: Optional[str] = Field("military", description="生成器类型 (source_type=random_events)")
    connection_id: Optional[str] = Field(None, description="数据库连接标识 (source_type=database)")
    table_patterns: Optional[List[str]] = Field(None, description="表名过滤 (source_type=database)")
    # 事件驱动参数
    payload: Optional[Dict[str, Any]] = Field(None, description="Webhook 载荷 (source_type=webhook)")
    headers: Optional[Dict[str, str]] = Field(None, description="Webhook 请求头 (source_type=webhook)")
    sensor_id: Optional[str] = Field(None, description="传感器 ID (source_type=sensor)")
    value: Optional[Any] = Field(None, description="传感器值 (source_type=sensor)")
    content: Optional[str] = Field(None, description="原始内容 (source_type=mcp/file/api)")
    structured_data: Optional[Dict[str, Any]] = Field(None, description="结构化数据 (source_type=mcp/file/api)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    # 通用参数
    scenario_id: Optional[str] = Field(None, description="场景 ID")
    workspace_id: Optional[str] = Field("default", description="工作空间 ID")
    scenario_context: Optional[Dict[str, Any]] = Field(None, description="场景上下文")
    # 语义学习：后台自动触发 OL Pipeline 配置（可选）
    config: Optional[Dict[str, Any]] = Field(
        None, description="摄入扩展配置。语义学习相关：config.auto_pipeline=True 时自然语言摄入自动跑 L1~L5",
    )


class UnifiedIngestResponse(BaseModel):
    """统一摄入响应"""
    status: str
    source_type: str
    record_id: Optional[str] = None
    event_id: Optional[str] = None
    routed_to: Optional[str] = None
    message: Optional[str] = None
    extraction_confidence: Optional[float] = None


@router.post("/unified", response_model=UnifiedIngestResponse)
async def unified_ingest(
    request: UnifiedIngestRequest,
    user=Depends(get_current_user),
):
    """统一摄入端点 — 根据 source_type 自动路由"""
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        facade = get_unified_ingest_facade()

        # 构建路由参数（只传递非 None 值，避免把配置 config 泄漏到下层 ingest）
        kwargs = {}
        for field_name in request.model_fields:
            if field_name == "config":
                continue
            val = getattr(request, field_name, None)
            if val is not None:
                kwargs[field_name] = val

        # source_type 单独提取，不作为 kwargs 传递
        source_type = kwargs.pop("source_type")

        result = await facade.ingest(source_type, **kwargs)
        _audit(
            action="ingest_unified",
            user_id=user_id,
            result_status="success",
            details={
                "source_type": source_type,
                "workspace_id": request.workspace_id or "default",
                "scenario_id": request.scenario_id,
            },
            workspace_id=request.workspace_id or "default",
        )

        # -------------------------------------------------------------------
        # T2：Ingest → OL Pipeline 自动触发（fire-and-forget）
        # 触发三条件（全部满足）：
        #   1. 有 workspace_id
        #   2. 开关开启：request.config.auto_pipeline=True 或
        #      环境变量 INGEST_AUTO_PIPELINE_DEFAULT='true'
        #   3. source_type == 'natural_language'
        # -------------------------------------------------------------------
        ws_id = request.workspace_id
        req_cfg = request.config or {}
        env_default = os.environ.get("INGEST_AUTO_PIPELINE_DEFAULT", "false")
        auto_pipeline: bool = bool(req_cfg.get("auto_pipeline")) or (
            str(env_default).lower() == "true"
        )
        if (
            ws_id
            and auto_pipeline
            and source_type == "natural_language"
        ):
            ingest_id = str(result.get("record_id") or result.get("event_id") or "")
            extra_docs = []
            if request.event_context:
                extra_docs.append(request.event_context)
            if request.content:
                extra_docs.append(request.content)
            # 不 await：完全 fire and forget
            asyncio.create_task(
                _ingest_auto_run_pipeline(
                    workspace_id=str(ws_id),
                    text=request.text or "",
                    extra_docs=extra_docs,
                    source_type="natural_language",
                    source_ref=ingest_id or None,
                    ontology_id=request.ontology_id,
                    triggered_by=f"ingest_{ingest_id or user_id}",
                ),
                name=f"ingest_auto_ol_pipeline:{ws_id}:{ingest_id}",
            )

        return UnifiedIngestResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        _audit(
            action="ingest_unified_failed",
            user_id=user_id,
            result_status="failure",
            result_message=str(e),
            details={
                "source_type": request.source_type,
                "workspace_id": request.workspace_id or "default",
                "scenario_id": request.scenario_id,
            },
            workspace_id=request.workspace_id or "default",
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/source-types")
async def get_supported_source_types(
    user=Depends(get_current_user),
):
    """获取所有支持的源类型"""
    user_id = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        facade = get_unified_ingest_facade()
        result = facade.get_supported_source_types()
        _audit(
            action="ingest_list_source_types",
            user_id=user_id,
            result_status="success",
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit(
            action="ingest_list_source_types_failed",
            user_id=user_id,
            result_status="failure",
            result_message=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))
