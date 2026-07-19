"""+AI Reasoning API — 统一检索端点。

POST /api/reasoning/retrieve — 全平台统一数据检索
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..services.unified_retrieve import (
    RetrieveRequest, RetrieveResult,
    get_retrieve_engine,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reasoning", tags=["reasoning"])


@router.post("/retrieve", response_model=dict)
async def unified_retrieve(
    query: str,
    workspace_id: str = "default",
    ontology_id: Optional[str] = None,
    ontology_ids: Optional[str] = None,
    source_types: Optional[str] = None,
    top_k: int = 20,
    include_provenance: bool = True,
    include_metrics: bool = False,
):
    """全平台统一数据检索。

    支持跨源联邦查询:
    - schema: 本体类型定义
    - entity: 运行时实体实例
    - document: 非结构化文档

    每个结果包含4级溯源链（如果 include_provenance=true）:
    原始文档 → 提取记录 → 构建操作 → 图谱实体
    """
    try:
        ont_ids = []
        if ontology_ids:
            ont_ids = [o.strip() for o in ontology_ids.split(",") if o.strip()]
        elif ontology_id:
            ont_ids = [ontology_id]

        src_types = ["schema", "entity", "document"]
        if source_types:
            src_types = [s.strip() for s in source_types.split(",") if s.strip()]

        request = RetrieveRequest(
            query=query,
            workspace_id=workspace_id,
            ontology_ids=ont_ids,
            source_types=src_types,
            top_k=top_k,
            include_provenance=include_provenance,
            include_metrics=include_metrics,
        )

        engine = get_retrieve_engine()
        result = await engine.retrieve(request)
        return result.to_dict()
    except Exception as e:
        logger.error("Unified retrieve failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrieve/health")
async def retrieve_health():
    """检索服务健康检查"""
    return {"status": "ok", "service": "UnifiedRetrieveEngine"}


@router.get("/provenance/{entity_id}")
async def trace_provenance(entity_id: str):
    """查询单个实体的完整溯源链"""
    try:
        from odap.biz.core.ontology.construction.provenance.provenance_linker import get_provenance_linker
        linker = get_provenance_linker()
        chain = linker.link_chain(entity_id)
        return {
            "entity_id": entity_id,
            "chain": chain.to_dict(),
            "is_complete": chain.is_complete(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
