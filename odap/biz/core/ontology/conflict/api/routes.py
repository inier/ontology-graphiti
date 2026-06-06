"""
冲突解决 API 路由 (T317)

POST /api/ontology/conflict/detect  - 检测多源冲突
POST /api/ontology/conflict/resolve - 解决冲突
GET  /api/ontology/conflict/conflicts - 列出冲突
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..models import (
    ConflictCandidate,
    ConflictRecord,
    ConflictType,
)
from ..services import ConflictService


router = APIRouter(prefix="/api/ontology/conflict", tags=["conflict"])

# 模块级单例
conflict_service = ConflictService()


# ---------- Schemas ----------

class ConflictCandidateSchema(BaseModel):
    source_id: str
    value: Any
    confidence: float = 1.0
    observed_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SourceEntitySchema(BaseModel):
    id: str
    type: str = "unknown"
    fields: Dict[str, Any] = Field(default_factory=dict)


class SourceSchema(BaseModel):
    source_id: str
    entities: List[SourceEntitySchema] = Field(default_factory=list)


class DetectRequest(BaseModel):
    sources: List[SourceSchema]


class ResolveRequest(BaseModel):
    conflict: Dict[str, Any]   # 接收 ConflictRecord dict（由前端回传或服务层缓存）
    strategy: str
    context: Dict[str, Any] = Field(default_factory=dict)


# ---------- 工具函数 ----------

def _to_record(d: Dict[str, Any]) -> ConflictRecord:
    """从 dict 重建 ConflictRecord（API 边界）"""
    cands = []
    for c in d.get("candidates", []):
        observed = c.get("observed_at")
        observed_dt = datetime.fromisoformat(observed) if observed else datetime.now()
        cands.append(ConflictCandidate(
            source_id=c["source_id"],
            value=c["value"],
            confidence=c.get("confidence", 1.0),
            observed_at=observed_dt,
            metadata=c.get("metadata", {}),
        ))
    return ConflictRecord(
        id=d.get("id", ""),
        entity_id=d["entity_id"],
        entity_type=d.get("entity_type", "unknown"),
        field_name=d["field_name"],
        conflict_type=ConflictType(d.get("conflict_type", "value_mismatch")),
        candidates=cands,
    )


# ---------- 端点 ----------

@router.post("/detect")
async def detect_conflicts(request: DetectRequest):
    """
    检测多源数据中的字段冲突。
    返回: {"conflicts": [...], "count": int}
    """
    try:
        sources = [s.model_dump() for s in request.sources]
        return conflict_service.detect_conflicts(sources)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resolve")
async def resolve_conflict(request: ResolveRequest):
    """
    解决单条冲突。
    request.conflict 必须包含 entity_id/field_name/candidates[]
    request.strategy 必填（first_wins/last_wins/llm_judge/manual）
    """
    try:
        record = _to_record(request.conflict)
        return conflict_service.resolve_conflict(record, request.strategy, request.context)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conflicts")
async def list_conflicts(status: Optional[str] = None):
    """
    列出冲突（占位：暂存于内存；生产环境应由 storage/ 持久化）。
    当前仅返回空列表 + 状态校验，避免误导。
    """
    try:
        if status is not None and status not in {"pending", "resolved", "abandoned", "awaiting_human"}:
            raise HTTPException(status_code=400, detail=f"unknown status: {status}")
        return {"conflicts": [], "count": 0, "status": status}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
