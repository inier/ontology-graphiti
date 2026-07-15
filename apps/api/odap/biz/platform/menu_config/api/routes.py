"""菜单配置管理 API — RBAC 三级菜单 + 角色权限分配

提供侧边栏菜单树的 CRUD、角色-菜单权限分配接口。
管理员可配置菜单树和角色权限；普通用户按角色获取可见菜单。

路由前缀: /api/menu-config
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from odap.infra.security.jwt_auth import get_current_user
from ..services.menu_config_service import MenuConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/menu-config", tags=["menu-config"])

menu_config_service = MenuConfigService()


# ── 请求/响应模型 ──

class CreateMenuItemRequest(BaseModel):
    name: str
    code: Optional[str] = None
    parent_id: Optional[str] = None
    menu_type: str = "menu"
    link_type: str = "internal"
    path: Optional[str] = None
    url: Optional[str] = None
    icon: str = "AppstoreOutlined"
    sort_order: int = 0
    is_active: bool = True
    is_visible: bool = True
    description: str = ""


class UpdateMenuItemRequest(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    parent_id: Optional[str] = None
    menu_type: Optional[str] = None
    link_type: Optional[str] = None
    path: Optional[str] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    is_visible: Optional[bool] = None
    description: Optional[str] = None


class SetRoleMenusRequest(BaseModel):
    role_id: str
    menu_item_ids: List[str]


# ── 权限检查 ──

def _is_admin(user: dict) -> bool:
    """JWT payload 可能包含 role/role_type/roles 多种字段格式，需要全部兼容。"""
    if not isinstance(user, dict):
        return False
    # 方式一：role 字段直接等于 "admin"
    if user.get("role") == "admin":
        return True
    # 方式二：roles 数组中包含 "admin"
    roles = user.get("roles", [])
    if isinstance(roles, list) and "admin" in roles:
        return True
    # 方式三：role_type 为 system_admin
    if user.get("role_type") == "system_admin":
        return True
    return False


def _user_role_ids(user: dict) -> List[str]:
    """从 JWT payload 提取角色 ID 列表，兼容多种字段格式。"""
    if not isinstance(user, dict):
        return []
    ids = set()
    # role 字段（可能是数字 ID 如 "1" 或字符串如 "admin"）
    role = user.get("role", "")
    if role and role != "admin":  # "admin" 已由 _is_admin 单独处理
        ids.add(role)
    # roles 数组中的非 admin 项
    roles = user.get("roles", [])
    if isinstance(roles, list):
        for r in roles:
            if r != "admin":
                ids.add(r)
    # ws_role
    ws_role = user.get("ws_role", "")
    if ws_role:
        ids.add(ws_role)
    # role_type 作为备选
    role_type = user.get("role_type", "")
    if role_type:
        ids.add(role_type)
    return list(ids)


# ═══════════════════════════════════════════════════
#  公开接口：侧边栏菜单树
# ═══════════════════════════════════════════════════

@router.get("/tree")
async def get_menu_tree(user=Depends(get_current_user)):
    """获取当前用户可见的菜单树（按角色过滤）"""
    try:
        if _is_admin(user):
            tree = menu_config_service.get_user_menu_tree([], is_admin=True)
        else:
            role_ids = _user_role_ids(user)
            tree = menu_config_service.get_user_menu_tree(role_ids)
        return {"tree": tree}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items")
async def list_menu_items(
    menu_type: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """获取已启用的菜单项扁平列表（按角色过滤）"""
    try:
        if _is_admin(user):
            result = menu_config_service.list_items(active_only=True, menu_type=menu_type)
        else:
            role_ids = _user_role_ids(user)
            items = menu_config_service._storage.get_menus_for_roles(role_ids, active_only=True)
            if menu_type:
                items = [i for i in items if i.get("menu_type") == menu_type]
            result = {"items": items, "total": len(items)}
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════
#  管理接口：仅管理员
# ═══════════════════════════════════════════════════

@router.get("/items/all")
async def list_all_menu_items(
    menu_type: Optional[str] = Query(None),
    user=Depends(get_current_user),
):
    """获取全部菜单项（含禁用，仅管理员）"""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        return menu_config_service.list_items(active_only=False, menu_type=menu_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tree/all")
async def get_full_tree(user=Depends(get_current_user)):
    """获取完整菜单树（含禁用项，仅管理员）"""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        tree = menu_config_service.get_tree(active_only=False)
        return {"tree": tree}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/items")
async def create_menu_item(
    request: CreateMenuItemRequest,
    user=Depends(get_current_user),
):
    """创建菜单项（仅管理员）"""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        result = menu_config_service.create_item(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/items/{item_id}")
async def update_menu_item(
    item_id: str,
    request: UpdateMenuItemRequest,
    user=Depends(get_current_user),
):
    """更新菜单项（仅管理员）"""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        data = {k: v for k, v in request.model_dump().items() if v is not None}
        result = menu_config_service.update_item(item_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/items/{item_id}")
async def delete_menu_item(
    item_id: str,
    user=Depends(get_current_user),
):
    """删除菜单项（仅管理员，级联删除子节点和角色关联）"""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        result = menu_config_service.delete_item(item_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════
#  角色-菜单权限分配
# ═══════════════════════════════════════════════════

@router.post("/role-menus")
async def set_role_menus(
    request: SetRoleMenusRequest,
    user=Depends(get_current_user),
):
    """设置角色的菜单权限（全量替换，仅管理员）"""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        return menu_config_service.set_role_menus(request.role_id, request.menu_item_ids)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/role-menus/{role_id}")
async def get_role_menus(
    role_id: str,
    user=Depends(get_current_user),
):
    """获取角色已分配的菜单项"""
    try:
        return menu_config_service.get_role_menus(role_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/menu-roles/{menu_item_id}")
async def get_menu_roles(
    menu_item_id: str,
    user=Depends(get_current_user),
):
    """获取菜单项关联的角色列表（反向查询）"""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    try:
        return menu_config_service.get_menu_roles(menu_item_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
