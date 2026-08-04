"""Semantic Retrieval API routes (spec 008 / contracts/api-contracts.md).

端点（前缀 /api/semantic-retrieval）：
- POST /query         统一检索（auto 路由）FR-001
- POST /graph         分项图检索 FR-005
- POST /nl            分项 NL 检索（USL 消歧）FR-003/FR-016
- POST /metric        分项指标查询 FR-006
- POST /chain         分项链式推理 FR-004
- POST /mdl           分项 MDL/DSL 推理 FR-004
- POST /hybrid        混合检索编排 FR-007/008
- POST /stream        AG-UI 流式检索（SSE）FR-008 / Iter 4.2
- POST /stream/chain  AG-UI 流式链式推理（SSE）Iter 4.2

安全（project_memory 规则）：
- 所有端点 user=Depends(get_current_user)（强制认证，禁止 optional）
- workspace_id 从 JWT ws_id 提取（FR-012 隔离）
- HTTPException 透传，service ValueError → 400，其它异常 → 500
- 审计不记明文（FR-013），query_audit 埋点（Iter 3.2 #5）
"""

import logging
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from odap.infra.security.audit_helper import extract_workspace_id, query_audit
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.sse_utils import SSE_HEADERS, sse_response

from ..models.schemas import (
    ChainRequest,
    HybridRequest,
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


def _emit_query_audit(
    operator: str,
    workspace_id: str,
    query: str,
    mode: str,
    total: int,
    extra: Dict[str, Any] = None,
) -> None:
    """Iter 3.2 #5 查询审计埋点（fire-and-forget，不阻塞响应）。

    审计不记明文（FR-013）：query 截断到 100 字符，只记统计指标。
    """
    try:
        query_audit(
            operator=operator,
            query_params={
                "query": query[:100],
                "retrieval_type": mode,
                "workspace_id": workspace_id,
            },
            result_summary={
                "count": total,
                "mode": mode,
                **(extra or {}),
            },
            workspace_id=workspace_id,
        )
    except Exception as exc:
        logger.warning("query_audit 埋点失败（不影响检索）: %s", exc)


@router.post("/query", response_model=SearchResult)
async def unified_query(request: SearchRequest, user=Depends(get_current_user)):
    """统一检索：调用方仅给 query + mode=auto，引擎自动路由（FR-001）。"""
    workspace_id = extract_workspace_id(user)
    operator_id, _ = _extract_operator(user)
    try:
        result = await _service.search(workspace_id, request)
    except HTTPException:
        raise
    except ValueError as exc:
        # 不支持的 mode（如 chain/mdl/metric 尚未实现）→ 400
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("unified query failed")
        raise HTTPException(status_code=500, detail=str(exc))
    _emit_query_audit(operator_id, workspace_id, request.query, result.mode, result.total)
    return result


@router.post("/graph", response_model=SearchResult)
async def graph_search(request: SearchRequest, user=Depends(get_current_user)):
    """分项图检索（FR-005）。"""
    workspace_id = extract_workspace_id(user)
    operator_id, _ = _extract_operator(user)
    try:
        raw = await _service.graph_search(workspace_id, request.query, limit=request.limit)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("graph search failed")
        raise HTTPException(status_code=500, detail=str(exc))
    _emit_query_audit(operator_id, workspace_id, request.query, "graph", raw["total"])
    return SearchResult(
        query=request.query, mode="graph", total=raw["total"], rows=raw["rows"], explain=raw.get("explain")
    )


@router.post("/nl", response_model=SearchResult)
async def nl_search(request: SearchRequest, user=Depends(get_current_user)):
    """分项 NL 检索 + USL 术语消歧（FR-003/FR-016）。"""
    workspace_id = extract_workspace_id(user)
    operator_id, _ = _extract_operator(user)
    try:
        raw = await _service.nl_search(workspace_id, request.query, limit=request.limit)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("nl search failed")
        raise HTTPException(status_code=500, detail=str(exc))
    _emit_query_audit(operator_id, workspace_id, request.query, "nl", raw["total"])
    return SearchResult(
        query=request.query, mode="nl", total=raw["total"], rows=raw["rows"], explain=raw.get("explain")
    )


@router.post("/metric", response_model=SearchResult)
async def metric_query(request: MetricRequest, user=Depends(get_current_user)):
    """分项指标查询 — TBox 自动派生 count/density/trend (FR-006 / US2 BI 工具)。"""
    workspace_id = extract_workspace_id(user)
    operator_id, _ = _extract_operator(user)
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
    _emit_query_audit(
        operator_id, workspace_id, f"metric:{request.metric}", "metric", raw["total"],
        extra={"metric": request.metric},
    )
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
    operator_id, _ = _extract_operator(user)
    try:
        raw = await _service.chain_search(
            workspace_id,
            query=request.query,
            rules=list(request.rules),
            max_depth=request.max_depth,
            persist_candidates=request.persist_candidates,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("chain reason failed")
        raise HTTPException(status_code=500, detail=str(exc))
    _emit_query_audit(
        operator_id, workspace_id, request.query, "chain", raw["total"],
        extra={"cycle": raw["reasoning"]["cycle_detected"], "depth": request.max_depth},
    )
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
    operator_id, _ = _extract_operator(user)
    try:
        raw = await _service.mdl_search(
            workspace_id,
            query=request.query,
            persist_candidates=request.persist_candidates,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("mdl reason failed")
        raise HTTPException(status_code=500, detail=str(exc))
    _emit_query_audit(
        operator_id, workspace_id, request.query, "mdl", raw["total"],
        extra={"template": raw["reasoning"]["template"], "status": raw["reasoning"]["status"]},
    )
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


@router.post("/hybrid", response_model=SearchResult)
async def hybrid_search(request: HybridRequest, user=Depends(get_current_user)):
    """混合检索编排 — 多组件顺序执行 + on_failure 容错 (FR-007/008 / US4)。"""
    workspace_id = extract_workspace_id(user)
    operator_id, _ = _extract_operator(user)
    components = [c.model_dump() for c in request.components]
    try:
        raw = await _service.hybrid_search(
            workspace_id,
            components,
            merge=request.merge,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("hybrid search failed")
        raise HTTPException(status_code=500, detail=str(exc))
    _emit_query_audit(
        operator_id, workspace_id, f"hybrid:{len(components)}components", "hybrid", raw["total"],
        extra={"components": len(components), "warnings": len(raw.get("warnings", []))},
    )
    return SearchResult(
        query=f"hybrid:{len(components)}components",
        mode="hybrid",
        total=raw["total"],
        rows=raw["rows"],
        components=raw["components"],
        explain={"request_id": raw["request_id"]},
        warnings=list(raw.get("warnings", [])),
    )


# ------------------------------------------------------------------
# Iter 4.2: AG-UI 流式检索端点（SSE）
# ------------------------------------------------------------------


async def _agui_event_stream(event_generator) -> "StreamingResponse":
    """将 AG-UI 事件流封装为 SSE StreamingResponse。"""
    import json

    async def sse_generator():
        async for event_dict in event_generator:
            yield f"data: {json.dumps(event_dict, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("/stream")
async def stream_query(request: SearchRequest, user=Depends(get_current_user)):
    """AG-UI 流式检索（SSE）— 检索结果按 AG-UI 协议流式返回（FR-008 / Iter 4.2）。

    事件序列：
        RUN_STARTED → STEP_STARTED → TEXT_MESSAGE_* → STEP_FINISHED → RUN_FINISHED

    低置信度结果触发 Interrupt（HITL 确认）。
    """
    workspace_id = extract_workspace_id(user)
    operator_id, _ = _extract_operator(user)

    try:
        from odap.infra.openharness.agui.retrieval_adapter import RetrievalAGUIAdapter

        adapter = RetrievalAGUIAdapter(retrieval_service=_service)
        event_gen = adapter.stream_search(
            workspace_id=workspace_id,
            query=request.query,
            mode=request.mode,
            limit=request.limit,
            operator=operator_id,
        )
        return await _agui_event_stream(event_gen)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("stream_query 端点异常")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stream/chain")
async def stream_chain_query(request: ChainRequest, user=Depends(get_current_user)):
    """AG-UI 流式链式推理（SSE）— 每个推理步骤一个 STEP 事件（Iter 4.2）。

    事件序列：
        RUN_STARTED → (STEP_STARTED → TEXT_MESSAGE_CONTENT → STEP_FINISHED)* → RUN_FINISHED

    循环检测触发 Interrupt（HITL 确认）。
    """
    workspace_id = extract_workspace_id(user)
    operator_id, _ = _extract_operator(user)

    try:
        from odap.infra.openharness.agui.retrieval_adapter import RetrievalAGUIAdapter

        adapter = RetrievalAGUIAdapter(retrieval_service=_service)
        event_gen = adapter.stream_chain_search(
            workspace_id=workspace_id,
            query=request.query,
            rules=list(request.rules),
            max_depth=request.max_depth,
            operator=operator_id,
        )
        return await _agui_event_stream(event_gen)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("stream_chain_query 端点异常")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
