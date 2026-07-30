"""Semantic Retrieval API routes (spec 008 / contracts/api-contracts.md).

端点（前缀 /api/semantic-retrieval）：
- POST /query   统一检索（auto 路由）FR-001
- POST /graph   分项图检索 FR-005
- POST /nl      分项 NL 检索（USL 消歧）FR-003/FR-016

安全（project_memory 规则）：
- 所有端点 user=Depends(get_current_user)（强制认证，禁止 optional）
- workspace_id 从 JWT ws_id 提取（FR-012 隔离）
- HTTPException 透传，service ValueError → 400，其它异常 → 500
- 审计不记明文（FR-013）
"""

import logging
from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException

from odap.infra.security.audit_helper import extract_workspace_id
from odap.infra.security.jwt_auth import get_current_user

from ..models.schemas import (
    ChainRequest,
    MdlRequest,
    MetricRequest,
    SearchRequest,
    SearchResult,
)
from ..services.retrieval_service import RetrievalService

logger = logging.getLogger("semantic_retrieval.routes")

router = APIRouter(prefix="/api/semantic-retrieval", tags=["semantic-retrieval"])

_service = RetrievalService()


def _extract_operator(user) -> Tuple[str, str]:
    """从 JWT user 提取操作者（project_memory：禁止 hardcode operator_id）。"""
    if isinstance(user, dict):
        return user.get("sub", "anonymous"), user.get("name", "anonymous")
    return "anonymous", "anonymous"


@router.post("/query", response_model=SearchResult)
async def unified_query(request: SearchRequest, user=Depends(get_current_user)):
    """统一检索：调用方仅给 query + mode=auto，引擎自动路由（FR-001）。"""
    workspace_id = extract_workspace_id(user)
    _operator_id, _operator_name = _extract_operator(user)
    try:
        return await _service.search(workspace_id, request)
    except HTTPException:
        raise
    except ValueError as exc:
        # 不支持的 mode（如 chain/mdl/metric 尚未实现）→ 400
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("unified query failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/graph", response_model=SearchResult)
async def graph_search(request: SearchRequest, user=Depends(get_current_user)):
    """分项图检索（FR-005）。"""
    workspace_id = extract_workspace_id(user)
    try:
        raw = await _service.graph_search(workspace_id, request.query, limit=request.limit)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("graph search failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return SearchResult(
        query=request.query, mode="graph", total=raw["total"], rows=raw["rows"], explain=raw.get("explain")
    )


@router.post("/nl", response_model=SearchResult)
async def nl_search(request: SearchRequest, user=Depends(get_current_user)):
    """分项 NL 检索 + USL 术语消歧（FR-003/FR-016）。"""
    workspace_id = extract_workspace_id(user)
    try:
        raw = await _service.nl_search(workspace_id, request.query, limit=request.limit)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("nl search failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return SearchResult(
        query=request.query, mode="nl", total=raw["total"], rows=raw["rows"], explain=raw.get("explain")
    )


@router.post("/metric", response_model=SearchResult)
async def metric_query(request: MetricRequest, user=Depends(get_current_user)):
    """分项指标查询 — TBox 自动派生 count/density/trend (FR-006 / US2 BI 工具)。"""
    workspace_id = extract_workspace_id(user)
    tw = request.time_window.model_dump() if request.time_window is not None else None
    try:
        raw = await _service.metric_search(
            workspace_id,
            request.metric,
            object_type=request.object_type,
            granularity=request.granularity,
            time_window=tw,
            limit=20,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("metric query failed")
        raise HTTPException(status_code=500, detail=str(exc))
    metrics = raw.get("metrics", raw["rows"])
    return SearchResult(
        query=f"metric:{request.metric}",
        mode="metric",
        total=raw["total"],
        rows=metrics,
        components=[],
        explain=raw.get("explain"),
    )


@router.post("/chain", response_model=SearchResult)
async def chain_reason(request: ChainRequest, user=Depends(get_current_user)):
    """分项链式推理 — rules[] 有序传导 + 循环检测 (FR-004/FR-014 / US3)。"""
    workspace_id = extract_workspace_id(user)
    try:
        raw = await _service.chain_search(
            workspace_id,
            query=request.query,
            rules=list(request.rules),
            max_depth=request.max_depth,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("chain reason failed")
        raise HTTPException(status_code=500, detail=str(exc))
    reasoning = raw["reasoning"]
    return SearchResult(
        query=request.query,
        mode="chain",
        total=raw["total"],
        rows=list(reasoning["steps"]),
        components=[],
        reasoning=reasoning,
        warnings=list(raw.get("warnings", [])),
    )


@router.post("/mdl", response_model=SearchResult)
async def mdl_reason(request: MdlRequest, user=Depends(get_current_user)):
    """分项 MDL/DSL 推理 — 复用 HE YAML 模板引用 (FR-004 / US3 / Q6 不发明 DSL)。"""
    workspace_id = extract_workspace_id(user)
    try:
        raw = await _service.mdl_search(
            workspace_id,
            query=request.query,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("mdl reason failed")
        raise HTTPException(status_code=500, detail=str(exc))
    reasoning = raw["reasoning"]
    return SearchResult(
        query=request.query,
        mode="mdl",
        total=raw["total"],
        rows=[reasoning],
        components=[],
        reasoning=reasoning,
        warnings=list(raw.get("warnings", [])),
    )
