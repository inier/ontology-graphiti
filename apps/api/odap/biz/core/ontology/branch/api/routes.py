"""
Branch & Merge API 路由 (T357)

路由前缀: /api/ontology/branches
端点（**静态路径优先于动态路径**，避免 FastAPI 路由匹配冲突）:
  POST   /                                    创建分支
  GET    /                                    列出分支 (?ontology_id=)
  GET    /merge-requests                      列出 MR (?branch_id=&status=)
  POST   /{branch_id}/merge-requests          创建合并请求
  GET    /merge-requests/{mr_id}              获取 MR
  POST   /merge-requests/{mr_id}/detect-conflicts   检测冲突
  POST   /merge-requests/{mr_id}/resolve      解决冲突
  POST   /merge-requests/{mr_id}/execute      执行合并
  GET    /merge-requests/{mr_id}/conflicts    列出 MR 冲突
  GET    /{branch_id}                         获取分支
  DELETE /{branch_id}                         删除分支
  GET    /{branch_id}/lineage                 分支父子链
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from ..services import BranchService
from .schemas import (
    ConflictResolutionRequest,
    CreateBranchRequest,
    CreateMergeRequestRequest,
)


router = APIRouter(prefix="/api/ontology/branches", tags=["branches"])

# 模块级单例
branch_service = BranchService()


# ---------- 静态路径必须先声明（FastAPI 按声明顺序匹配）----------

@router.post("")
async def create_branch(request: CreateBranchRequest):
    """创建分支"""
    try:
        result = branch_service.create_branch(
            name=request.name,
            ontology_id=request.ontology_id,
            base_version_id=request.base_version_id,
            description=request.description,
            created_by=request.created_by,
            head_version_id=request.head_version_id,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_branches(ontology_id: Optional[str] = None):
    """列出分支（可按 ontology_id 过滤）"""
    try:
        return branch_service.list_branches(ontology_id=ontology_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- MergeRequest 静态路径（在 /{branch_id} 之前）----------

@router.get("/merge-requests")
async def list_merge_requests(
    branch_id: Optional[str] = None,
    status: Optional[str] = None,
):
    """列出合并请求"""
    try:
        return branch_service.list_merge_requests(branch_id=branch_id, status=status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{branch_id}/merge-requests")
async def create_merge_request(branch_id: str, request: CreateMergeRequestRequest):
    """创建合并请求"""
    try:
        # branch_id 优先作为 source
        src = branch_id or request.source_branch_id
        result = branch_service.create_merge_request(
            source_branch_id=src,
            target_branch_id=request.target_branch_id,
            title=request.title,
            description=request.description,
            base_snapshot=request.base_snapshot,
            ours_snapshot=request.ours_snapshot,
            theirs_snapshot=request.theirs_snapshot,
            created_by=request.created_by,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/merge-requests/{mr_id}")
async def get_merge_request(mr_id: str):
    """获取合并请求"""
    try:
        result = branch_service.get_merge_request(mr_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge-requests/{mr_id}/detect-conflicts")
async def detect_conflicts(mr_id: str):
    """检测 MR 冲突"""
    try:
        result = branch_service.detect_conflicts(mr_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge-requests/{mr_id}/resolve")
async def resolve_conflict(mr_id: str, request: ConflictResolutionRequest):
    """解决 MR 中单条冲突"""
    try:
        # mr_id 仅作为路径占位，conflict_id 决定具体冲突
        _ = mr_id
        result = branch_service.resolve_conflict(
            conflict_id=request.conflict_id,
            resolution=request.resolution,
            resolved_value=request.resolved_value,
            resolved_by=request.resolved_by,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge-requests/{mr_id}/execute")
async def execute_merge(mr_id: str):
    """执行合并"""
    try:
        result = branch_service.execute_merge(mr_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/merge-requests/{mr_id}/conflicts")
async def list_conflicts(mr_id: str):
    """列出 MR 的冲突"""
    try:
        result = branch_service.detect_conflicts(mr_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- 动态路径（最后声明）----------

@router.get("/{branch_id}")
async def get_branch(branch_id: str):
    """获取分支"""
    try:
        result = branch_service.get_branch(branch_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{branch_id}")
async def delete_branch(branch_id: str):
    """删除分支（级联删 MR）"""
    try:
        result = branch_service.delete_branch(branch_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{branch_id}/lineage")
async def get_branch_lineage(branch_id: str):
    """获取分支父子链"""
    try:
        return branch_service.get_lineage(branch_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
