"""
Inheritance API 路由 (T371)

前缀: /api/ontology/inheritance
端点:
  POST   /edges                          添加继承边
  DELETE /edges/{child_id}/{parent_id}   删除边
  GET    /edges                          查询边 (?child=&parent=)
  GET    /resolve/{type_id}              解析 ObjectType 属性链
  POST   /mixins                         创建 Mixin
  GET    /mixins                         列出 Mixin
  GET    /mixins/{mixin_id}              获取 Mixin
  PUT    /mixins/{mixin_id}              更新
  DELETE /mixins/{mixin_id}              删除
  POST   /mixins/{mixin_id}/attach/{type_id}
  POST   /mixins/{mixin_id}/detach/{type_id}
  POST   /validate                       body: {"type_id": "..."}

对齐 AGENTS.md 规则 3：路由层必须 `except HTTPException: raise`。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from ..services import InheritanceService
from .schemas import (
    AddEdgeRequest,
    CreateMixinRequest,
    UpdateMixinRequest,
    ValidateRequest,
)


router = APIRouter(prefix="/api/ontology/inheritance", tags=["inheritance"])

# 模块级单例
inheritance_service = InheritanceService()


# ---------- edges ----------

@router.post("/edges")
async def add_edge(request: AddEdgeRequest):
    """添加继承边（先验证再添加）"""
    try:
        result = inheritance_service.add_edge(
            child_id=request.child_type_id,
            parent_id=request.parent_type_id,
            discriminator=request.discriminator,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/edges/{child_id}/{parent_id}")
async def remove_edge(child_id: str, parent_id: str):
    """删除继承边"""
    try:
        result = inheritance_service.remove_edge(child_id, parent_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/edges")
async def list_edges(
    child: Optional[str] = None,
    parent: Optional[str] = None,
):
    """查询继承边（可按 child/parent 过滤）"""
    try:
        return inheritance_service.list_edges(child_id=child, parent_id=parent)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resolve/{type_id}")
async def resolve_type(type_id: str):
    """解析 ObjectType 完整属性链"""
    try:
        return inheritance_service.resolve_type(type_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_inheritance(request: ValidateRequest):
    """验证指定 ObjectType 的继承图 + Mixin 冲突"""
    try:
        return inheritance_service.validate_type(request.type_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------- mixins ----------

@router.post("/mixins")
async def create_mixin(request: CreateMixinRequest):
    """创建 Mixin"""
    try:
        result = inheritance_service.add_mixin(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mixins")
async def list_mixins():
    """列出所有 Mixin"""
    try:
        return inheritance_service.list_mixins()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mixins/{mixin_id}")
async def get_mixin(mixin_id: str):
    """获取 Mixin"""
    try:
        result = inheritance_service.get_mixin(mixin_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/mixins/{mixin_id}")
async def update_mixin(mixin_id: str, request: UpdateMixinRequest):
    """更新 Mixin"""
    try:
        data = request.model_dump(exclude_none=True)
        result = inheritance_service.update_mixin(mixin_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mixins/{mixin_id}")
async def delete_mixin(mixin_id: str):
    """删除 Mixin"""
    try:
        result = inheritance_service.remove_mixin(mixin_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mixins/{mixin_id}/attach/{type_id}")
async def attach_mixin(mixin_id: str, type_id: str):
    """附加 Mixin 到 Type"""
    try:
        result = inheritance_service.attach_mixin_to_type(mixin_id, type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mixins/{mixin_id}/detach/{type_id}")
async def detach_mixin(mixin_id: str, type_id: str):
    """从 Type 分离 Mixin"""
    try:
        result = inheritance_service.detach_mixin_from_type(mixin_id, type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
