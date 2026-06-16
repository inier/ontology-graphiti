"""统一摄入路由

提供 POST /api/ingest/unified 统一摄入端点，
根据 source_type 自动路由到 IngestService 或 PerceptionHub。
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from odap.infra.security.jwt_auth import get_current_user
from ..unified_ingest_facade import get_unified_ingest_facade

router = APIRouter(prefix="/api/ingest", tags=["unified-ingest"])


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

        # 构建路由参数（只传递非 None 值）
        kwargs = {}
        for field_name in request.model_fields:
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
