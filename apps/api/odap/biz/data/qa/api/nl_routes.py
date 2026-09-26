"""NL 本体查询服务 - 新增 API 路由"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from odap.biz.data.qa.models import QueryRequest, QueryResponse, RetrievalResultSet
from odap.biz.data.qa.pipeline.query_pipeline import get_query_pipeline
from odap.biz.data.qa.evaluation.audit_storage import QueryAuditStorage
from odap.infra.security.jwt_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/qa", tags=["qa-nl"])

_audit_storage_instance: Optional[QueryAuditStorage] = None


def _get_audit_storage() -> QueryAuditStorage:
    global _audit_storage_instance
    if _audit_storage_instance is None:
        _audit_storage_instance = QueryAuditStorage()
    return _audit_storage_instance


# ── 请求/响应模型 ──────────────────────────────────────────────────────

class NLSearchRequest(BaseModel):
    """纯检索请求"""
    query: str
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    user_id: str = "anonymous"
    mode: str = "auto"
    top_k: int = 10


class NLSearchResponse(BaseModel):
    """纯检索响应"""
    results: List[Dict[str, Any]] = Field(default_factory=list)
    pillar_scores: Dict[str, float] = Field(default_factory=dict)
    total: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NLPlanRequest(BaseModel):
    """查询计划预览请求"""
    query: str
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    mode: str = "auto"
    top_k: int = 10


class NLExplainRequest(BaseModel):
    """查询解释请求"""
    query: str
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    mode: str = "auto"
    top_k: int = 10


class NLExplainResponse(BaseModel):
    """查询解释响应"""
    original_query: str
    understanding: Dict[str, Any] = Field(default_factory=dict)
    plan: Dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""


class PillarStatusResponse(BaseModel):
    """三支柱状态响应"""
    pillars: List[Dict[str, Any]] = Field(default_factory=list)
    index_info: Dict[str, Any] = Field(default_factory=dict)


class AuditDetailResponse(BaseModel):
    """审计详情响应"""
    record: Dict[str, Any] = Field(default_factory=dict)


class AuditListResponse(BaseModel):
    """审计列表响应"""
    records: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0


class AuditStatsResponse(BaseModel):
    """审计统计响应"""
    total_queries: int = 0
    avg_time_ms: float = 0.0
    pillar_usage: Dict[str, int] = Field(default_factory=dict)


# ── 路由 ──────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse)
async def nl_query(request: NLSearchRequest, user=Depends(get_current_user)):
    """完整查询 - 五阶段管线（Understanding→Planning→Execution→Fusion→Generation）"""
    if not request.query:
        raise HTTPException(status_code=400, detail="查询不能为空")
    try:
        pipeline = get_query_pipeline()
        query_request = QueryRequest(
            query=request.query,
            workspace_id=request.workspace_id,
            scenario_id=request.scenario_id,
            user_id=request.user_id,
            mode=request.mode,
            top_k=request.top_k,
        )
        result = await pipeline.query(query_request)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"查询服务不可用: {str(e)}")


@router.post("/search", response_model=NLSearchResponse)
async def nl_search(request: NLSearchRequest, user=Depends(get_current_user)):
    """纯检索 - 不生成回答，仅返回检索结果"""
    if not request.query:
        raise HTTPException(status_code=400, detail="查询不能为空")
    try:
        pipeline = get_query_pipeline()
        query_request = QueryRequest(
            query=request.query,
            workspace_id=request.workspace_id,
            scenario_id=request.scenario_id,
            user_id=request.user_id,
            mode=request.mode,
            top_k=request.top_k,
        )
        result_set = await pipeline.search(query_request)
        return NLSearchResponse(
            results=[r.model_dump() for r in result_set.results],
            pillar_scores=result_set.pillar_scores,
            total=len(result_set.results),
            metadata=result_set.metadata,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"检索服务不可用: {str(e)}")


@router.post("/plan", response_model=Dict[str, Any])
async def nl_plan(request: NLPlanRequest, user=Depends(get_current_user)):
    """查询计划预览 - 返回 QueryPlan，不执行"""
    if not request.query:
        raise HTTPException(status_code=400, detail="查询不能为空")
    try:
        pipeline = get_query_pipeline()
        query_request = QueryRequest(
            query=request.query,
            workspace_id=request.workspace_id,
            scenario_id=request.scenario_id,
            mode=request.mode,
            top_k=request.top_k,
        )
        explanation = pipeline.explain(query_request)
        return explanation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"查询规划不可用: {str(e)}")


@router.post("/explain", response_model=NLExplainResponse)
async def nl_explain(request: NLExplainRequest, user=Depends(get_current_user)):
    """查询解释 - 展示 NL 如何被理解和转换为查询"""
    if not request.query:
        raise HTTPException(status_code=400, detail="查询不能为空")
    try:
        pipeline = get_query_pipeline()
        query_request = QueryRequest(
            query=request.query,
            workspace_id=request.workspace_id,
            scenario_id=request.scenario_id,
            mode=request.mode,
            top_k=request.top_k,
        )
        explanation = pipeline.explain(query_request)
        return NLExplainResponse(
            original_query=explanation.get("original_query", ""),
            understanding=explanation.get("understanding", {}),
            plan=explanation.get("plan", {}),
            explanation=explanation.get("explanation", ""),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"查询解释不可用: {str(e)}")


@router.get("/retrieval/pillars", response_model=PillarStatusResponse)
async def get_pillar_status(user=Depends(get_current_user)):
    """查看三支柱状态和索引信息（如实探针，不谎报）。

    判定依据：
    - vector / graph 支柱真实依赖 GraphManager 连接，读取其公开 mode 属性
      （graphiti / neo4j_driver = 已连接；fallback / unavailable = 未连接）。
    - bm25 支柱基于本地倒排索引（按 workspace 惰性构建），不依赖图数据库，
      通过实际构造 BM25Retriever 探测其可用性。
    每个支柱返回 reason 字段说明判定依据，index_info 返回真实连接事实。
    """
    # 已连接的图谱模式（其余 fallback / unavailable 视为未连接）
    _CONNECTED_MODES = ("graphiti", "neo4j_driver")

    graph_mode = "unknown"
    graph_connected = False
    graph_reason = ""
    try:
        from odap.infra.graph.graph_service import GraphManager
        gm = GraphManager()
        # D-健康检查修复：原调用不存在的 gm.is_available() 恒抛 AttributeError；
        # 改用真实公开的 mode 属性判定连接状态。
        graph_mode = getattr(gm, "mode", "unknown")
        graph_connected = graph_mode in _CONNECTED_MODES
        graph_reason = (
            f"GraphManager.mode={graph_mode}"
            + ("" if graph_connected else "（未连接图数据库，vector/graph 支柱不可用）")
        )
    except Exception as e:
        graph_mode = "error"
        graph_connected = False
        graph_reason = f"GraphManager 初始化失败: {e}"
        logger.warning("retrieval/pillars 图谱探针失败: %s", e)

    # bm25 探针：实际构造 BM25Retriever（不依赖图数据库）
    bm25_status = "available"
    bm25_reason = "本地倒排索引，按 workspace 惰性构建"
    try:
        from odap.biz.data.qa.retrieval.bm25_retriever import BM25Retriever
        BM25Retriever()
    except Exception as e:
        bm25_status = "unavailable"
        bm25_reason = f"BM25Retriever 构造失败: {e}"
        logger.warning("retrieval/pillars BM25 探针失败: %s", e)

    vector_status = "available" if graph_connected else "unavailable"
    graph_status = "available" if graph_connected else "unavailable"

    pillars = [
        {"name": "bm25", "description": "精准关键词检索",
         "status": bm25_status, "reason": bm25_reason},
        {"name": "vector", "description": "语义相似度检索",
         "status": vector_status, "reason": graph_reason},
        {"name": "graph", "description": "图关联推理检索",
         "status": graph_status, "reason": graph_reason},
    ]

    index_info = {
        "graph_mode": graph_mode,
        "graph_connected": graph_connected,
        "connected_modes": list(_CONNECTED_MODES),
    }

    return PillarStatusResponse(pillars=pillars, index_info=index_info)


# ── 审计路由 ──────────────────────────────────────────────────────────

@router.get("/audit/{query_id}", response_model=AuditDetailResponse)
async def get_audit_detail(query_id: str, user=Depends(get_current_user)):
    """查询单次审计详情"""
    try:
        storage = _get_audit_storage()
        record = storage.get(query_id)
        if not record:
            raise HTTPException(status_code=404, detail="审计记录不存在")
        return AuditDetailResponse(record=record)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"审计查询不可用: {str(e)}")


@router.get("/audit", response_model=AuditListResponse)
async def list_audit_records(
    workspace_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(get_current_user)
):
    """查询审计列表"""
    try:
        storage = _get_audit_storage()
        records = storage.list_records(workspace_id, user_id, limit, offset)
        return AuditListResponse(records=records, total=len(records))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"审计查询不可用: {str(e)}")


@router.get("/audit/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    workspace_id: Optional[str] = Query(None),
    user=Depends(get_current_user)
):
    """审计统计"""
    try:
        storage = _get_audit_storage()
        stats = storage.get_stats(workspace_id)
        return AuditStatsResponse(**stats)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"审计统计不可用: {str(e)}")


# ── 评估路由 ──────────────────────────────────────────────────────────

class EvalResponse(BaseModel):
    """评估响应"""
    dataset_name: str = ""
    total_cases: int = 0
    retrieval_metrics: Dict[str, float] = Field(default_factory=dict)
    qa_metrics: Dict[str, float] = Field(default_factory=dict)
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    pillar_usage: Dict[str, int] = Field(default_factory=dict)


@router.post("/evaluate", response_model=EvalResponse)
async def run_evaluation(user=Depends(get_current_user)):
    """运行评估基准测试"""
    try:
        from odap.biz.data.qa.evaluation.benchmark import BenchmarkRunner, get_default_benchmark
        runner = BenchmarkRunner()
        dataset = get_default_benchmark()
        report = await runner.run(dataset)
        return EvalResponse(
            dataset_name=report.dataset_name,
            total_cases=report.total_cases,
            retrieval_metrics=report.retrieval_metrics.model_dump(),
            qa_metrics=report.qa_metrics.model_dump(),
            latency_p50_ms=report.latency_p50_ms,
            latency_p95_ms=report.latency_p95_ms,
            pillar_usage=report.pillar_usage,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"评估服务不可用: {str(e)}")
