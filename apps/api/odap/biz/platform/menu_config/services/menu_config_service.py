"""菜单配置服务 — RBAC 三级菜单树 + 角色权限"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..storage import Storage

logger = logging.getLogger(__name__)

# ── 审计工具（懒加载 + 容错） ──
def _menu_audit(action: str, *, result_status: str = "success",
                result_message: str = "", resource: str = None,
                details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(
            action=action,
            result_status=result_status,
            result_message=result_message,
            resource=resource,
            details=details or {},
            service="platform_menu",
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


class MenuConfigService:
    """菜单配置业务逻辑（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._storage = Storage()
        self._initialized = True

    # ── 菜单项 CRUD ──

    def list_items(
        self, active_only: bool = True, menu_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        items = self._storage.list_menu_items(active_only=active_only, menu_type=menu_type)
        return {"items": items, "total": len(items)}

    def get_item(self, item_id: str) -> Dict[str, Any]:
        item = self._storage.get_menu_item(item_id)
        if not item:
            return {"status": "error", "message": "菜单项不存在"}
        return item

    def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        code = data.get("code") or self._auto_code(data)
        # 校验 code 唯一
        if self._storage.get_menu_item_by_code(code):
            _menu_audit(
                action="menu_create",
                result_status="failure",
                result_message=f"权限码 '{code}' 已存在"[:200],
                resource="",
                details={"code": code, "name_len": len(data.get("name", ""))},
            )
            return {"status": "error", "message": f"权限码 '{code}' 已存在"}
        item = {
            "id": data.get("id") or uuid.uuid4().hex[:12],
            "parent_id": data.get("parent_id") or None,
            "name": data["name"],
            "code": code,
            "menu_type": data.get("menu_type", "menu"),
            "link_type": data.get("link_type", "internal"),
            "path": data.get("path"),
            "url": data.get("url"),
            "icon": data.get("icon", "AppstoreOutlined"),
            "sort_order": data.get("sort_order", 0),
            "is_active": data.get("is_active", True),
            "is_visible": data.get("is_visible", True),
            "description": data.get("description", ""),
            "created_at": now,
            "updated_at": now,
        }
        result = self._storage.save_menu_item(item)
        _menu_audit(
            action="menu_create",
            result_status="success",
            resource=item["id"],
            details={
                "menu_id": item["id"],
                "menu_type": item.get("menu_type", ""),
                "code": code,
                "name_len": len(item.get("name", "")),
            },
        )
        return result

    def update_item(self, item_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self._storage.get_menu_item(item_id)
        if not existing:
            _menu_audit(
                action="menu_update",
                result_status="failure",
                result_message="Menu not found",
                resource=item_id,
                details={"menu_id": item_id},
            )
            return {"status": "error", "message": "菜单项不存在"}
        # 如果更新 code，检查唯一性
        new_code = data.get("code")
        if new_code and new_code != existing["code"]:
            dup = self._storage.get_menu_item_by_code(new_code)
            if dup and dup["id"] != item_id:
                _menu_audit(
                    action="menu_update",
                    result_status="failure",
                    result_message=f"Duplicate code: {new_code}"[:200],
                    resource=item_id,
                    details={"menu_id": item_id},
                )
                return {"status": "error", "message": f"权限码 '{new_code}' 已存在"}
        changed = []
        for key in ("parent_id", "name", "code", "menu_type", "link_type",
                     "path", "url", "icon", "sort_order", "is_active",
                     "is_visible", "description"):
            if key in data:
                existing[key] = data[key]
                changed.append(key)
        existing["updated_at"] = datetime.now().isoformat()
        result = self._storage.save_menu_item(existing)
        _menu_audit(
            action="menu_update",
            result_status="success",
            resource=item_id,
            details={
                "menu_id": item_id,
                "changed_fields": changed,
                "field_count": len(changed),
            },
        )
        return result

    def delete_item(self, item_id: str) -> Dict[str, Any]:
        deleted = self._storage.delete_menu_item(item_id)
        _menu_audit(
            action="menu_delete",
            result_status="success" if deleted else "failure",
            result_message="" if deleted else "Menu not found",
            resource=item_id,
            details={"menu_id": item_id},
        )
        if deleted:
            return {"status": "success", "message": "已删除"}
        return {"status": "error", "message": "菜单项不存在"}

    # ── 树形结构 ──

    def get_tree(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """返回完整菜单树（嵌套 children）"""
        items = self._storage.list_menu_items(active_only=active_only)
        return self._build_tree(items)

    def get_user_menu_tree(
        self, role_ids: List[str], is_admin: bool = False,
    ) -> List[Dict[str, Any]]:
        """根据用户角色返回可见菜单树"""
        if is_admin:
            items = self._storage.list_menu_items(active_only=True)
        else:
            items = self._storage.get_menus_for_roles(role_ids, active_only=True)
        return self._build_tree(items)

    def _build_tree(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """扁平列表 → 树形结构"""
        item_map: Dict[str, Dict] = {}
        roots: List[Dict] = []

        for item in items:
            node = {**item, "children": []}
            item_map[item["id"]] = node

        for item in items:
            node = item_map[item["id"]]
            pid = item.get("parent_id")
            if pid and pid in item_map:
                item_map[pid]["children"].append(node)
            else:
                roots.append(node)

        return roots

    # ── 角色权限 ──

    def set_role_menus(self, role_id: str, menu_item_ids: List[str]) -> Dict[str, Any]:
        self._storage.set_role_menus(role_id, menu_item_ids)
        return {"status": "success", "role_id": role_id, "count": len(menu_item_ids)}

    def get_role_menus(self, role_id: str) -> Dict[str, Any]:
        menu_ids = self._storage.get_role_menu_ids(role_id)
        items = self._storage.list_menu_items_by_ids(menu_ids, active_only=False)
        return {"role_id": role_id, "menu_ids": menu_ids, "items": items}

    def get_menu_roles(self, menu_item_id: str) -> Dict[str, Any]:
        role_ids = self._storage.get_menu_role_ids(menu_item_id)
        return {"menu_item_id": menu_item_id, "role_ids": role_ids}

    # ── 工具方法 ──

    def _auto_code(self, data: Dict[str, Any]) -> str:
        """自动生成权限码"""
        menu_type = data.get("menu_type", "menu")
        name = data.get("name", "unnamed")
        prefix = {"directory": "dir", "menu": "menu", "action": "act"}.get(menu_type, "menu")
        slug = name.lower().replace(" ", "_")[:30]
        return f"{prefix}:{slug}:{uuid.uuid4().hex[:6]}"
