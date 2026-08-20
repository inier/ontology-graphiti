"""图分析 REST API（ADR-078，按 workspace 隔离）。

端点：
- GET /api/graph-analytics/centrality?metric=degree&top_k=10&workspace_id=
- GET /api/graph-analytics/community?algo=louvain&workspace_id=
- GET /api/graph-analytics/link-prediction?source=&target=&workspace_id=
- GET /api/graph-analytics/shortest-path?source=&target=&workspace_id=
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from odap.infra.security.jwt_auth import get_current_user

router = APIRouter(prefix="/api/graph-analytics", tags=["graph-analytics"])


@router.get("/centrality")
async def centrality(
    metric: str = Query("degree", description="degree|betweenness|closeness|eigenvector|pagerank"),
    top_k: int = Query(10, ge=1, le=100),
    workspace_id: str = Query("default"),
    user=Depends(get_current_user),
):
    from ..service import get_analytics_service
    try:
        return get_analytics_service().centrality(
            metric=metric, top_k=top_k, workspace_id=workspace_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/community")
async def community(
    algo: str = Query("louvain", description="louvain|label_propagation|girvan_newman"),
    workspace_id: str = Query("default"),
    user=Depends(get_current_user),
):
    from ..service import get_analytics_service
    try:
        return get_analytics_service().community(algo=algo, workspace_id=workspace_id)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/link-prediction")
async def link_prediction(
    source: str = Query(...),
    target: str = Query(...),
    workspace_id: str = Query("default"),
    user=Depends(get_current_user),
):
    from ..service import get_analytics_service
    try:
        return get_analytics_service().link_prediction(
            source=source, target=target, workspace_id=workspace_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shortest-path")
async def shortest_path(
    source: str = Query(...),
    target: str = Query(...),
    weighted: bool = Query(False),
    workspace_id: str = Query("default"),
    user=Depends(get_current_user),
):
    from ..service import get_analytics_service
    try:
        return get_analytics_service().shortest_path(
            source=source, target=target, weighted=weighted, workspace_id=workspace_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
