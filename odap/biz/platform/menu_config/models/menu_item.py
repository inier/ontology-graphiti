"""菜单配置领域模型 — RBAC 三级菜单（目录 / 菜单 / 操作）"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field


class MenuType(str, Enum):
    """菜单层级类型"""
    DIRECTORY = "directory"   # 目录：可折叠分组，不对应页面
    MENU = "menu"             # 菜单：可导航页面（内部路由或 iframe）
    ACTION = "action"         # 操作：页面内按钮/权限点（如 创建、编辑、删除）


class MenuLinkType(str, Enum):
    """菜单链接类型（仅 menu 类型使用）"""
    INTERNAL = "internal"     # 平台内部路由
    IFRAME = "iframe"         # 外部 iframe 地址


class MenuItem(BaseModel):
    """菜单项（支持 parent_id 自引用构成树）"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None          # 父节点 ID，NULL 为顶级
    name: str                                # 显示名称
    code: str                                # 权限码（唯一，如 system:user:list）
    menu_type: MenuType = MenuType.MENU
    link_type: MenuLinkType = MenuLinkType.INTERNAL
    path: Optional[str] = None               # 内部路由路径（menu 类型）
    url: Optional[str] = None                # iframe 外部地址（menu + iframe）
    icon: str = "AppstoreOutlined"           # Ant Design 图标名（directory/menu）
    sort_order: int = 0                      # 排序权重（越小越靠前）
    is_active: bool = True                   # 是否启用
    is_visible: bool = True                  # 是否在侧边栏可见（False = 隐藏路由）
    description: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MenuItemTree(BaseModel):
    """菜单树节点（含子节点）"""
    id: str
    parent_id: Optional[str] = None
    name: str
    code: str
    menu_type: MenuType
    link_type: MenuLinkType = MenuLinkType.INTERNAL
    path: Optional[str] = None
    url: Optional[str] = None
    icon: str = "AppstoreOutlined"
    sort_order: int = 0
    is_active: bool = True
    is_visible: bool = True
    description: str = ""
    children: List["MenuItemTree"] = Field(default_factory=list)
